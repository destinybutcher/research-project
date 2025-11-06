"""CP-SAT constraint-based scheduler for optimal shift assignments."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session

from scheduler.domain.models import Assignment, Employee, Shift
from scheduler.domain.repositories import EmployeeRepository, ShiftRepository
from scheduler.services.requirements import build_requirements_for_day
from scheduler.services.scoring import calculate_role_fitness

from .skill_loader import load_averaged_skills, update_employee_skills_from_history


class CPSatScheduler:
    """
    CP-SAT based scheduler that optimizes for skill match and fairness.
    
    Uses Google OR-Tools CP-SAT solver to find optimal assignments considering:
    - Skill-based fitness scores
    - Fairness in hours distribution
    - Hard constraints (coverage, caps, role compatibility)
    """
    
    def __init__(
        self,
        historical_skills_path: Optional[str] = None,
        skill_match_weight: float = 1.0,
        fairness_weight: float = 0.3,
    ):
        """
        Initialize CP-SAT scheduler.
        
        Args:
            historical_skills_path: Path to shiftDetails CSV for averaging skills
            skill_match_weight: Weight for skill match in objective (default: 1.0)
            fairness_weight: Weight for fairness in objective (default: 0.3)
        """
        self.historical_skills_path = historical_skills_path
        self.skill_match_weight = skill_match_weight
        self.fairness_weight = fairness_weight
        
        # Will be loaded when needed
        self.skill_averages: Optional[Dict[int, Dict[str, float]]] = None
    
    def make_schedule(
        self,
        session: Session,
        week_id: str,
        cfg,
    ) -> List[Assignment]:
        """
        Generate optimal schedule for the week using CP-SAT.
        
        Args:
            session: Database session
            week_id: ISO week identifier
            cfg: SchedulerConfig
        
        Returns:
            List of Assignment objects
        """
        print(f"[INFO] CP-SAT Scheduler: Building schedule for {week_id}")
        
        # Load employees and shifts
        employees = EmployeeRepository.get_all(session)
        shifts = ShiftRepository.get_by_week(session, week_id)
        
        if not employees:
            raise RuntimeError("No employees available")
        if not shifts:
            raise RuntimeError(f"No shifts found for week {week_id}")
        
        # Load and apply historical skill averages if available
        if self.historical_skills_path:
            print(f"[INFO] Loading historical skills from {self.historical_skills_path}")
            self.skill_averages = load_averaged_skills(self.historical_skills_path)
            update_employee_skills_from_history(employees, self.skill_averages)
        
        # Build model
        model = cp_model.CpModel()
        
        # Create decision variables and helper structures
        assignments_dict, shift_role_slots, employee_roles = self._create_variables(
            model, employees, shifts, cfg
        )
        
        # Add constraints
        self._add_coverage_constraints(
            model, assignments_dict, shift_role_slots, shifts, cfg
        )
        self._add_one_shift_per_day_constraints(
            model, assignments_dict, employee_roles, shifts, cfg
        )
        self._add_hours_constraints(
            model, assignments_dict, employee_roles, shifts, employees, cfg
        )
        
        # Build objective
        self._build_objective(
            model, assignments_dict, employee_roles, employees, shifts, cfg
        )
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0  # Time limit
        solver.parameters.num_search_workers = 4  # Parallel search
        
        print(f"[INFO] Solving CP-SAT model...")
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"[OK] Solution found (status: {self._status_name(status)})")
            assignments = self._extract_solution(
                solver, assignments_dict, employee_roles, employees, shifts, cfg
            )
            print(f"[OK] Generated {len(assignments)} assignments")
            return assignments
        else:
            raise RuntimeError(
                f"CP-SAT solver failed to find solution (status: {self._status_name(status)})"
            )
    
    def _create_variables(
        self,
        model: cp_model.CpModel,
        employees: List[Employee],
        shifts: List[Shift],
        cfg,
    ) -> Tuple[Dict, Dict, Dict]:
        """
        Create decision variables for the model.
        
        Returns:
            (assignments_dict, shift_role_slots, employee_roles)
            assignments_dict: {(shift_id, emp_id, role, slot_idx): BoolVar}
            shift_role_slots: {shift_id: [(role, slot_idx)]} - all slots needed
            employee_roles: {emp_id: set of compatible roles}
        """
        assignments_dict = {}
        shift_role_slots = defaultdict(list)
        employee_roles = {}
        
        # Group employees by role
        employees_by_role = defaultdict(list)
        for emp in employees:
            employees_by_role[emp.primary_role.upper()].append(emp)
            # Employees can only work their primary role (strict compatibility)
            employee_roles[emp.employee_id] = {emp.primary_role.upper()}
        
        # Build shift requirements and create variables
        for shift in shifts:
            date_str = pd.Timestamp(shift.date).strftime("%Y-%m-%d")
            requirements = build_requirements_for_day(date_str, cfg)
            
            # For each required role, create variables for each slot and each compatible employee
            for role, count in requirements.items():
                role = role.upper()
                
                # Only create variables for employees who can work this role
                compatible_employees = employees_by_role.get(role, [])
                
                # Create variables for each slot (slot_idx = 0, 1, 2, ...)
                for slot_idx in range(count):
                    shift_role_slots[shift.shift_id].append((role, slot_idx))
                    
                    for emp in compatible_employees:
                        var_name = f"assign_s{shift.shift_id}_e{emp.employee_id}_r{role}_slot{slot_idx}"
                        assignments_dict[(shift.shift_id, emp.employee_id, role, slot_idx)] = (
                            model.NewBoolVar(var_name)
                        )
        
        return assignments_dict, dict(shift_role_slots), employee_roles
    
    def _add_coverage_constraints(
        self,
        model: cp_model.CpModel,
        assignments_dict: Dict,
        shift_role_slots: Dict,
        shifts: List[Shift],
        cfg,
    ) -> None:
        """Add constraints to ensure each shift slot is properly covered."""
        for shift in shifts:
            if shift.shift_id not in shift_role_slots:
                continue
            
            # For each (role, slot_idx) on this shift, exactly one employee must be assigned
            for role, slot_idx in shift_role_slots[shift.shift_id]:
                # Sum of assignments for this (shift, role, slot) must equal 1
                assignment_vars = [
                    assignments_dict[(shift.shift_id, emp_id, role, slot_idx)]
                    for (s_id, emp_id, r, s_idx) in assignments_dict.keys()
                    if s_id == shift.shift_id and r == role and s_idx == slot_idx
                ]
                
                if assignment_vars:
                    model.Add(sum(assignment_vars) == 1)
    
    def _add_one_shift_per_day_constraints(
        self,
        model: cp_model.CpModel,
        assignments_dict: Dict,
        employee_roles: Dict,
        shifts: List[Shift],
        cfg,
    ) -> None:
        """
        Add constraints: each employee can work at most one shift per day.
        Note: On weekends, staggered shifts may overlap, so we allow assignments
        to the same shift_id (which represents the same day).
        """
        # Group shifts by date
        shifts_by_date = defaultdict(list)
        for shift in shifts:
            shifts_by_date[shift.date].append(shift)
        
        # For each employee and each day
        for emp_id in employee_roles.keys():
            for day, day_shifts in shifts_by_date.items():
                # Get all assignment variables for this employee on this day
                # Note: On weekends, staggered shifts may overlap, but employee can still
                # work only ONE slot total (not one per role, but one total for the day)
                day_assignment_vars = []
                for shift in day_shifts:
                    for role in employee_roles[emp_id]:
                        # Get all slots for this employee-role on this shift
                        for (s_id, e_id, r, slot_idx) in assignments_dict.keys():
                            if s_id == shift.shift_id and e_id == emp_id and r == role:
                                day_assignment_vars.append(assignments_dict[(s_id, e_id, r, slot_idx)])
                
                # Employee can work at most one slot per day (even if staggered)
                if len(day_assignment_vars) > 1:
                    model.Add(sum(day_assignment_vars) <= 1)
    
    def _add_hours_constraints(
        self,
        model: cp_model.CpModel,
        assignments_dict: Dict,
        employee_roles: Dict,
        shifts: List[Shift],
        employees: List[Employee],
        cfg,
    ) -> None:
        """Add constraints for minimum and maximum hours per employee."""
        from scheduler.services.requirements import build_requirements_for_day
        from scheduler.services.timeplan import get_time_window_for_role
        
        # Calculate shift durations per (shift_id, role) pair
        shift_role_durations = {}
        for shift in shifts:
            date_obj = shift.date
            day_name = pd.Timestamp(date_obj).day_name()
            is_weekend = day_name in ["Saturday", "Sunday"]
            
            # Get requirements to know which roles are needed
            date_str = pd.Timestamp(date_obj).strftime("%Y-%m-%d")
            requirements = build_requirements_for_day(date_str, cfg)
            
            for role, count in requirements.items():
                # Calculate duration for each slot (for staggered shifts)
                for slot_idx in range(count):
                    start_hm, end_hm = get_time_window_for_role(role, date_obj, cfg, slot_index=slot_idx)
                    duration = (pd.Timestamp(f"{date_obj} {end_hm}") - 
                               pd.Timestamp(f"{date_obj} {start_hm}")).total_seconds() / 3600
                    
                    # Store duration per (shift_id, role, slot_idx)
                    shift_role_durations[(shift.shift_id, role, slot_idx)] = duration
        
        # Create helper variables for total hours per employee
        employee_hours = {}
        
        for emp in employees:
            emp_id = emp.employee_id
            hours_terms = []  # List of (var, coefficient) pairs
            
            for (s_id, e_id, role, slot_idx) in assignments_dict.keys():
                if e_id == emp_id:
                    duration = shift_role_durations.get((s_id, role, slot_idx), 8.0)
                    # Multiply by 10 to work with integers (e.g., 8.0 -> 80)
                    duration_int = int(round(duration * 10))
                    hours_terms.append((assignments_dict[(s_id, e_id, role, slot_idx)], duration_int))
            
            if hours_terms:
                # Create total hours variable (in units of 0.1 hours, so 400 = 40.0 hours)
                max_hours_int = int((cfg.global_hard_cap or 45) * 10)
                total_hours = model.NewIntVar(0, max_hours_int, f"hours_e{emp_id}")
                
                # Sum: total_hours = sum(assignment * duration)
                model.Add(total_hours == sum(
                    var * coeff for var, coeff in hours_terms
                ))
                employee_hours[emp_id] = total_hours
                
                # Hard cap constraint
                hard_cap = cfg.hours_policy.get(emp.primary_role.upper(), {}).get('hard_cap', 40)
                model.Add(total_hours <= int(hard_cap * 10))
        
        # Store for objective function
        self._employee_hours_vars = employee_hours
    
    def _build_objective(
        self,
        model: cp_model.CpModel,
        assignments_dict: Dict,
        employee_roles: Dict,
        employees: List[Employee],
        shifts: List[Shift],
        cfg,
    ) -> None:
        """
        Build objective function: maximize skill match, minimize fairness violations.
        """
        # Compute skill scores for each assignment
        employees_dict = {emp.employee_id: emp for emp in employees}
        weights = cfg.weights.__dict__ if hasattr(cfg.weights, '__dict__') else {}
        
        objective_terms = []
        
        # 1. Skill match component (maximize)
        for (s_id, emp_id, role, slot_idx) in assignments_dict.keys():
            if emp_id in employees_dict:
                emp = employees_dict[emp_id]
                skill_score = calculate_role_fitness(emp, role, weights)
                # Scale to integer (multiply by 100 for precision)
                objective_terms.append(
                    assignments_dict[(s_id, emp_id, role, slot_idx)] * int(skill_score * 100 * self.skill_match_weight)
                )
        
        # 2. Fairness component (minimize max - min hours per role)
        # For simplicity, we'll add a penalty for deviation from average hours
        # More complex: minimize max_hours - min_hours for each role cohort
        
        # Group employees by role
        employees_by_role = defaultdict(list)
        for emp in employees:
            employees_by_role[emp.primary_role.upper()].append(emp.employee_id)
        
        # For each role, minimize variance in hours
        for role, emp_ids in employees_by_role.items():
            if len(emp_ids) < 2:
                continue
            
            role_hours = [
                self._employee_hours_vars.get(emp_id)
                for emp_id in emp_ids
                if emp_id in self._employee_hours_vars
            ]
            
            if len(role_hours) >= 2:
                # Minimize max - min (fairness)
                max_hours = model.NewIntVar(0, 400, f"max_hours_{role}")
                min_hours = model.NewIntVar(0, 400, f"min_hours_{role}")
                
                model.AddMaxEquality(max_hours, role_hours)
                model.AddMinEquality(min_hours, role_hours)
                
                # Penalty for unfairness (max - min)
                unfairness = model.NewIntVar(0, 400, f"unfairness_{role}")
                model.Add(unfairness == max_hours - min_hours)
                
                # Subtract from objective (minimize unfairness)
                objective_terms.append(-unfairness * int(self.fairness_weight * 100))
        
        # Maximize total objective
        model.Maximize(sum(objective_terms))
    
    def _extract_solution(
        self,
        solver: cp_model.CpSolver,
        assignments_dict: Dict,
        employee_roles: Dict,
        employees: List[Employee],
        shifts: List[Shift],
        cfg,
    ) -> List[Assignment]:
        """Extract assignment objects from solver solution."""
        employees_dict = {emp.employee_id: emp for emp in employees}
        shifts_dict = {shift.shift_id: shift for shift in shifts}
        
        assignments = []
        timezone = cfg.timezone
        
        # Helper to get time window for role
        from scheduler.services.timeplan import get_time_window_for_role
        
        for (s_id, emp_id, role, slot_idx), var in assignments_dict.items():
            if solver.Value(var) == 1:
                shift = shifts_dict.get(s_id)
                if not shift:
                    continue
                
                emp = employees_dict.get(emp_id)
                if not emp:
                    continue
                
                # Determine time window using the slot_idx from the solution
                start_hm, end_hm = get_time_window_for_role(
                    role, shift.date, cfg, slot_index=slot_idx
                )
                
                # Create datetime objects
                start_dt = pd.Timestamp(f"{shift.date} {start_hm}").tz_localize(timezone)
                end_dt = pd.Timestamp(f"{shift.date} {end_hm}").tz_localize(timezone)
                
                # Determine shift_type and day_type
                day_name = pd.Timestamp(shift.date).day_name()
                is_weekend = day_name in ["Saturday", "Sunday"]
                
                if is_weekend:
                    shift_type = f"weekend_slot{slot_idx+1}"
                    day_type = "weekend"
                else:
                    shift_type = "weekday"
                    day_type = "weekday"
                
                assignment = Assignment(
                    shift_id=s_id,
                    emp_id=emp_id,
                    start_time=start_dt,
                    end_time=end_dt,
                    role=role,
                    shift_type=shift_type,
                    day_type=day_type,
                )
                assignments.append(assignment)
        
        return assignments
    
    def _status_name(self, status: int) -> str:
        """Convert solver status to string."""
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        return status_map.get(status, f"UNKNOWN({status})")

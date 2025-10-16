"""Constraint checking and validation for scheduling."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Set

from scheduler.domain.models import Assignment, Employee


def can_assign_employee(
    employee: Employee,
    role: str,
    shift_date: date,
    shift_hours: float,
    assigned_today: Set[int],
    weekly_hours: Dict[int, float],
    hours_policy: Dict,
    global_hard_cap: float = 50.0,
) -> bool:
    """
    Check if an employee can be assigned to a shift based on hard constraints.
    
    Args:
        employee: Employee to check
        role: Role to assign (must match employee.primary_role)
        shift_date: Date of the shift
        shift_hours: Hours for this shift
        assigned_today: Set of employee IDs already assigned today
        weekly_hours: Dict of emp_id -> hours worked this week
        hours_policy: Role-based hours policy from config
        global_hard_cap: Global maximum hours per week
    
    Returns:
        True if employee can be assigned, False otherwise
    """
    emp_id = employee.employee_id
    
    # 1. Role eligibility
    if employee.primary_role.upper() != role.upper():
        return False
    
    # 2. Not already assigned today
    if emp_id in assigned_today:
        return False
    
    # 3. Weekly hours cap
    current_hours = weekly_hours.get(emp_id, 0.0)
    post_assignment_hours = current_hours + shift_hours
    
    # Check role-specific hard cap
    role_policy = hours_policy.get(role.upper(), {})
    role_hard_cap = role_policy.get('hard_cap', global_hard_cap)
    
    if post_assignment_hours > role_hard_cap:
        return False
    
    # Check global hard cap
    if post_assignment_hours > global_hard_cap:
        return False
    
    return True


def validate_assignment_constraints(
    assignments: List[Assignment],
    employees: List[Employee],
    cfg,
) -> None:
    """
    Validate a set of assignments against all hard constraints.
    
    Args:
        assignments: List of assignments to validate
        employees: List of all employees
        cfg: SchedulerConfig
    
    Raises:
        ValueError: If any constraint is violated
    """
    # Build employee lookup
    emp_lookup = {emp.employee_id: emp for emp in employees}
    
    # Track assignments by employee by date
    emp_by_date: Dict[int, Dict[date, List[Assignment]]] = {}
    
    for assign in assignments:
        emp_id = assign.emp_id
        shift_date = assign.start_time.date()
        
        if emp_id not in emp_by_date:
            emp_by_date[emp_id] = {}
        if shift_date not in emp_by_date[emp_id]:
            emp_by_date[emp_id][shift_date] = []
        
        emp_by_date[emp_id][shift_date].append(assign)
    
    # 1. Check for overlaps within same day
    for emp_id, date_assignments in emp_by_date.items():
        for shift_date, day_assigns in date_assignments.items():
            if len(day_assigns) > 1:
                # Check for time overlaps
                for i, a1 in enumerate(day_assigns):
                    for a2 in day_assigns[i+1:]:
                        if a1.start_time < a2.end_time and a2.start_time < a1.end_time:
                            raise ValueError(
                                f"Employee {emp_id} has overlapping assignments on {shift_date}: "
                                f"{a1.start_time} - {a1.end_time} overlaps {a2.start_time} - {a2.end_time}"
                            )
    
    # 2. Check weekly hours caps
    weekly_hours: Dict[int, float] = {}
    for assign in assignments:
        emp_id = assign.emp_id
        hours = (assign.end_time - assign.start_time).total_seconds() / 3600
        weekly_hours[emp_id] = weekly_hours.get(emp_id, 0.0) + hours
    
    for emp_id, total_hours in weekly_hours.items():
        emp = emp_lookup.get(emp_id)
        if emp:
            role = emp.primary_role
            role_policy = getattr(cfg, 'hours_policy', {}).get(role, {})
            hard_cap = role_policy.get('hard_cap', 40.0)
            
            if total_hours > hard_cap:
                raise ValueError(
                    f"Employee {emp_id} ({emp.first_name} {emp.last_name}) exceeds weekly hard cap: "
                    f"{total_hours:.1f}h > {hard_cap}h"
                )
    
    # 3. Check café hours (except SANDWICH can start early)
    for assign in assignments:
        emp = emp_lookup.get(assign.emp_id)
        if emp and emp.primary_role != "SANDWICH":
            # Non-SANDWICH roles must work within café hours
            start_hour = assign.start_time.hour
            end_hour = assign.end_time.hour
            
            if start_hour < 7:
                raise ValueError(
                    f"Assignment {assign.id} starts before café hours (07:00): {assign.start_time}"
                )
            if end_hour > 15:
                raise ValueError(
                    f"Assignment {assign.id} ends after café hours (15:00): {assign.end_time}"
                )
    
    print("[OK] All assignment constraints validated")


"""Orchestrator - coordinates all role-specific schedulers to build a complete week schedule."""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from scheduler.domain.models import Assignment, Employee
from scheduler.domain.repositories import AssignmentRepository, EmployeeRepository, ShiftRepository
from scheduler.services.constraints import validate_assignment_constraints

from .base import BaseScheduler
from .cohort import CohortScheduler
from .manager import ManagerScheduler
from .sandwich import SandwichScheduler


class Orchestrator:
    """
    Orchestrator coordinates multiple role-specific schedulers.
    
    Each scheduler generates assignments for its role(s) independently,
    then the orchestrator merges and validates the complete schedule.
    """
    
    def __init__(self, scheduler_order: List[str] | None = None):
        """
        Initialize orchestrator with scheduler execution order.
        
        Args:
            scheduler_order: Order to execute schedulers (default: MANAGER, SANDWICH, BARISTA, WAITER)
        """
        self.scheduler_order = scheduler_order or ["MANAGER", "SANDWICH", "BARISTA", "WAITER"]
    
    def build_schedule(
        self,
        session: Session,
        week_id: str,
        cfg,
    ) -> List[Assignment]:
        """
        Build complete schedule for a week using all role schedulers.
        
        Args:
            session: Database session
            week_id: ISO week identifier
            cfg: SchedulerConfig
        
        Returns:
            List of all assignments for the week
        """
        print(f"[INFO] Orchestrator: Building schedule for {week_id}")
        print(f"[INFO] Scheduler order: {self.scheduler_order}")
        
        # Create schedulers in configured order
        schedulers: List[BaseScheduler] = []
        for role in self.scheduler_order:
            if role == "MANAGER":
                schedulers.append(ManagerScheduler())
            elif role == "SANDWICH":
                schedulers.append(SandwichScheduler())
            elif role in ["BARISTA", "WAITER"]:
                schedulers.append(CohortScheduler(role))
            else:
                print(f"[WARN] Unknown role {role} in scheduler_order, skipping")
        
        # Run each scheduler
        all_assignments: List[Assignment] = []
        for scheduler in schedulers:
            role_name = scheduler.get_role_name()
            print(f"\n[INFO] Running {role_name} scheduler...")
            
            try:
                assignments = scheduler.make_schedule(session, week_id, cfg)
                all_assignments.extend(assignments)
                print(f"[OK] {role_name} scheduler completed: {len(assignments)} assignments")
            except RuntimeError as e:
                print(f"[ERROR] {role_name} scheduler failed: {e}")
                raise
        
        # Global validation
        print(f"\n[INFO] Validating complete schedule...")
        employees = EmployeeRepository.get_all(session)
        validate_assignment_constraints(all_assignments, employees, cfg)
        
        print(f"[OK] Orchestrator: Generated {len(all_assignments)} total assignments")
        return all_assignments


def build_week_schedule(
    session: Session,
    week_id: str,
    cfg,
    scheduler_order: List[str] | None = None,
    persist: bool = True,
) -> List[Assignment]:
    """
    Convenience function to build a week schedule using the orchestrator.
    
    Args:
        session: Database session
        week_id: ISO week identifier
        cfg: SchedulerConfig
        scheduler_order: Optional custom scheduler execution order
        persist: If True, save assignments to database
    
    Returns:
        List of assignments
    """
    orchestrator = Orchestrator(scheduler_order)
    assignments = orchestrator.build_schedule(session, week_id, cfg)
    
    if persist:
        # Delete existing assignments for this week
        deleted = AssignmentRepository.delete_by_week(session, week_id)
        if deleted > 0:
            print(f"[INFO] Deleted {deleted} existing assignments for {week_id}")
        
        # Persist new assignments
        AssignmentRepository.bulk_create(session, assignments)
        print(f"[INFO] Persisted {len(assignments)} assignments to database")
    
    return assignments


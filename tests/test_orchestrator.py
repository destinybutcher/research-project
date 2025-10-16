"""Tests for Orchestrator - full week schedule generation."""

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.domain.models import Base, Employee, Shift
from scheduler.engine.orchestrator import Orchestrator, build_week_schedule
from scheduler.io.config import load_config


@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_employees(db_session):
    """Create a full set of employees for all roles."""
    employees = [
        # Managers
        Employee(employee_id=1001, first_name="Max", last_name="Hayes", primary_role="MANAGER"),
        Employee(employee_id=1002, first_name="Mia", last_name="Stone", primary_role="MANAGER"),
        # Waiters
        Employee(employee_id=1003, first_name="Wendy", last_name="Ng", primary_role="WAITER",
                customer_service_rating=5.0, skill_speed=3.0),
        Employee(employee_id=1004, first_name="Will", last_name="Brown", primary_role="WAITER",
                customer_service_rating=4.0, skill_speed=4.0),
        # Baristas
        Employee(employee_id=1005, first_name="Bella", last_name="Tran", primary_role="BARISTA",
                skill_coffee=3.0, skill_speed=3.0, customer_service_rating=3.0),
        Employee(employee_id=1006, first_name="Ben", last_name="Park", primary_role="BARISTA",
                skill_coffee=4.0, skill_speed=4.0, customer_service_rating=4.0),
        # Sandwich
        Employee(employee_id=1007, first_name="Sam", last_name="Lee", primary_role="SANDWICH",
                skill_sandwich=5.0, skill_speed=3.0),
        Employee(employee_id=1008, first_name="Sara", last_name="Khan", primary_role="SANDWICH",
                skill_sandwich=4.0, skill_speed=4.0),
    ]
    db_session.add_all(employees)
    db_session.commit()
    return employees


@pytest.fixture
def sample_shifts(db_session):
    """Create sample shifts for one week."""
    week_id = "2025-W48"
    year = 2025
    week = 48
    dates = [dt.date.fromisocalendar(year, week, dow) for dow in range(1, 8)]
    
    shifts = [
        Shift(shift_id=100000 + i, date=dates[i], week_id=week_id)
        for i in range(7)
    ]
    db_session.add_all(shifts)
    db_session.commit()
    return shifts


@pytest.fixture
def sample_config():
    """Load sample configuration."""
    return load_config("./scheduler_config.yaml")


def test_orchestrator_builds_complete_schedule(db_session, sample_employees, sample_shifts, sample_config):
    """Test that orchestrator creates a complete valid schedule."""
    orchestrator = Orchestrator()
    
    assignments = orchestrator.build_schedule(db_session, "2025-W48", sample_config)
    
    # Should create assignments for all roles
    # Minimum: 7 days × 4 roles = 28 assignments (with weekend extras)
    assert len(assignments) >= 28
    
    # Check all roles are represented
    roles_assigned = set(a.role for a in assignments)
    expected_roles = {"MANAGER", "BARISTA", "WAITER", "SANDWICH"}
    assert roles_assigned == expected_roles


def test_orchestrator_no_employee_overlaps(db_session, sample_employees, sample_shifts, sample_config):
    """Test that no employee has overlapping shifts."""
    orchestrator = Orchestrator()
    
    assignments = orchestrator.build_schedule(db_session, "2025-W48", sample_config)
    
    # Group by employee and date
    emp_by_date = {}
    for assign in assignments:
        key = (assign.emp_id, assign.start_time.date())
        if key not in emp_by_date:
            emp_by_date[key] = []
        emp_by_date[key].append(assign)
    
    # Check for overlaps
    for (emp_id, shift_date), day_assigns in emp_by_date.items():
        if len(day_assigns) > 1:
            for i, a1 in enumerate(day_assigns):
                for a2 in day_assigns[i+1:]:
                    overlap = a1.start_time < a2.end_time and a2.start_time < a1.end_time
                    assert not overlap, f"Employee {emp_id} has overlapping shifts on {shift_date}"


def test_orchestrator_all_employees_assigned(db_session, sample_employees, sample_shifts, sample_config):
    """Test that all employees get at least one assignment."""
    orchestrator = Orchestrator()
    
    assignments = orchestrator.build_schedule(db_session, "2025-W48", sample_config)
    
    # Get unique employee IDs from assignments
    assigned_emp_ids = set(a.emp_id for a in assignments)
    all_emp_ids = {e.employee_id for e in sample_employees}
    
    # All employees should have at least one shift
    assert assigned_emp_ids == all_emp_ids, f"Not all employees assigned: {all_emp_ids - assigned_emp_ids}"


def test_build_week_schedule_persists_to_db(db_session, sample_employees, sample_shifts, sample_config):
    """Test that build_week_schedule persists assignments to database."""
    # Build and persist
    assignments = build_week_schedule(db_session, "2025-W48", sample_config, persist=True)
    
    # Query back from database
    from scheduler.domain.repositories import AssignmentRepository
    db_assignments = AssignmentRepository.get_by_week(db_session, "2025-W48")
    
    # Should match
    assert len(db_assignments) == len(assignments)


def test_orchestrator_custom_order(db_session, sample_employees, sample_shifts, sample_config):
    """Test that orchestrator respects custom scheduler order."""
    # Custom order: SANDWICH first, then MANAGER, then FOH
    custom_order = ["SANDWICH", "MANAGER", "BARISTA", "WAITER"]
    orchestrator = Orchestrator(scheduler_order=custom_order)
    
    assignments = orchestrator.build_schedule(db_session, "2025-W48", sample_config)
    
    # Should still create valid schedule regardless of order
    assert len(assignments) >= 28
    
    # All roles should be covered
    roles_assigned = set(a.role for a in assignments)
    expected_roles = {"MANAGER", "BARISTA", "WAITER", "SANDWICH"}
    assert roles_assigned == expected_roles


"""Tests for ManagerScheduler."""

import datetime as dt
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.domain.models import Base, Employee, Shift
from scheduler.engine.manager import ManagerScheduler
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
def sample_managers(db_session):
    """Create sample manager employees."""
    managers = [
        Employee(
            employee_id=1001,
            first_name="Max",
            last_name="Hayes",
            primary_role="MANAGER",
        ),
        Employee(
            employee_id=1002,
            first_name="Mia",
            last_name="Stone",
            primary_role="MANAGER",
        ),
    ]
    db_session.add_all(managers)
    db_session.commit()
    return managers


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


def test_manager_scheduler_creates_assignments(db_session, sample_managers, sample_shifts, sample_config):
    """Test that ManagerScheduler creates valid assignments."""
    scheduler = ManagerScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Should create 9 assignments: 5 weekdays × 1 manager + 2 weekends × 2 managers
    assert len(assignments) == 9
    
    # Check all assignments have required fields
    for assign in assignments:
        assert assign.shift_id is not None
        assert assign.emp_id in [1001, 1002]
        assert assign.start_time is not None
        assert assign.end_time is not None
        assert assign.role == "MANAGER"


def test_manager_scheduler_respects_hours_caps(db_session, sample_managers, sample_shifts, sample_config):
    """Test that managers don't exceed their hard cap."""
    scheduler = ManagerScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Calculate hours per manager
    hours_per_manager = {}
    for assign in assignments:
        emp_id = assign.emp_id
        hours = (assign.end_time - assign.start_time).total_seconds() / 3600
        hours_per_manager[emp_id] = hours_per_manager.get(emp_id, 0.0) + hours
    
    # Check both managers are within 40h hard cap
    for emp_id, total_hours in hours_per_manager.items():
        assert total_hours <= 40.0, f"Manager {emp_id} exceeds 40h cap: {total_hours}h"


def test_manager_scheduler_weekend_coverage(db_session, sample_managers, sample_shifts, sample_config):
    """Test that weekends have 2 managers."""
    scheduler = ManagerScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Count managers per day
    managers_per_day = {}
    for assign in assignments:
        shift_date = assign.start_time.date()
        managers_per_day[shift_date] = managers_per_day.get(shift_date, 0) + 1
    
    # Check weekend coverage
    for shift in sample_shifts:
        day_name = dt.datetime.combine(shift.date, dt.time()).strftime('%A')
        is_weekend = day_name in ["Saturday", "Sunday"]
        
        expected = 2 if is_weekend else 1
        actual = managers_per_day.get(shift.date, 0)
        
        assert actual == expected, f"{shift.date} ({day_name}): expected {expected} managers, got {actual}"


def test_manager_scheduler_no_overlaps(db_session, sample_managers, sample_shifts, sample_config):
    """Test that no manager has overlapping assignments."""
    scheduler = ManagerScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Group by employee and date
    emp_assignments = {}
    for assign in assignments:
        key = (assign.emp_id, assign.start_time.date())
        if key not in emp_assignments:
            emp_assignments[key] = []
        emp_assignments[key].append(assign)
    
    # Check for overlaps
    for (emp_id, shift_date), day_assigns in emp_assignments.items():
        if len(day_assigns) > 1:
            # Check time overlaps
            for i, a1 in enumerate(day_assigns):
                for a2 in day_assigns[i+1:]:
                    assert not (a1.start_time < a2.end_time and a2.start_time < a1.end_time), \
                        f"Manager {emp_id} has overlapping shifts on {shift_date}"


def test_manager_scheduler_fails_with_no_managers(db_session, sample_shifts, sample_config):
    """Test that scheduler fails gracefully when no managers available."""
    # Don't add any managers
    scheduler = ManagerScheduler()
    
    with pytest.raises(RuntimeError, match="No managers available"):
        scheduler.make_schedule(db_session, "2025-W48", sample_config)


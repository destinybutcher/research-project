"""Tests for SandwichScheduler."""

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.domain.models import Base, Employee, Shift
from scheduler.engine.sandwich import SandwichScheduler
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
def sample_sandwich_staff(db_session):
    """Create sample sandwich employees."""
    staff = [
        Employee(
            employee_id=1007,
            first_name="Sam",
            last_name="Lee",
            primary_role="SANDWICH",
            skill_sandwich=5.0,
            skill_speed=3.0,
        ),
        Employee(
            employee_id=1008,
            first_name="Sara",
            last_name="Khan",
            primary_role="SANDWICH",
            skill_sandwich=4.0,
            skill_speed=4.0,
        ),
    ]
    db_session.add_all(staff)
    db_session.commit()
    return staff


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


def test_sandwich_scheduler_creates_assignments(db_session, sample_sandwich_staff, sample_shifts, sample_config):
    """Test that SandwichScheduler creates valid assignments."""
    scheduler = SandwichScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Should create 7 assignments (1 per day)
    assert len(assignments) == 7
    
    # Check all assignments have required fields
    for assign in assignments:
        assert assign.shift_id is not None
        assert assign.emp_id in [1007, 1008]
        assert assign.start_time is not None
        assert assign.end_time is not None
        assert assign.role == "SANDWICH"


def test_sandwich_scheduler_early_morning_shifts(db_session, sample_sandwich_staff, sample_shifts, sample_config):
    """Test that SANDWICH shifts start early (before café hours)."""
    scheduler = SandwichScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Check that some shifts start before 07:00 (café opening)
    early_shifts = [a for a in assignments if a.start_time.hour < 7]
    assert len(early_shifts) > 0, "SANDWICH shifts should include early morning prep"
    
    # Check that early shifts start at 05:00 or 06:00
    for assign in early_shifts:
        assert assign.start_time.hour in [5, 6], f"Early shift starts at unexpected hour: {assign.start_time.hour}"


def test_sandwich_scheduler_respects_hours_caps(db_session, sample_sandwich_staff, sample_shifts, sample_config):
    """Test that sandwich staff don't exceed their hard cap."""
    scheduler = SandwichScheduler()
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Calculate hours per employee
    hours_per_emp = {}
    for assign in assignments:
        emp_id = assign.emp_id
        hours = (assign.end_time - assign.start_time).total_seconds() / 3600
        hours_per_emp[emp_id] = hours_per_emp.get(emp_id, 0.0) + hours
    
    # Check all are within 36h hard cap (SANDWICH policy)
    for emp_id, total_hours in hours_per_emp.items():
        assert total_hours <= 36.0, f"SANDWICH {emp_id} exceeds 36h cap: {total_hours}h"


def test_sandwich_scheduler_no_overlaps(db_session, sample_sandwich_staff, sample_shifts, sample_config):
    """Test that no sandwich staff has overlapping assignments."""
    scheduler = SandwichScheduler()
    
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
                    overlap = a1.start_time < a2.end_time and a2.start_time < a1.end_time
                    assert not overlap, f"SANDWICH {emp_id} has overlapping shifts on {shift_date}"


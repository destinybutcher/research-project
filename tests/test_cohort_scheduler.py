"""Tests for CohortScheduler (BARISTA and WAITER)."""

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.domain.models import Base, Employee, Shift
from scheduler.engine.cohort import CohortScheduler
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
def sample_baristas(db_session):
    """Create sample barista employees."""
    baristas = [
        Employee(
            employee_id=1005,
            first_name="Bella",
            last_name="Tran",
            primary_role="BARISTA",
            skill_coffee=3.0,
            skill_speed=3.0,
            customer_service_rating=3.0,
        ),
        Employee(
            employee_id=1006,
            first_name="Ben",
            last_name="Park",
            primary_role="BARISTA",
            skill_coffee=4.0,
            skill_speed=4.0,
            customer_service_rating=4.0,
        ),
    ]
    db_session.add_all(baristas)
    db_session.commit()
    return baristas


@pytest.fixture
def sample_waiters(db_session):
    """Create sample waiter employees."""
    waiters = [
        Employee(
            employee_id=1003,
            first_name="Wendy",
            last_name="Ng",
            primary_role="WAITER",
            customer_service_rating=5.0,
            skill_speed=3.0,
        ),
        Employee(
            employee_id=1004,
            first_name="Will",
            last_name="Brown",
            primary_role="WAITER",
            customer_service_rating=4.0,
            skill_speed=4.0,
        ),
    ]
    db_session.add_all(waiters)
    db_session.commit()
    return waiters


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


def test_barista_scheduler_creates_assignments(db_session, sample_baristas, sample_shifts, sample_config):
    """Test that BARISTA scheduler creates valid assignments."""
    scheduler = CohortScheduler("BARISTA")
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Should create assignments based on requirements (5 weekdays + 2 weekends with config)
    assert len(assignments) >= 7
    
    # Check all assignments have required fields
    for assign in assignments:
        assert assign.shift_id is not None
        assert assign.emp_id in [1005, 1006]
        assert assign.start_time is not None
        assert assign.end_time is not None
        assert assign.role == "BARISTA"


def test_waiter_scheduler_creates_assignments(db_session, sample_waiters, sample_shifts, sample_config):
    """Test that WAITER scheduler creates valid assignments."""
    scheduler = CohortScheduler("WAITER")
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Should create assignments based on requirements
    assert len(assignments) >= 7
    
    # Check all assignments have required fields
    for assign in assignments:
        assert assign.shift_id is not None
        assert assign.emp_id in [1003, 1004]
        assert assign.start_time is not None
        assert assign.end_time is not None
        assert assign.role == "WAITER"


def test_cohort_scheduler_respects_hours_caps(db_session, sample_baristas, sample_shifts, sample_config):
    """Test that cohort members don't exceed their hard cap."""
    scheduler = CohortScheduler("BARISTA")
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Calculate hours per employee
    hours_per_emp = {}
    for assign in assignments:
        emp_id = assign.emp_id
        hours = (assign.end_time - assign.start_time).total_seconds() / 3600
        hours_per_emp[emp_id] = hours_per_emp.get(emp_id, 0.0) + hours
    
    # Check all are within 40h hard cap
    for emp_id, total_hours in hours_per_emp.items():
        assert total_hours <= 40.0, f"BARISTA {emp_id} exceeds 40h cap: {total_hours}h"


def test_cohort_scheduler_rejects_invalid_role(db_session):
    """Test that CohortScheduler only accepts BARISTA or WAITER."""
    with pytest.raises(ValueError, match="only handles BARISTA and WAITER"):
        CohortScheduler("MANAGER")
    
    with pytest.raises(ValueError, match="only handles BARISTA and WAITER"):
        CohortScheduler("SANDWICH")


def test_cohort_scheduler_cafe_hours(db_session, sample_baristas, sample_shifts, sample_config):
    """Test that BARISTA/WAITER shifts are within café hours (07:00-15:00)."""
    scheduler = CohortScheduler("BARISTA")
    
    assignments = scheduler.make_schedule(db_session, "2025-W48", sample_config)
    
    # Check all shifts are within café hours
    for assign in assignments:
        start_hour = assign.start_time.hour
        end_hour = assign.end_time.hour
        
        assert start_hour >= 7, f"Shift starts before café hours: {assign.start_time}"
        assert end_hour <= 15, f"Shift ends after café hours: {assign.end_time}"


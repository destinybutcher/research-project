"""Tests for CSV import/export functionality."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scheduler.domain.models import Base, Employee, Shift
from scheduler.domain.repositories import EmployeeRepository, ShiftRepository
from scheduler.io.export_csv import export_employees_csv
from scheduler.io.import_csv import import_employees_csv, import_shifts_csv


@pytest.fixture
def db_session():
    """Create in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_import_employees_csv(db_session, tmp_path):
    """Test importing employees from CSV."""
    # Create temporary CSV
    csv_content = """employee_id,first_name,last_name,primary_role,skill_coffee,skill_sandwich,customer_service_rating,skill_speed
1001,Max,Hayes,MANAGER,,,,
1002,Mia,Stone,MANAGER,,,,
1003,Ben,Park,BARISTA,4.0,,4.0,4.0
"""
    csv_file = tmp_path / "employees.csv"
    csv_file.write_text(csv_content)
    
    # Import
    count = import_employees_csv(db_session, csv_file)
    assert count == 3
    
    # Verify in database
    employees = EmployeeRepository.get_all(db_session)
    assert len(employees) == 3
    
    # Check manager
    manager = EmployeeRepository.get_by_id(db_session, 1001)
    assert manager.first_name == "Max"
    assert manager.primary_role == "MANAGER"
    
    # Check barista
    barista = EmployeeRepository.get_by_id(db_session, 1003)
    assert barista.skill_coffee == 4.0
    assert barista.primary_role == "BARISTA"


def test_import_shifts_csv(db_session, tmp_path):
    """Test importing shifts from CSV."""
    # Create temporary CSV
    csv_content = """id,date,week_id
1000,2025-09-01,2025-W36
1001,2025-09-02,2025-W36
1002,2025-09-03,2025-W36
"""
    csv_file = tmp_path / "shifts.csv"
    csv_file.write_text(csv_content)
    
    # Import
    count = import_shifts_csv(db_session, csv_file, week_id="2025-W36")
    assert count == 3
    
    # Verify in database
    shifts = ShiftRepository.get_by_week(db_session, "2025-W36")
    assert len(shifts) == 3
    
    # Check first shift
    shift = ShiftRepository.get_by_id(db_session, 1000)
    assert str(shift.date) == "2025-09-01"
    assert shift.week_id == "2025-W36"


def test_export_employees_csv(db_session, tmp_path):
    """Test exporting employees to CSV."""
    # Add employees to database
    employees = [
        Employee(employee_id=1001, first_name="Max", last_name="Hayes", primary_role="MANAGER"),
        Employee(employee_id=1002, first_name="Mia", last_name="Stone", primary_role="MANAGER"),
    ]
    db_session.add_all(employees)
    db_session.commit()
    
    # Export
    csv_file = tmp_path / "employees_export.csv"
    count = export_employees_csv(db_session, csv_file)
    assert count == 2
    
    # Verify CSV was created
    assert csv_file.exists()
    
    # Read back and verify content
    import pandas as pd
    df = pd.read_csv(csv_file)
    assert len(df) == 2
    assert list(df['employee_id']) == [1001, 1002]
    assert list(df['primary_role']) == ['MANAGER', 'MANAGER']


def test_import_csv_week_filter(db_session, tmp_path):
    """Test that import can filter by week_id."""
    # Create CSV with multiple weeks
    csv_content = """id,date,week_id
1000,2025-09-01,2025-W36
1001,2025-09-02,2025-W36
2000,2025-11-24,2025-W48
2001,2025-11-25,2025-W48
"""
    csv_file = tmp_path / "shifts.csv"
    csv_file.write_text(csv_content)
    
    # Import only W36
    count = import_shifts_csv(db_session, csv_file, week_id="2025-W36")
    assert count == 2
    
    # Verify only W36 in database
    shifts = ShiftRepository.get_by_week(db_session, "2025-W36")
    assert len(shifts) == 2
    
    shifts_w48 = ShiftRepository.get_by_week(db_session, "2025-W48")
    assert len(shifts_w48) == 0


"""CSV import utilities to load data into database."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from scheduler.domain.models import Employee, Feedback, Shift


def import_employees_csv(session: Session, csv_path: str | Path) -> int:
    """
    Import employees from CSV into database.
    
    Args:
        session: Database session
        csv_path: Path to employees CSV
    
    Returns:
        Number of employees imported
    """
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Normalize role to uppercase
    if 'primary_role' in df.columns:
        df['primary_role'] = df['primary_role'].str.upper()
    
    # Create Employee objects
    employees = []
    for _, row in df.iterrows():
        emp = Employee(
            employee_id=int(row['employee_id']),
            first_name=str(row['first_name']),
            last_name=str(row['last_name']),
            primary_role=str(row['primary_role']),
            skill_coffee=float(row['skill_coffee']) if pd.notna(row.get('skill_coffee')) else None,
            skill_sandwich=float(row['skill_sandwich']) if pd.notna(row.get('skill_sandwich')) else None,
            customer_service_rating=float(row['customer_service_rating']) if pd.notna(row.get('customer_service_rating')) else None,
            skill_speed=float(row['skill_speed']) if pd.notna(row.get('skill_speed')) else None,
        )
        employees.append(emp)
    
    # Bulk insert
    session.add_all(employees)
    session.commit()
    
    print(f"[INFO] Imported {len(employees)} employees from {csv_path}")
    return len(employees)


def import_shifts_csv(session: Session, csv_path: str | Path, week_id: str | None = None) -> int:
    """
    Import shifts from CSV into database.
    
    Args:
        session: Database session
        csv_path: Path to shifts CSV
        week_id: Optional week_id to filter (e.g., "2025-W36")
    
    Returns:
        Number of shifts imported
    """
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    df.rename(columns={'id': 'shift_id'}, inplace=True)
    
    # Filter by week if specified
    if week_id is not None and 'week_id' in df.columns:
        df = df[df['week_id'] == week_id].copy()
    
    # Convert date
    df['date'] = pd.to_datetime(df['date']).dt.date
    
    # Create Shift objects
    shifts = []
    for _, row in df.iterrows():
        shift = Shift(
            shift_id=int(row['shift_id']),
            date=row['date'],
            week_id=str(row['week_id']),
        )
        shifts.append(shift)
    
    # Bulk insert
    session.add_all(shifts)
    session.commit()
    
    print(f"[INFO] Imported {len(shifts)} shifts from {csv_path}")
    return len(shifts)


def import_feedback_csv(session: Session, csv_path: str | Path, week_id: str | None = None) -> int:
    """
    Import feedback from CSV into database.
    
    Args:
        session: Database session
        csv_path: Path to feedback CSV
        week_id: Optional week_id to filter
    
    Returns:
        Number of feedback records imported
    """
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Filter by week if specified
    if week_id is not None and 'week_id' in df.columns:
        df = df[df['week_id'] == week_id].copy()
    
    # Convert dates
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
    if 'submitted_at' in df.columns:
        df['submitted_at'] = pd.to_datetime(df['submitted_at'])
    
    # Normalize role
    if 'role' in df.columns:
        df['role'] = df['role'].str.upper()
    
    # Deduplicate: keep latest by submitted_at
    if 'submitted_at' in df.columns:
        df = df.sort_values('submitted_at')
    df = df.drop_duplicates(subset=['shift_id', 'emp_id'], keep='last')
    
    # Create Feedback objects
    feedbacks = []
    for _, row in df.iterrows():
        feedback = Feedback(
            week_id=str(row['week_id']),
            date=row['date'],
            shift_id=int(row['shift_id']),
            emp_id=int(row['emp_id']),
            role=str(row['role']),
            present=bool(str(row.get('present', 'TRUE')).upper() in ['TRUE', 'T', '1', 'YES']),
            overall_service_rating=int(row['overall_service_rating']),
            traffic_level=str(row.get('traffic_level', 'normal')).lower(),
            comment=str(row.get('comment', '')) if pd.notna(row.get('comment')) else None,
            tags=str(row.get('tags', '')) if pd.notna(row.get('tags')) else None,
            submitted_at=row.get('submitted_at', pd.Timestamp.now()),
        )
        feedbacks.append(feedback)
    
    # Bulk insert
    session.add_all(feedbacks)
    session.commit()
    
    print(f"[INFO] Imported {len(feedbacks)} feedback records from {csv_path}")
    return len(feedbacks)


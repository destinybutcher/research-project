"""Repository classes for data access."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Assignment, Base, Employee, Feedback, Shift


class DatabaseManager:
    """Manages database connection and session factory."""
    
    def __init__(self, db_url: str = "sqlite:///scheduler.db"):
        """
        Initialize database manager.
        
        Args:
            db_url: SQLAlchemy database URL (default: sqlite:///scheduler.db)
        """
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)
    
    def drop_tables(self):
        """Drop all tables (use with caution!)."""
        Base.metadata.drop_all(self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()


class EmployeeRepository:
    """Repository for employee data access."""
    
    @staticmethod
    def get_all(session: Session) -> List[Employee]:
        """Get all employees."""
        return session.query(Employee).all()
    
    @staticmethod
    def get_by_id(session: Session, employee_id: int) -> Optional[Employee]:
        """Get employee by ID."""
        return session.query(Employee).filter(Employee.employee_id == employee_id).first()
    
    @staticmethod
    def get_by_role(session: Session, role: str) -> List[Employee]:
        """Get all employees with a specific role."""
        return session.query(Employee).filter(Employee.primary_role == role.upper()).all()
    
    @staticmethod
    def create(session: Session, employee: Employee) -> Employee:
        """Create a new employee."""
        session.add(employee)
        session.commit()
        session.refresh(employee)
        return employee
    
    @staticmethod
    def update(session: Session, employee: Employee) -> Employee:
        """Update an existing employee."""
        session.merge(employee)
        session.commit()
        return employee
    
    @staticmethod
    def bulk_create(session: Session, employees: List[Employee]) -> None:
        """Create multiple employees."""
        session.add_all(employees)
        session.commit()


class ShiftRepository:
    """Repository for shift data access."""
    
    @staticmethod
    def get_all(session: Session) -> List[Shift]:
        """Get all shifts."""
        return session.query(Shift).all()
    
    @staticmethod
    def get_by_week(session: Session, week_id: str) -> List[Shift]:
        """Get all shifts for a specific week."""
        return session.query(Shift).filter(Shift.week_id == week_id).order_by(Shift.date).all()
    
    @staticmethod
    def get_by_id(session: Session, shift_id: int) -> Optional[Shift]:
        """Get shift by ID."""
        return session.query(Shift).filter(Shift.shift_id == shift_id).first()
    
    @staticmethod
    def create(session: Session, shift: Shift) -> Shift:
        """Create a new shift."""
        session.add(shift)
        session.commit()
        session.refresh(shift)
        return shift
    
    @staticmethod
    def bulk_create(session: Session, shifts: List[Shift]) -> None:
        """Create multiple shifts."""
        session.add_all(shifts)
        session.commit()


class AssignmentRepository:
    """Repository for assignment data access."""
    
    @staticmethod
    def get_all(session: Session) -> List[Assignment]:
        """Get all assignments."""
        return session.query(Assignment).all()
    
    @staticmethod
    def get_by_week(session: Session, week_id: str) -> List[Assignment]:
        """Get all assignments for a specific week."""
        return (
            session.query(Assignment)
            .join(Shift)
            .filter(Shift.week_id == week_id)
            .all()
        )
    
    @staticmethod
    def get_by_employee(session: Session, emp_id: int) -> List[Assignment]:
        """Get all assignments for a specific employee."""
        return session.query(Assignment).filter(Assignment.emp_id == emp_id).all()
    
    @staticmethod
    def create(session: Session, assignment: Assignment) -> Assignment:
        """Create a new assignment."""
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
        return assignment
    
    @staticmethod
    def bulk_create(session: Session, assignments: List[Assignment]) -> None:
        """Create multiple assignments."""
        session.add_all(assignments)
        session.commit()
    
    @staticmethod
    def delete_by_week(session: Session, week_id: str) -> int:
        """Delete all assignments for a specific week. Returns number of deleted rows."""
        # Get shift IDs for this week
        shifts = session.query(Shift).filter(Shift.week_id == week_id).all()
        shift_ids = [shift.shift_id for shift in shifts]
        
        if not shift_ids:
            return 0
        
        # Delete assignments for these shifts
        count = (
            session.query(Assignment)
            .filter(Assignment.shift_id.in_(shift_ids))
            .delete(synchronize_session=False)
        )
        session.commit()
        return count


class FeedbackRepository:
    """Repository for feedback data access."""
    
    @staticmethod
    def get_all(session: Session) -> List[Feedback]:
        """Get all feedback."""
        return session.query(Feedback).all()
    
    @staticmethod
    def get_by_week(session: Session, week_id: str) -> List[Feedback]:
        """Get all feedback for a specific week."""
        return session.query(Feedback).filter(Feedback.week_id == week_id).all()
    
    @staticmethod
    def get_by_employee(session: Session, emp_id: int) -> List[Feedback]:
        """Get all feedback for a specific employee."""
        return session.query(Feedback).filter(Feedback.emp_id == emp_id).order_by(Feedback.submitted_at).all()
    
    @staticmethod
    def create(session: Session, feedback: Feedback) -> Feedback:
        """Create a new feedback record."""
        session.add(feedback)
        session.commit()
        session.refresh(feedback)
        return feedback
    
    @staticmethod
    def bulk_create(session: Session, feedbacks: List[Feedback]) -> None:
        """Create multiple feedback records."""
        session.add_all(feedbacks)
        session.commit()


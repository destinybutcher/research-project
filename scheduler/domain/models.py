"""SQLAlchemy models for café scheduling system."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Employee(Base):
    """Employee model with skills and role information."""
    
    __tablename__ = "employees"
    
    employee_id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    primary_role = Column(String(20), nullable=False)  # MANAGER, BARISTA, WAITER, SANDWICH
    
    # Skills (0-10 scale, nullable for roles that don't use them)
    skill_coffee = Column(Float, nullable=True)
    skill_sandwich = Column(Float, nullable=True)
    customer_service_rating = Column(Float, nullable=True)
    skill_speed = Column(Float, nullable=True)
    
    # Relationships
    assignments = relationship("Assignment", back_populates="employee")
    feedback = relationship("Feedback", back_populates="employee")
    
    def __repr__(self) -> str:
        return f"<Employee(id={self.employee_id}, name='{self.first_name} {self.last_name}', role='{self.primary_role}')>"


class Shift(Base):
    """Shift model representing a single day's work period."""
    
    __tablename__ = "shifts"
    
    shift_id = Column(Integer, primary_key=True, name="id")
    date = Column(Date, nullable=False)
    week_id = Column(String(10), nullable=False)  # ISO week format: 2025-W36
    
    # Relationships
    assignments = relationship("Assignment", back_populates="shift")
    feedback = relationship("Feedback", back_populates="shift")
    
    def __repr__(self) -> str:
        return f"<Shift(id={self.shift_id}, date={self.date}, week={self.week_id})>"


class Assignment(Base):
    """Assignment linking an employee to a shift with specific times."""
    
    __tablename__ = "assignments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    emp_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    start_time = Column(DateTime, nullable=False)  # Timezone-aware
    end_time = Column(DateTime, nullable=False)  # Timezone-aware
    role = Column(String(20), nullable=True)  # Role this assignment is for
    shift_type = Column(String(50), nullable=True)  # e.g., "weekday", "weekend_staggered"
    day_type = Column(String(20), nullable=True)  # e.g., "weekday", "weekend"
    
    # Relationships
    shift = relationship("Shift", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")
    
    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, shift={self.shift_id}, emp={self.emp_id}, role={self.role})>"


class Feedback(Base):
    """Manager feedback for post-shift performance evaluation."""
    
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week_id = Column(String(10), nullable=False)
    date = Column(Date, nullable=False)
    shift_id = Column(Integer, ForeignKey("shifts.id"), nullable=False)
    emp_id = Column(Integer, ForeignKey("employees.employee_id"), nullable=False)
    role = Column(String(20), nullable=False)
    
    # Feedback fields
    present = Column(Boolean, nullable=False, default=True)
    overall_service_rating = Column(Integer, nullable=False)  # 1-5 scale
    traffic_level = Column(String(20), nullable=False, default="normal")  # quiet, normal, busy
    comment = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)  # Semicolon-separated keywords
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    shift = relationship("Shift", back_populates="feedback")
    employee = relationship("Employee", back_populates="feedback")
    
    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, emp={self.emp_id}, rating={self.overall_service_rating}, traffic={self.traffic_level})>"


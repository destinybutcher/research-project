"""Tests for service layer (constraints, scoring, timeplan)."""

import datetime as dt
from datetime import date

import pytest

from scheduler.domain.models import Employee
from scheduler.services.constraints import can_assign_employee, calculate_hours_deviation_penalty
from scheduler.services.scoring import calculate_employee_score, calculate_fairness_penalty, calculate_role_fitness
from scheduler.services.timeplan import calculate_shift_hours, get_time_window_for_role, parse_time_string


def test_parse_time_string():
    """Test time string parsing."""
    t = parse_time_string("07:30")
    assert t.hour == 7
    assert t.minute == 30


def test_calculate_shift_hours():
    """Test shift duration calculation."""
    hours = calculate_shift_hours("07:00", "15:00")
    assert hours == 8.0
    
    hours = calculate_shift_hours("05:00", "12:00")
    assert hours == 7.0


def test_can_assign_employee_role_eligibility():
    """Test that employees must match the required role."""
    barista = Employee(employee_id=1, first_name="Test", last_name="User", primary_role="BARISTA")
    
    # Can assign to BARISTA role
    result = can_assign_employee(
        barista, "BARISTA", date(2025, 1, 1), 8.0, set(), {}, {}, 40.0
    )
    assert result is True
    
    # Cannot assign to MANAGER role
    result = can_assign_employee(
        barista, "MANAGER", date(2025, 1, 1), 8.0, set(), {}, {}, 40.0
    )
    assert result is False


def test_can_assign_employee_already_assigned_today():
    """Test that employee cannot be assigned twice on same day."""
    barista = Employee(employee_id=1, first_name="Test", last_name="User", primary_role="BARISTA")
    
    # First assignment: OK
    assigned_today = set()
    result = can_assign_employee(
        barista, "BARISTA", date(2025, 1, 1), 8.0, assigned_today, {}, {}, 40.0
    )
    assert result is True
    
    # Second assignment same day: NOT OK
    assigned_today = {1}
    result = can_assign_employee(
        barista, "BARISTA", date(2025, 1, 1), 8.0, assigned_today, {}, {}, 40.0
    )
    assert result is False


def test_can_assign_employee_hours_cap():
    """Test that employee cannot exceed weekly hours cap."""
    barista = Employee(employee_id=1, first_name="Test", last_name="User", primary_role="BARISTA")
    
    # Already worked 35 hours, trying to add 8 more (total 43 > 40 cap)
    weekly_hours = {1: 35.0}
    hours_policy = {'BARISTA': {'hard_cap': 40.0}}
    
    result = can_assign_employee(
        barista, "BARISTA", date(2025, 1, 1), 8.0, set(), weekly_hours, hours_policy, 40.0
    )
    assert result is False
    
    # With only 30 hours, can add 8 more (total 38 < 40)
    weekly_hours = {1: 30.0}
    result = can_assign_employee(
        barista, "BARISTA", date(2025, 1, 1), 8.0, set(), weekly_hours, hours_policy, 40.0
    )
    assert result is True


def test_calculate_role_fitness_barista():
    """Test role fitness calculation for BARISTA."""
    barista = Employee(
        employee_id=1,
        first_name="Test",
        last_name="User",
        primary_role="BARISTA",
        skill_coffee=4.0,
        skill_speed=3.0,
        customer_service_rating=5.0,
    )
    
    weights = {'coffee': 1.0, 'speed': 0.5, 'customer_service': 0.5}
    fitness = calculate_role_fitness(barista, "BARISTA", weights)
    
    # Expected: 1.0*4.0 + 0.5*3.0 + 0.5*5.0 = 4.0 + 1.5 + 2.5 = 8.0
    assert fitness == 8.0


def test_calculate_fairness_penalty():
    """Test fairness penalty calculation."""
    # Cohort: [10h, 20h, 30h] → median = 20h
    cohort_hours = {1: 10.0, 2: 20.0, 3: 30.0}
    
    # Employee with 20h (at median): no penalty
    penalty = calculate_fairness_penalty(2, 20.0, cohort_hours, penalty_per_std=0.25)
    assert penalty == 0.0
    
    # Employee with 10h (below median): no penalty
    penalty = calculate_fairness_penalty(1, 10.0, cohort_hours, penalty_per_std=0.25)
    assert penalty == 0.0
    
    # Employee with 30h (above median): penalty > 0
    penalty = calculate_fairness_penalty(3, 30.0, cohort_hours, penalty_per_std=0.25)
    assert penalty > 0.0


def test_calculate_employee_score():
    """Test complete employee scoring."""
    barista = Employee(
        employee_id=1,
        first_name="Test",
        last_name="User",
        primary_role="BARISTA",
        skill_coffee=4.0,
        skill_speed=3.0,
        customer_service_rating=5.0,
    )
    
    cohort_hours = {1: 20.0, 2: 20.0}  # Balanced cohort
    weights = {'coffee': 1.0, 'speed': 0.5, 'customer_service': 0.5}
    hours_policy = {'BARISTA': {'target_min': 16, 'target_max': 40, 'hard_cap': 40}}
    hours_penalties = {'per_hour_below_target': 0.5, 'per_hour_above_target': 0.75}
    
    score = calculate_employee_score(
        barista, "BARISTA", 20.0, cohort_hours, weights, hours_policy, hours_penalties
    )
    
    # Should be positive (fitness - minimal penalties)
    assert score > 0.0


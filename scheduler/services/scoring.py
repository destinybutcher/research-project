"""Scoring functions for employee fitness and fairness."""

from __future__ import annotations

from typing import Dict

from scheduler.domain.models import Employee


def calculate_employee_score(
    employee: Employee,
    role: str,
    current_hours: float,
    role_cohort_hours: Dict[int, float],
    weights: Dict[str, float],
    hours_policy: Dict,
    hours_penalties: Dict[str, float],
) -> float:
    """
    Calculate overall score for assigning an employee to a role.
    
    Higher score = better candidate.
    
    Args:
        employee: Employee to score
        role: Role to assign
        current_hours: Employee's current weekly hours
        role_cohort_hours: Hours for all employees in this role {emp_id: hours}
        weights: Scoring weights from config
        hours_policy: Role-based hours policy
        hours_penalties: Penalties for deviation from target hours
    
    Returns:
        Overall score (higher is better)
    """
    # 1. Base fitness from skills
    fitness = calculate_role_fitness(employee, role, weights)
    
    # 2. Fairness penalty (prefer employees with fewer hours in their cohort)
    fairness_penalty = calculate_fairness_penalty(
        employee.employee_id,
        current_hours,
        role_cohort_hours,
        weights.get('fairness_penalty_per_std_above_median', 0.25)
    )
    
    # 3. Hours deviation penalty (prefer keeping within target range)
    hours_penalty = calculate_hours_deviation_penalty(
        current_hours,
        role,
        hours_policy,
        hours_penalties
    )
    
    return fitness - fairness_penalty - hours_penalty


def calculate_role_fitness(employee: Employee, role: str, weights: Dict[str, float]) -> float:
    """
    Calculate skill-based fitness for a role.
    
    Args:
        employee: Employee to score
        role: Role to assign
        weights: Skill weights from config
    
    Returns:
        Weighted sum of relevant skills
    """
    role = role.upper()
    
    if role == "MANAGER":
        return weights.get('manager_weight', 1.0)
    
    elif role == "BARISTA":
        coffee = employee.skill_coffee or 0.0
        speed = employee.skill_speed or 0.0
        cs = employee.customer_service_rating or 0.0
        
        return (
            weights.get('coffee', 1.0) * coffee +
            weights.get('speed', 0.5) * speed +
            weights.get('customer_service', 0.5) * cs
        )
    
    elif role == "WAITER":
        cs = employee.customer_service_rating or 0.0
        speed = employee.skill_speed or 0.0
        
        return (
            weights.get('customer_service', 0.5) * cs +
            weights.get('speed', 0.5) * speed
        )
    
    elif role == "SANDWICH":
        sandwich = employee.skill_sandwich or 0.0
        return weights.get('sandwich', 1.0) * sandwich
    
    return 0.0


def calculate_fairness_penalty(
    emp_id: int,
    current_hours: float,
    cohort_hours: Dict[int, float],
    penalty_per_std: float = 0.25,
) -> float:
    """
    Calculate fairness penalty based on hours distribution within role cohort.
    
    Strongly penalizes employees who have more hours than others in their cohort.
    
    Args:
        emp_id: Employee ID
        current_hours: Current weekly hours for this employee
        cohort_hours: Hours for all employees in the same role
        penalty_per_std: Penalty weight (higher = more aggressive fairness)
    
    Returns:
        Penalty value (higher = less preferred)
    """
    if not cohort_hours or len(cohort_hours) <= 1:
        return 0.0
    
    # Simple approach: penalize based on difference from minimum hours in cohort
    min_hours = min(cohort_hours.values())
    
    if current_hours <= min_hours:
        return 0.0
    
    # Strong penalty for having more hours than the least-worked person
    # This ensures rotation between employees
    hours_above_min = current_hours - min_hours
    return penalty_per_std * hours_above_min


def calculate_hours_deviation_penalty(
    current_hours: float,
    role: str,
    hours_policy: Dict,
    hours_penalties: Dict[str, float],
) -> float:
    """
    Calculate penalty for deviation from target hours range.
    
    Args:
        current_hours: Current weekly hours
        role: Employee role
        hours_policy: Role-based hours policy
        hours_penalties: Penalty rates for below/above target
    
    Returns:
        Penalty value (higher = less preferred)
    """
    role_policy = hours_policy.get(role.upper(), {})
    target_min = role_policy.get('target_min', 0)
    target_max = role_policy.get('target_max', 40)
    
    if current_hours < target_min:
        # Below target: penalize
        deficit = target_min - current_hours
        return deficit * hours_penalties.get('per_hour_below_target', 0.5)
    
    elif current_hours > target_max:
        # Above target: penalize
        excess = current_hours - target_max
        return excess * hours_penalties.get('per_hour_above_target', 0.75)
    
    # Within target range: no penalty
    return 0.0


from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class RoleWeights:
    manager_weight: float
    coffee: float
    sandwich: float
    speed: float
    customer_service: float
    fairness_penalty_per_std_above_median: float


def role_fitness(row: pd.Series, role: str, w: RoleWeights) -> float:
    role = role.upper()
    if role == "MANAGER":
        return w.manager_weight
    if role == "BARISTA":
        return (
            w.coffee * float(row.get("skill_coffee", 0))
            + w.speed * float(row.get("skill_speed", 0))
            + w.customer_service * float(row.get("customer_service_rating", 0))
        )
    if role == "WAITER":
        return (
            w.customer_service * float(row.get("customer_service_rating", 0))
            + w.speed * float(row.get("skill_speed", 0))
        )
    if role == "SANDWICH":
        return w.sandwich * float(row.get("skill_sandwich", 0))
    return 0.0


def fairness_penalty(hours_series: pd.Series, role: str, w: RoleWeights) -> Dict[int, float]:
    # Compute penalty per employee for being above median in their role cohort
    if hours_series.empty:
        return {}
    median = hours_series.median()
    std = hours_series.std(ddof=0)
    penalties: Dict[int, float] = {}
    if std == 0:
        return {int(emp): 0.0 for emp in hours_series.index}
    for emp_id, hrs in hours_series.items():
        z = max(0.0, (hrs - median) / std)
        penalties[int(emp_id)] = z * w.fairness_penalty_per_std_above_median
    return penalties


def hours_deviation_penalty(
    current_hours: float,
    role: str,
    hours_policy: Dict[str, Dict[str, float]],
    hours_penalties: Dict[str, float],
) -> float:
    pol = hours_policy.get(role)
    if not pol:
        return 0.0
    tmin = float(pol.get("target_min", 0))
    tmax = float(pol.get("target_max", 1e9))
    below = max(0.0, tmin - current_hours)
    above = max(0.0, current_hours - tmax)
    return (
        below * float(hours_penalties.get("per_hour_below_target", 0.0))
        + above * float(hours_penalties.get("per_hour_above_target", 0.0))
    )



"""Daily requirements calculation."""

from __future__ import annotations

from typing import Dict

import pandas as pd


def build_requirements_for_day(date_str: str, cfg) -> Dict[str, int]:
    """
    Build role requirements for a specific day.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        cfg: SchedulerConfig with default_requirements, weekend_requirements, overrides
    
    Returns:
        Dict of role -> count required for this day
    """
    req = dict(cfg.default_requirements)
    
    # Check if it's a weekend (Saturday or Sunday)
    day_name = pd.Timestamp(date_str).day_name()
    if day_name in ["Saturday", "Sunday"]:
        # Use weekend requirements
        weekend_reqs = getattr(cfg, 'weekend_requirements', {})
        for role, count in weekend_reqs.items():
            req[role] = count
    
    # Apply date-specific overrides (takes precedence)
    if date_str in cfg.overrides:
        for role, count in cfg.overrides[date_str].items():
            req[role] = count
    
    return req


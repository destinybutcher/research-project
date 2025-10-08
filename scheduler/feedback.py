from __future__ import annotations

import pandas as pd


def apply_post_shift_feedback(assignments_df: pd.DataFrame, feedback_df: pd.DataFrame, employees_df: pd.DataFrame, weights: dict):
    """
    Later: update per-employee skill estimates using post-shift ratings:
    - coffee_rating, sandwich_rating, customer_service_rating, speed_rating
    Approach: exponential moving average or Bayesian update.
    """
    raise NotImplementedError


def learn_weight_adjustments(history_df: pd.DataFrame):
    """
    Later: adjust global weights (coffee/sandwich/speed/CS) based on outcomes.
    """
    raise NotImplementedError



from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable

import pandas as pd


ROLES = {"MANAGER", "BARISTA", "WAITER", "SANDWICH"}


def is_role_eligible(primary_role: str, required_role: str) -> bool:
    primary_role = primary_role.upper()
    required_role = required_role.upper()
    if required_role not in ROLES:
        return False
    if primary_role == "SANDWICH":
        return required_role == "SANDWICH"
    if primary_role == "BARISTA":
        return required_role == "BARISTA"
    if primary_role == "WAITER":
        return required_role == "WAITER"
    if primary_role == "MANAGER":
        return required_role == "MANAGER"
    return False


def has_overlap(assignments_df: pd.DataFrame) -> bool:
    # Check overlaps per employee per date
    if assignments_df.empty:
        return False
    df = assignments_df.copy()
    df["start_time"] = pd.to_datetime(df["start_time"])  # timezone-aware
    df["end_time"] = pd.to_datetime(df["end_time"])  # timezone-aware
    df["date"] = df["start_time"].dt.tz_convert(None).dt.date
    df.sort_values(["emp_id", "date", "start_time"], inplace=True)
    def _overlap(group: pd.DataFrame) -> bool:
        prev_end = None
        for _, row in group.iterrows():
            if prev_end is not None and row["start_time"] < prev_end:
                return True
            prev_end = row["end_time"]
        return False
    return df.groupby(["emp_id", "date"]).apply(_overlap).any()


def within_cafe_hours(assignments_df: pd.DataFrame, start_hm: str, end_hm: str) -> bool:
    if assignments_df.empty:
        return True
    start_h, start_m = [int(x) for x in start_hm.split(":")]
    end_h, end_m = [int(x) for x in end_hm.split(":")]
    df = assignments_df.copy()
    df["start_time"] = pd.to_datetime(df["start_time"]).dt.tz_convert(None)
    df["end_time"] = pd.to_datetime(df["end_time"]).dt.tz_convert(None)
    return (
        (df["start_time"].dt.hour >= start_h)
        & (df["start_time"].dt.minute >= start_m)
        & (df["end_time"].dt.hour <= end_h)
        & (df["end_time"].dt.minute == 0)
    ).all()



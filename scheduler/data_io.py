from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Tuple

import pandas as pd


def read_employees(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize columns
    df.rename(
        columns={
            "employee_id": "employee_id",
            "first_name": "first_name",
            "last_name": "last_name",
            "primary_role": "primary_role",
            "skill_coffee": "skill_coffee",
            "skill_sandwich": "skill_sandwich",
            "customer_service_rating": "customer_service_rating",
            "skill_speed": "skill_speed",
        },
        inplace=True,
    )
    df["primary_role"] = df["primary_role"].str.upper()
    return df


def read_shifts(path: str | Path, week_id: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.rename(columns={"id": "shift_id"}, inplace=True)
    # Keep only target week if provided
    if week_id is not None:
        df = df[df["week_id"] == week_id].copy()
    # Ensure date dtype
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def write_assignments(path: str | Path, assignments_df: pd.DataFrame) -> None:
    cols = ["shift_id", "emp_id", "start_time", "end_time"]
    assignments_df[cols].to_csv(path, index=False)


def local_day_bounds(local_date: datetime, start_hm: str, end_hm: str, tz: str) -> Tuple[datetime, datetime]:
    # naive local times; assignment will format as ISO8601 with offset via pandas tz_localize
    start_h, start_m = [int(x) for x in start_hm.split(":")]
    end_h, end_m = [int(x) for x in end_hm.split(":")]
    day = local_date.date()
    start_dt = datetime.combine(day, time(start_h, start_m))
    end_dt = datetime.combine(day, time(end_h, end_m))
    return start_dt, end_dt


def to_iso_with_tz(dt: datetime, tz: str) -> str:
    # Represent as ISO8601 with local offset using pandas timezone handling
    s = pd.Timestamp(dt).tz_localize(tz)
    return s.isoformat()



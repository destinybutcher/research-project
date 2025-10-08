from __future__ import annotations

from typing import Dict

import pandas as pd

from .constraints import has_overlap, within_cafe_hours


def validate_assignments(
    employees_df: pd.DataFrame,
    shifts_df: pd.DataFrame,
    assignments_df: pd.DataFrame,
    start_hm: str,
    end_hm: str,
    requirements_by_date: Dict[str, Dict[str, int]] | None = None,
) -> None:
    # Referential integrity
    emp_ids = set(int(x) for x in employees_df["employee_id"].unique())
    shift_ids = set(int(x) for x in shifts_df["shift_id"].unique())
    if not set(int(x) for x in assignments_df["emp_id"]).issubset(emp_ids):
        raise ValueError("Assignments reference unknown employee ids")
    if not set(int(x) for x in assignments_df["shift_id"]).issubset(shift_ids):
        raise ValueError("Assignments reference unknown shift ids")

    # Cafe hours window - allow SANDWICH shifts to start before café hours
    # Get employee roles for each assignment
    emp_roles = employees_df[["employee_id", "primary_role"]].copy()
    emp_roles["primary_role"] = emp_roles["primary_role"].str.upper()
    merged = assignments_df.merge(emp_roles, left_on="emp_id", right_on="employee_id", how="left")
    
    # Convert times to datetime for easier checking
    merged["start_time"] = pd.to_datetime(merged["start_time"])
    merged["end_time"] = pd.to_datetime(merged["end_time"])
    
    # Check café hours for non-SANDWICH roles (07:00-15:00)
    non_sandwich = merged[merged["primary_role"] != "SANDWICH"]
    if not non_sandwich.empty:
        # Check start times are >= 07:00
        invalid_starts = non_sandwich[non_sandwich["start_time"].dt.hour < 7]
        if not invalid_starts.empty:
            raise ValueError(f"Non-SANDWICH shifts start before café hours (07:00): {len(invalid_starts)} assignments")
        
        # Check end times are <= 15:00
        invalid_ends = non_sandwich[non_sandwich["end_time"].dt.hour > 15]
        if not invalid_ends.empty:
            raise ValueError(f"Non-SANDWICH shifts end after café hours (15:00): {len(invalid_ends)} assignments")
        
        # Check end minutes are 00
        invalid_minutes = non_sandwich[non_sandwich["end_time"].dt.minute != 0]
        if not invalid_minutes.empty:
            raise ValueError(f"Non-SANDWICH shifts don't end on the hour: {len(invalid_minutes)} assignments")
    
    # For SANDWICH roles, allow early start but ensure end is within reasonable hours
    sandwich_assignments = merged[merged["primary_role"] == "SANDWICH"]
    if not sandwich_assignments.empty:
        # SANDWICH shifts should end by 15:00 (café closing)
        invalid_sandwich_ends = sandwich_assignments[sandwich_assignments["end_time"].dt.hour > 15]
        if not invalid_sandwich_ends.empty:
            raise ValueError(f"SANDWICH shifts end after café closing (15:00): {len(invalid_sandwich_ends)} assignments")

    # No overlaps per employee per day
    if has_overlap(assignments_df):
        raise ValueError("Overlapping assignments detected for an employee within a day")

    # Weekly hours cap
    # infer block hours by difference (assumes same for all)
    ts = assignments_df.copy()
    ts["start_time"] = pd.to_datetime(ts["start_time"])  # tz-aware
    ts["end_time"] = pd.to_datetime(ts["end_time"])  # tz-aware
    ts["hours"] = (ts["end_time"] - ts["start_time"]).dt.total_seconds() / 3600.0
    if per_role_caps:
        # join with employees to get primary roles
        emp_roles = employees_df[["employee_id", "primary_role"]].copy()
        emp_roles["primary_role"] = emp_roles["primary_role"].str.upper()
        merged = ts.merge(emp_roles, left_on="emp_id", right_on="employee_id", how="left")
        weekly = merged.groupby(["emp_id", "primary_role"])['hours'].sum().reset_index()
        for _, row in weekly.iterrows():
            role = str(row["primary_role"]).upper()
            cap = float(per_role_caps.get(role, float("inf")))
            if row["hours"] > cap + 1e-6:
                raise ValueError(f"Weekly hours exceed hard cap for role {role}: {row['hours']:.2f} > {cap}")
    if global_hard_cap is not None:
        weekly_emp = ts.groupby("emp_id")["hours"].sum()
        if (weekly_emp > float(global_hard_cap) + 1e-6).any():
            raise ValueError("Weekly hours exceed global hard cap for some employees")

    # Coverage per role per day exactly met if requirements provided
    if requirements_by_date is not None:
        ts["date"] = ts["start_time"].dt.tz_convert(None).dt.strftime("%Y-%m-%d")
        counts = ts.groupby(["date", "role"]).size().unstack(fill_value=0)
        for date_str, role_req in requirements_by_date.items():
            for role, needed in role_req.items():
                got = int(counts.get(role, pd.Series()).get(date_str, 0))
                if got != int(needed):
                    raise ValueError(
                        f"Coverage mismatch on {date_str} for role {role}: expected {needed}, got {got}"
                    )


def summarize_assignments(assignments_df: pd.DataFrame) -> str:
    if assignments_df.empty:
        return "No assignments."
    ts = assignments_df.copy()
    ts["start_time"] = pd.to_datetime(ts["start_time"])  # tz-aware
    ts["end_time"] = pd.to_datetime(ts["end_time"])  # tz-aware
    ts["date"] = ts["start_time"].dt.tz_convert(None).dt.strftime("%Y-%m-%d")
    ts["hours"] = (ts["end_time"] - ts["start_time"]).dt.total_seconds() / 3600.0

    coverage = ts.groupby(["date", "role"]).size().unstack(fill_value=0)
    hours = ts.groupby("emp_id")["hours"].sum().sort_values(ascending=False)
    tags = ts.groupby(["date", "role"])  # capture day/shift types
    tag_summary = ts.groupby(["date", "role"]).agg(
        shift_types=("shift_type", lambda s: ",".join(sorted(set([str(x) for x in s if pd.notna(x)]))) ),
        day_types=("day_type", lambda s: ",".join(sorted(set([str(x) for x in s if pd.notna(x)]))) ),
    )

    lines = ["Coverage per day per role:"]
    lines.append(coverage.to_string())
    lines.append("")
    lines.append("Shift/Day types per day per role:")
    lines.append(tag_summary.to_string())
    lines.append("")
    lines.append("Hours per employee (week):")
    lines.append(hours.to_string())
    return "\n".join(lines)



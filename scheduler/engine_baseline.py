from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd

from .config import SchedulerConfig
from .constraints import is_role_eligible
from .data_io import local_day_bounds, to_iso_with_tz
from .scoring import RoleWeights, fairness_penalty, role_fitness
from .scoring import hours_deviation_penalty


@dataclass
class Assignment:
    shift_id: int
    emp_id: int
    start_time: str
    end_time: str
    role: str
    shift_type: str | None = None
    day_type: str | None = None


def build_requirements_for_day(date_str: str, cfg: SchedulerConfig) -> Dict[str, int]:
    req = dict(cfg.default_requirements)
    
    # Check if it's a weekend (Saturday or Sunday)
    date_obj = pd.Timestamp(date_str).date()
    day_name = pd.Timestamp(date_str).day_name()
    if day_name in ["Saturday", "Sunday"]:
        # Use weekend requirements
        for role, count in cfg.weekend_requirements.items():
            req[role] = count
    
    # Apply date-specific overrides (takes precedence)
    if date_str in cfg.overrides:
        for role, count in cfg.overrides[date_str].items():
            req[role] = count
    
    return req


def greedy_schedule(
    employees_df: pd.DataFrame, shifts_df: pd.DataFrame, cfg: SchedulerConfig
) -> pd.DataFrame:
    # Prepare
    tz = cfg.timezone
    default_start = cfg.default_shift.start
    default_end = cfg.default_shift.end
    block_hours = cfg.default_shift.duration_hours
    role_weights = RoleWeights(
        manager_weight=cfg.weights.manager_weight,
        coffee=cfg.weights.coffee,
        sandwich=cfg.weights.sandwich,
        speed=cfg.weights.speed,
        customer_service=cfg.weights.customer_service,
        fairness_penalty_per_std_above_median=cfg.weights.fairness_penalty_per_std_above_median,
    )

    # Track weekly hours per employee
    weekly_hours: Dict[int, float] = defaultdict(float)

    # Group shifts by day
    shifts_df = shifts_df.sort_values(["date", "shift_id"])  # ensure stable order
    days = list(shifts_df["date"].unique())
    if getattr(cfg, "schedule_busy_days_first", False):
        def _busy_key(d):
            name = pd.Timestamp(d).day_name()
            return (0 if name in cfg.busy_days else 1, pd.Timestamp(d))
        days = sorted(days, key=_busy_key)

    assignments: List[Assignment] = []

    # For fairness penalties per role, compute within the role cohort
    for day in days:
        day_str = pd.Timestamp(day).strftime("%Y-%m-%d")
        weekday_name = pd.Timestamp(day).day_name()
        is_busy_day = weekday_name in cfg.busy_days
        day_type = "weekend" if is_busy_day else "weekday"
        day_shifts = shifts_df[shifts_df["date"] == day]
        if day_shifts.empty:
            continue
        # coverage requirements for the day
        req_map = build_requirements_for_day(day_str, cfg)

        # maintain who is already assigned today
        assigned_today: set[int] = set()

        # precompute fairness per role based on current weekly hours
        fairness_by_role: Dict[str, Dict[int, float]] = {}
        for role in req_map.keys():
            role_cohort = employees_df[employees_df["primary_role"].str.upper() == role]
            hours_series = pd.Series(
                {int(row.employee_id): weekly_hours[int(row.employee_id)] for _, row in role_cohort.iterrows()}
            )
            fairness_by_role[role] = fairness_penalty(hours_series, role, role_weights)

        # For each role and required slots, assign employees across shifts of the day.
        # We distribute sequentially over the shifts; each slot is one employee for 1 block.
        # Gather shift_ids for the day
        shift_ids = list(day_shifts["shift_id"].astype(int))
        if not shift_ids:
            continue

        for role, needed in req_map.items():
            if needed == 0:
                continue

            role_candidates = employees_df[
                employees_df["primary_role"].str.upper() == role
            ].copy()

            if role_candidates.empty:
                raise RuntimeError(
                    f"Coverage impossible on {day_str} for role {role}: no eligible employees."
                )

            # Determine time windows for this role/day
            role_windows = cfg.role_time_windows.get(role, {}) if cfg.role_time_windows else {}
            time_patterns: List[Tuple[str, str]] = []
            shift_type_label = None
            if role in {"BARISTA", "WAITER"}:
                if is_busy_day:
                    # Prefer two staggered windows; if not configured, fallback to default single
                    weekend_pat = role_windows.get("weekend_staggered") if role_windows else None
                    if isinstance(weekend_pat, list) and len(weekend_pat) >= 2:
                        for p in weekend_pat[:2]:
                            time_patterns.append((p["start"], p["end"]))
                        shift_type_label = "weekend_double"
                    else:
                        # fallback to default
                        time_patterns.append((default_start, default_end))
                        time_patterns.append((default_start, default_end))
                        shift_type_label = "weekend_double"
                else:
                    weekday_pat = role_windows.get("weekday") if role_windows else None
                    if isinstance(weekday_pat, dict) and "start" in weekday_pat and "end" in weekday_pat:
                        time_patterns.append((weekday_pat["start"], weekday_pat["end"]))
                    else:
                        time_patterns.append((default_start, default_end))
                    shift_type_label = "weekday_single"
            elif role == "SANDWICH":
                if is_busy_day:
                    weekend_pat = role_windows.get("weekend") if role_windows else None
                    if isinstance(weekend_pat, list) and len(weekend_pat) >= 2:
                        for p in weekend_pat[:2]:
                            time_patterns.append((p["start"], p["end"]))
                        shift_type_label = "weekend_double"
                    else:
                        # default early to 05:00-13:30 and 06:00-13:30 if not configured
                        time_patterns.extend([("05:00", "13:30"), ("06:00", "13:30")])
                        shift_type_label = "weekend_double"
                else:
                    weekday_pat = role_windows.get("weekday") if role_windows else None
                    if isinstance(weekday_pat, list) and len(weekday_pat) >= 1:
                        p = weekday_pat[0]
                        time_patterns.append((p["start"], p["end"]))
                    else:
                        time_patterns.append(("05:00", "12:00"))
                    shift_type_label = "weekday_single"
            else:
                # MANAGER or other roles use default single block
                time_patterns.append((default_start, default_end))
                shift_type_label = "weekday_single" if not is_busy_day else "weekend_single"

            # For roles needing multiple slots, replicate patterns to match needed count
            if len(time_patterns) == 1 and needed > 1:
                # fill with same window copies
                time_patterns = time_patterns * needed
            elif len(time_patterns) >= 2 and needed > len(time_patterns):
                # cycle through provided patterns
                reps = (needed + len(time_patterns) - 1) // len(time_patterns)
                time_patterns = (time_patterns * reps)[:needed]

            # Simple round-robin across shift_ids to place each slot
            round_robin = deque(shift_ids)
            slots_assigned = 0

            backtrack_buffer: List[Tuple[int, Assignment]] = []

            while slots_assigned < needed:
                if not round_robin:
                    round_robin = deque(shift_ids)
                current_shift_id = round_robin.popleft()
                # Select time pattern for this slot
                start_hm, end_hm = time_patterns[slots_assigned] if slots_assigned < len(time_patterns) else (default_start, default_end)

                # candidate pool: eligible, not assigned today, within hours cap
                def eligible_mask(r: pd.Series) -> bool:
                    emp_id = int(r["employee_id"])
                    if emp_id in assigned_today:
                        return False
                    # compute slot hours for this window
                    sdt, edt = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
                    slot_hours = (edt - sdt).total_seconds() / 3600.0
                    # per-role hard cap, and optional global hard cap
                    role_pol = cfg.hours_policy.get(role, {})
                    role_cap = float(role_pol.get("hard_cap", cfg.hours_caps.max_hours_per_week_per_employee))
                    if weekly_hours[emp_id] + slot_hours > role_cap:
                        return False
                    if cfg.global_hard_cap is not None and weekly_hours[emp_id] + slot_hours > float(cfg.global_hard_cap):
                        return False
                    return is_role_eligible(str(r["primary_role"]), role)

                pool = role_candidates[role_candidates.apply(eligible_mask, axis=1)]
                if pool.empty:
                    # attempt backtracking: swap within the same role for this day
                    swapped = False
                    for idx, prev in reversed(backtrack_buffer):
                        prev_emp_id = prev.emp_id
                        # try to replace prev with someone else to free a better candidate now
                        alt_pool = role_candidates[
                            role_candidates["employee_id"] != prev_emp_id
                        ]
                        alt_pool = alt_pool[alt_pool.apply(eligible_mask, axis=1)]
                        if alt_pool.empty:
                            continue
                        fairness_map = fairness_by_role.get(role, {})
                        alt_scores = alt_pool.apply(
                            lambda r: role_fitness(r, role, role_weights)
                            - float(fairness_map.get(int(r["employee_id"]), 0.0)),
                            axis=1,
                        )
                        best_idx = int(alt_scores.idxmax())
                        best_row = alt_pool.loc[best_idx]
                        best_emp_id = int(best_row["employee_id"])

                        # Apply swap
                        # revert hours for previous assignment based on its actual duration
                        prev_start = pd.to_datetime(prev.start_time).tz_convert(None).to_pydatetime()
                        prev_end = pd.to_datetime(prev.end_time).tz_convert(None).to_pydatetime()
                        prev_hours = (prev_end - prev_start).total_seconds() / 3600.0
                        weekly_hours[prev_emp_id] -= prev_hours
                        assigned_today.remove(prev_emp_id)
                        # add hours for best candidate based on current window
                        sdt2, edt2 = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
                        slot_hours2 = (edt2 - sdt2).total_seconds() / 3600.0
                        weekly_hours[best_emp_id] += slot_hours2
                        assigned_today.add(best_emp_id)

                        # replace in assignments list
                        assignments[idx] = Assignment(
                            shift_id=prev.shift_id,
                            emp_id=best_emp_id,
                            start_time=prev.start_time,
                            end_time=prev.end_time,
                            role=role,
                        )
                        backtrack_buffer[idx] = (idx, assignments[idx])
                        swapped = True
                        break

                    if not swapped:
                        raise RuntimeError(
                            f"Coverage impossible on {day_str} for role {role}: insufficient eligible staff within hour caps."
                        )

                    # after swap, continue to next iteration without incrementing slots_assigned to retry
                    continue

                fairness_map = fairness_by_role.get(role, {})
                # Strictly filter pool to those who remain within hard cap after this slot
                sdt_pool, edt_pool = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
                slot_hours_pool = (edt_pool - sdt_pool).total_seconds() / 3600.0
                role_pol_pool = cfg.hours_policy.get(role, {})
                hard_cap_pool = float(role_pol_pool.get("hard_cap", cfg.hours_caps.max_hours_per_week_per_employee))
                if not pool.empty:
                    pool = pool[pool.apply(lambda rr: weekly_hours[int(rr["employee_id"])] + slot_hours_pool <= hard_cap_pool, axis=1)]
                    if pool.empty:
                        # trigger backtracking path
                        raise RuntimeError(
                            f"Coverage impossible on {day_str} for role {role}: insufficient eligible staff within hour caps."
                        )
                # include hours deviation penalty (lower is better, so subtract)
                def score_row(r: pd.Series) -> float:
                    emp_id_local = int(r["employee_id"])
                    # compute slot hours to estimate post-assignment weekly hours
                    sdt3, edt3 = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
                    slot_hours3 = (edt3 - sdt3).total_seconds() / 3600.0
                    post_hours = weekly_hours[emp_id_local] + slot_hours3
                    
                    # Strong penalty for exceeding hard cap
                    role_pol = cfg.hours_policy.get(role, {})
                    hard_cap = float(role_pol.get("hard_cap", cfg.hours_caps.max_hours_per_week_per_employee))
                    if post_hours > hard_cap:
                        return -1000.0  # Strong negative score for exceeding hard cap
                    
                    hours_pen = hours_deviation_penalty(
                        post_hours, role, cfg.hours_policy, cfg.hours_penalties
                    )
                    return (
                        role_fitness(r, role, role_weights)
                        - float(fairness_map.get(emp_id_local, 0.0))
                        - hours_pen
                    )
                scores = pool.apply(score_row, axis=1)
                chosen_idx = int(scores.idxmax())
                chosen = pool.loc[chosen_idx]
                emp_id = int(chosen["employee_id"])

                # build times
                start_dt, end_dt = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
                start_iso = to_iso_with_tz(start_dt, tz)
                end_iso = to_iso_with_tz(end_dt, tz)

                assign = Assignment(
                    shift_id=int(current_shift_id),
                    emp_id=emp_id,
                    start_time=start_iso,
                    end_time=end_iso,
                    role=role,
                    shift_type=shift_type_label,
                    day_type=day_type,
                )
                assignments.append(assign)
                backtrack_buffer.append((len(assignments) - 1, assign))

                # increment weekly hours by actual slot duration
                weekly_hours[emp_id] += (end_dt - start_dt).total_seconds() / 3600.0
                assigned_today.add(emp_id)
                slots_assigned += 1

            # Weekend fallback: if we exit loop without filling all needed slots
            if slots_assigned < needed and is_busy_day and cfg.weekend_fallback.get(role, {}).get("enabled", False):
                fb = cfg.weekend_fallback[role]
                min_required = int(fb.get("min_required", 1))
                allow_single = bool(fb.get("allow_single_full_shift", False))
                # Try single full shift if allowed
                if allow_single and slots_assigned < needed:
                    start_hm_fb, end_hm_fb = default_start, default_end
                    def eligible_fb(r: pd.Series) -> bool:
                        emp_id_fb = int(r["employee_id"])
                        if emp_id_fb in assigned_today:
                            return False
                        sdt_fb, edt_fb = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm_fb, end_hm_fb, tz)
                        slot_h_fb = (edt_fb - sdt_fb).total_seconds() / 3600.0
                        role_pol_fb = cfg.hours_policy.get(role, {})
                        cap_fb = float(role_pol_fb.get("hard_cap", cfg.hours_caps.max_hours_per_week_per_employee))
                        if weekly_hours[emp_id_fb] + slot_h_fb > cap_fb:
                            return False
                        if cfg.global_hard_cap is not None and weekly_hours[emp_id_fb] + slot_h_fb > float(cfg.global_hard_cap):
                            return False
                        return is_role_eligible(str(r["primary_role"]), role)
                    fb_pool = role_candidates[role_candidates.apply(eligible_fb, axis=1)]
                    if not fb_pool.empty:
                        def fb_score(r: pd.Series) -> float:
                            emp = int(r["employee_id"])
                            sdt4, edt4 = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm_fb, end_hm_fb, tz)
                            slot_h4 = (edt4 - sdt4).total_seconds() / 3600.0
                            post_h = weekly_hours[emp] + slot_h4
                            return (
                                role_fitness(r, role, role_weights)
                                - float(fairness_by_role.get(role, {}).get(emp, 0.0))
                                - hours_deviation_penalty(post_h, role, cfg.hours_policy, cfg.hours_penalties)
                            )
                        best_idx_fb = int(fb_pool.apply(fb_score, axis=1).idxmax())
                        rbest = fb_pool.loc[best_idx_fb]
                        emp_fb = int(rbest["employee_id"])
                        sdt_fb2, edt_fb2 = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm_fb, end_hm_fb, tz)
                        start_iso_fb = to_iso_with_tz(sdt_fb2, tz)
                        end_iso_fb = to_iso_with_tz(edt_fb2, tz)
                        assign_fb = Assignment(
                            shift_id=int(shift_ids[0]),
                            emp_id=emp_fb,
                            start_time=start_iso_fb,
                            end_time=end_iso_fb,
                            role=role,
                            shift_type="weekend_fallback_single",
                            day_type=day_type,
                        )
                        assignments.append(assign_fb)
                        weekly_hours[emp_fb] += (edt_fb2 - sdt_fb2).total_seconds() / 3600.0
                        assigned_today.add(emp_fb)
                        slots_assigned += 1
                # If still below min_required, log debug and continue (soft reduce requirement)
                if slots_assigned < min_required:
                    _emit_debug(day, day_str, role, employees_df, weekly_hours, default_start, default_end, tz, cfg)
                    # Do not raise here; accept under-staff to min_required policy if even that not met, raise
                    raise RuntimeError(
                        f"Coverage impossible on {day_str} for role {role} even after weekend fallback"
                    )

    # Build DataFrame
    out = pd.DataFrame(
        [
            {
                "shift_id": a.shift_id,
                "emp_id": a.emp_id,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "role": a.role,
                "shift_type": a.shift_type,
                "day_type": a.day_type,
            }
            for a in assignments
        ]
    )
    return out


def _emit_debug(day, day_str, role, employees_df, weekly_hours, start_hm, end_hm, tz, cfg):
    print(f"[DEBUG] Unable to cover {day_str} role {role}. Candidate analysis:")
    sdt, edt = local_day_bounds(pd.Timestamp(day).to_pydatetime(), start_hm, end_hm, tz)
    slot_hours = (edt - sdt).total_seconds() / 3600.0
    for _, e in employees_df.iterrows():
        eid = int(e["employee_id"])
        reasons = []
        if str(e["primary_role"]).upper() != role:
            reasons.append("role_mismatch")
        elif weekly_hours[eid] + slot_hours > float(cfg.hours_policy.get(role, {}).get("hard_cap", 1e9)):
            reasons.append("would_exceed_hard_cap")
        else:
            reasons.append("OK_or_other_constraint")
        print("  -", eid, reasons)



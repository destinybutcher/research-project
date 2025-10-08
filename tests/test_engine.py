import pandas as pd

from scheduler.config import SchedulerConfig
from scheduler.engine_baseline import greedy_schedule, build_requirements_for_day
from scheduler.validator import validate_assignments


def _employees_basic():
    return pd.DataFrame(
        [
            {"employee_id": 1, "first_name": "A", "last_name": "A", "primary_role": "MANAGER"},
            {"employee_id": 2, "first_name": "B", "last_name": "B", "primary_role": "BARISTA", "skill_coffee": 5, "skill_speed": 4, "customer_service_rating": 3},
            {"employee_id": 3, "first_name": "C", "last_name": "C", "primary_role": "BARISTA", "skill_coffee": 4, "skill_speed": 3, "customer_service_rating": 4},
            {"employee_id": 4, "first_name": "D", "last_name": "D", "primary_role": "WAITER", "skill_speed": 3, "customer_service_rating": 5},
            {"employee_id": 5, "first_name": "E", "last_name": "E", "primary_role": "SANDWICH", "skill_sandwich": 5},
        ]
    )


def _shifts_5_days():
    rows = []
    for i, d in enumerate(pd.date_range("2025-09-01", periods=5, freq="D")):
        rows.append({"shift_id": i + 1, "date": d.date(), "week_id": "2025-W36"})
    return pd.DataFrame(rows)


def test_generate_and_validate_basic():
    cfg = SchedulerConfig()
    employees = _employees_basic()
    shifts = _shifts_5_days()
    assignments = greedy_schedule(employees, shifts, cfg)

    req_by_date = {}
    for date in sorted(shifts["date"].unique()):
        ds = pd.Timestamp(date).strftime("%Y-%m-%d")
        req_by_date[ds] = build_requirements_for_day(ds, cfg)

    validate_assignments(
        employees,
        shifts,
        assignments,
        cfg.default_shift.start,
        cfg.default_shift.end,
        requirements_by_date=req_by_date,
    )


def test_insufficient_sandwich_staff():
    cfg = SchedulerConfig()
    employees = _employees_basic().query("primary_role != 'SANDWICH'")
    shifts = _shifts_5_days().head(1)
    try:
        _ = greedy_schedule(employees, shifts, cfg)
        assert False, "Expected RuntimeError due to missing SANDWICH staff"
    except RuntimeError as e:
        assert "SANDWICH" in str(e)



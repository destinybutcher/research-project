import pandas as pd

from scheduler.validator import validate_assignments


def test_referential_integrity_failure():
    employees = pd.DataFrame([{"employee_id": 1}])
    shifts = pd.DataFrame([{"shift_id": 1, "date": pd.Timestamp("2025-09-01").date(), "week_id": "2025-W36"}])
    assignments = pd.DataFrame(
        [{"shift_id": 1, "emp_id": 999, "start_time": "2025-09-01T07:00:00+10:00", "end_time": "2025-09-01T15:00:00+10:00", "role": "MANAGER"}]
    )
    try:
        validate_assignments(employees, shifts, assignments, "07:00", "15:00")
        assert False, "Should fail unknown employee id"
    except ValueError as e:
        assert "employee" in str(e).lower()



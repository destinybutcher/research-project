import pandas as pd

from scheduler.constraints import is_role_eligible, has_overlap, within_cafe_hours


def test_role_eligibility_matrix():
    assert is_role_eligible("BARISTA", "BARISTA")
    assert not is_role_eligible("BARISTA", "SANDWICH")
    assert is_role_eligible("SANDWICH", "SANDWICH")
    assert not is_role_eligible("SANDWICH", "BARISTA")
    assert is_role_eligible("MANAGER", "MANAGER")
    assert not is_role_eligible("WAITER", "BARISTA")


def test_overlap_detection():
    df = pd.DataFrame(
        [
            {
                "shift_id": 1,
                "emp_id": 1001,
                "start_time": "2025-09-01T07:00:00+10:00",
                "end_time": "2025-09-01T15:00:00+10:00",
            },
            {
                "shift_id": 2,
                "emp_id": 1001,
                "start_time": "2025-09-01T14:00:00+10:00",
                "end_time": "2025-09-01T15:00:00+10:00",
            },
        ]
    )
    assert has_overlap(df)


def test_cafe_hours_window():
    df = pd.DataFrame(
        [
            {
                "shift_id": 1,
                "emp_id": 1001,
                "start_time": "2025-09-01T07:00:00+10:00",
                "end_time": "2025-09-01T15:00:00+10:00",
            }
        ]
    )
    assert within_cafe_hours(df, "07:00", "15:00")
    bad = df.copy()
    bad.loc[0, "end_time"] = "2025-09-01T15:30:00+10:00"
    assert not within_cafe_hours(bad, "07:00", "15:00")



# Café Scheduler (Milestone 1)

AI-assisted rostering baseline for a café. Generates a valid weekly schedule from CSVs respecting roles, skills, and hard constraints.

## Quickstart

Requirements: Python 3.11, `pandas`. Optionally `pyyaml` if using YAML config.

```bash
python -m pip install pandas pyyaml
```

Project layout:

```
scheduler/
  config.py, data_io.py, constraints.py, scoring.py, engine_baseline.py,
  validator.py, feedback.py, cli.py
tests/
  ...
```

### Example config (`scheduler_config.yaml`)

```yaml
timezone: "Australia/Sydney"
default_shift:
  start: "07:00"
  end: "15:00"
  duration_hours: 8
default_requirements:
  MANAGER: 1
  BARISTA: 2
  WAITER: 1
  SANDWICH: 1
overrides: {}
hours_caps:
  max_hours_per_week_per_employee: 40
weights:
  manager_weight: 1.0
  coffee: 1.0
  sandwich: 1.0
  speed: 0.5
  customer_service: 0.5
  fairness_penalty_per_std_above_median: 0.25
```

### Commands

Generate for a week:

```bash
python -m scheduler.cli generate --week 2025-W36 \
  --employees /mnt/data/employees_new_12w_v2.csv \
  --shifts /mnt/data/shift_new_12w_v2.csv \
  --config ./scheduler_config.yaml \
  --out ./shift_details_generated.csv
```

Validate an existing assignment CSV:

```bash
python -m scheduler.cli validate \
  --employees /mnt/data/employees_new_12w_v2.csv \
  --shifts /mnt/data/shift_new_12w_v2.csv \
  --assignments ./shift_details_generated.csv \
  --config ./scheduler_config.yaml
```

Print a summary:

```bash
python -m scheduler.cli summarize --assignments ./shift_details_generated.csv
```

## Notes

- Baseline uses a greedy algorithm with light backtracking within a day/role.
- Strict validation enforces café hours, no overlaps, coverage counts, and referential integrity.
- `feedback.py` provides stubs for future learning from post-shift ratings.



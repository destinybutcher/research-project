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
1. Modular Architecture
scheduler/
├── config.py          # Configuration management
├── data_io.py         # Data loading/saving
├── constraints.py     # Business rule validation
├── scoring.py         # Employee fitness scoring
├── engine_baseline.py # Core scheduling algorithm
├── validator.py       # Post-generation validation
├── feedback.py        # Future ML integration hooks
└── cli.py            # Command-line interface
2. Configuration-Driven Design
YAML-based configuration for flexible business rules
Role-based policies (hours, requirements, time windows)
Date-specific overrides for special days
Weighted scoring parameters for optimization

Core Algorithms & Techniques
1. Greedy Algorithm with Backtracking
Key Features:
Constraint satisfaction during assignment
Light backtracking for conflict resolution
Role-specific time windows (early SANDWICH shifts)
Weekend fallback logic for busy days
2. Multi-Objective Scoring Function
Components:
Skill-based fitness: Weighted sum of relevant skills
Fairness penalty: Load balancing within role cohorts
Hours deviation penalty: Soft constraints for target hours
3. Constraint Satisfaction
Hard Constraints:
No employee overlaps within same day
Role eligibility (SANDWICH ≠ BARISTA duties)
Weekly hours hard caps per role
Café operating hours (07:00-15:00, except SANDWICH)
Soft Constraints:
Target hours per role (16-32h for part-time, 38-40h for managers)
Fairness within role cohorts
Weekend coverage requirements


 Data Structures & Processing
1. Pandas DataFrames
Employees: Skills, roles, personal info
Shifts: Dates, week IDs, shift IDs
Assignments: Generated schedule with timestamps
2. Time Series Handling
Timezone-aware: Australia/Sydney (AEST/AEDT)


Validation & Quality Assurance
1. Multi-Layer Validation
Referential integrity: All IDs exist
Constraint checking: No overlaps, hours caps
Coverage validation: Requirements met
Business rules: Café hours, role eligibility
2. Comprehensive Reporting
Employee hours analysis with target/hard cap status
Daily schedule views with role coverage
Workload distribution across team
CSV exports for external systems



Performance & Scalability
1. Algorithm Complexity
Time: O(D × R × S × E) where D=days, R=roles, S=slots, E=employees
Space: O(E + A) where A=assignments
Practical: Handles 8 employees × 7 days efficiently
2. Optimization Techniques
Early termination on constraint violations
Candidate pool filtering before scoring
Backtracking buffer for conflict resolution
Pandas vectorization for data operations
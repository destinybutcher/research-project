# Test Suite for v2 Architecture

## Overview

This test suite validates the refactored role-based scheduling architecture.

## Test Organization

- `test_manager_scheduler.py` - Tests for ManagerScheduler
- `test_sandwich_scheduler.py` - Tests for SandwichScheduler  
- `test_cohort_scheduler.py` - Tests for CohortScheduler (BARISTA/WAITER)
- `test_orchestrator.py` - Tests for Orchestrator and full week generation
- `test_services.py` - Tests for service layer (constraints, scoring, timeplan)
- `test_csv_io.py` - Tests for CSV import/export functionality
- `conftest.py` - Shared fixtures and configuration

## Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_manager_scheduler.py

# Run with verbose output
python -m pytest -v tests/

# Run with coverage
python -m pytest --cov=scheduler tests/

# Run only fast tests (exclude slow/integration)
python -m pytest -m "not slow and not integration" tests/
```

## Test Coverage

### Manager Scheduler
- ✅ Creates valid assignments
- ✅ Respects hours caps (40h max)
- ✅ Weekend coverage (2 managers on Sat/Sun)
- ✅ No overlapping assignments
- ✅ Fails gracefully with no staff

### Sandwich Scheduler
- ✅ Creates valid assignments
- ✅ Early morning shifts (05:00-12:00)
- ✅ Respects hours caps (36h max)
- ✅ No overlapping assignments

### Cohort Scheduler
- ✅ Creates valid assignments for BARISTA/WAITER
- ✅ Respects hours caps (40h max)
- ✅ Café hours compliance (07:00-15:00)
- ✅ Rejects invalid roles

### Orchestrator
- ✅ Builds complete schedule for all roles
- ✅ No employee overlaps across roles
- ✅ All employees assigned
- ✅ Persists to database
- ✅ Custom scheduler order

### Services
- ✅ Time parsing and calculation
- ✅ Employee eligibility checking
- ✅ Role fitness scoring
- ✅ Fairness penalty calculation

### CSV I/O
- ✅ Import employees from CSV
- ✅ Import shifts from CSV
- ✅ Export to CSV
- ✅ Week filtering

## Requirements

```bash
pip install pytest pytest-cov
```

## Adding New Tests

1. Create test file: `tests/test_your_feature.py`
2. Use fixtures from `conftest.py` or create new ones
3. Follow naming convention: `test_feature_description`
4. Run tests to verify: `pytest tests/test_your_feature.py`


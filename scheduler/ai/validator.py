"""Validation functions for CP-SAT scheduler results."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List

from scheduler.domain.models import Assignment, Employee, Shift
from scheduler.services.constraints import validate_assignment_constraints
from scheduler.services.requirements import build_requirements_for_day


def validate_cp_sat_schedule(
    assignments: List[Assignment],
    employees: List[Employee],
    shifts: List[Shift],
    cfg,
) -> Dict[str, any]:
    """
    Validate CP-SAT generated schedule.
    
    Returns:
        Dict with validation results including:
        - valid: bool
        - errors: List[str]
        - warnings: List[str]
        - stats: Dict with statistics
    """
    results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'stats': {},
    }
    
    # 1. Use existing constraint validator
    try:
        validate_assignment_constraints(assignments, employees, cfg)
    except ValueError as e:
        results['valid'] = False
        results['errors'].append(f"Constraint validation failed: {e}")
        return results
    
    # 2. Check coverage per day per role
    shifts_by_date: Dict[date, List[Shift]] = defaultdict(list)
    for shift in shifts:
        shifts_by_date[shift.date].append(shift)
    
    assignments_by_date: Dict[date, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for assign in assignments:
        shift_date = assign.start_time.date()
        role = assign.role or "UNKNOWN"
        assignments_by_date[shift_date][role] += 1
    
    # Build requirements per day
    for shift_date, day_shifts in shifts_by_date.items():
        date_str = shift_date.strftime("%Y-%m-%d")
        requirements = build_requirements_for_day(date_str, cfg)
        
        for role, required_count in requirements.items():
            role = role.upper()
            actual_count = assignments_by_date[shift_date].get(role, 0)
            
            if actual_count != required_count:
                results['valid'] = False
                results['errors'].append(
                    f"Coverage mismatch on {date_str} for {role}: "
                    f"expected {required_count}, got {actual_count}"
                )
    
    # 3. Check one assignment per day per employee
    emp_by_date: Dict[int, Dict[date, List[Assignment]]] = defaultdict(lambda: defaultdict(list))
    for assign in assignments:
        shift_date = assign.start_time.date()
        emp_by_date[assign.emp_id][shift_date].append(assign)
    
    for emp_id, date_assigns in emp_by_date.items():
        for shift_date, day_assigns in date_assigns.items():
            if len(day_assigns) > 1:
                results['valid'] = False
                results['errors'].append(
                    f"Employee {emp_id} has {len(day_assigns)} assignments on {shift_date}"
                )
    
    # 4. Check role compatibility (employee can only work their primary role)
    emp_dict = {emp.employee_id: emp for emp in employees}
    for assign in assignments:
        emp = emp_dict.get(assign.emp_id)
        if emp and assign.role:
            if emp.primary_role.upper() != assign.role.upper():
                results['valid'] = False
                results['errors'].append(
                    f"Role mismatch: Employee {assign.emp_id} ({emp.primary_role}) "
                    f"assigned to {assign.role} role"
                )
    
    # 5. Check fairness (hours distribution within role cohorts)
    weekly_hours: Dict[int, float] = defaultdict(float)
    for assign in assignments:
        duration = (assign.end_time - assign.start_time).total_seconds() / 3600.0
        weekly_hours[assign.emp_id] += duration
    
    # Group by role
    hours_by_role: Dict[str, List[float]] = defaultdict(list)
    for emp_id, hours in weekly_hours.items():
        emp = emp_dict.get(emp_id)
        if emp:
            role = emp.primary_role.upper()
            hours_by_role[role].append(hours)
    
    # Calculate fairness metrics
    fairness_stats = {}
    for role, hours_list in hours_by_role.items():
        if len(hours_list) > 1:
            min_hours = min(hours_list)
            max_hours = max(hours_list)
            avg_hours = sum(hours_list) / len(hours_list)
            spread = max_hours - min_hours
            
            fairness_stats[role] = {
                'min': min_hours,
                'max': max_hours,
                'avg': avg_hours,
                'spread': spread,
                'count': len(hours_list),
            }
            
            # Warning if spread is too large (> 10 hours)
            if spread > 10.0:
                results['warnings'].append(
                    f"Large hours spread for {role}: {spread:.1f}h "
                    f"(min={min_hours:.1f}h, max={max_hours:.1f}h)"
                )
    
    # 6. Statistics
    results['stats'] = {
        'total_assignments': len(assignments),
        'total_employees': len(set(assign.emp_id for assign in assignments)),
        'total_shifts': len(shifts),
        'weekly_hours': dict(weekly_hours),
        'hours_by_role': {role: sum(hours_list) for role, hours_list in hours_by_role.items()},
        'fairness': fairness_stats,
    }
    
    return results


def print_validation_report(results: Dict) -> None:
    """Print validation results in a readable format."""
    print("\n" + "=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)
    
    if results['valid']:
        print("✓ Status: VALID")
    else:
        print("✗ Status: INVALID")
    
    if results['errors']:
        print(f"\nErrors ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"  ✗ {error}")
    
    if results['warnings']:
        print(f"\nWarnings ({len(results['warnings'])}):")
        for warning in results['warnings']:
            print(f"  ⚠ {warning}")
    
    stats = results['stats']
    print(f"\nStatistics:")
    print(f"  Total assignments: {stats.get('total_assignments', 0)}")
    print(f"  Employees assigned: {stats.get('total_employees', 0)}")
    print(f"  Total shifts: {stats.get('total_shifts', 0)}")
    
    if stats.get('hours_by_role'):
        print(f"\n  Hours by role:")
        for role, total_hours in stats['hours_by_role'].items():
            print(f"    {role}: {total_hours:.1f}h")
    
    if stats.get('fairness'):
        print(f"\n  Fairness (hours distribution):")
        for role, fair_stats in stats['fairness'].items():
            print(f"    {role}:")
            print(f"      Min: {fair_stats['min']:.1f}h")
            print(f"      Max: {fair_stats['max']:.1f}h")
            print(f"      Avg: {fair_stats['avg']:.1f}h")
            print(f"      Spread: {fair_stats['spread']:.1f}h")
    
    print("=" * 70)

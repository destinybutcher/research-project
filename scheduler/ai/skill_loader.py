"""Load and average skill points from historical shift data."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd


def load_averaged_skills(csv_path: str | Path) -> Dict[int, Dict[str, float]]:
    """
    Load historical shift details and compute average skill points per employee.
    
    Args:
        csv_path: Path to shiftDetails CSV file with historical data
    
    Returns:
        Dict mapping employee_id -> skill_dict
        skill_dict contains: coffee_rating, sandwich_rating, customer_service_rating, speed_rating
        Missing skills are None
    """
    df = pd.read_csv(csv_path)
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    # Group by employee and compute mean for each skill
    employee_skills = {}
    
    for emp_id in df['emp_id'].unique():
        emp_data = df[df['emp_id'] == emp_id]
        
        skills = {
            'coffee_rating': None,
            'sandwich_rating': None,
            'customer_service_rating': None,
            'speed_rating': None,
        }
        
        # Compute averages for each skill (ignore empty/NaN values)
        for skill in skills.keys():
            if skill in emp_data.columns:
                # Filter out empty strings and NaN
                skill_values = emp_data[skill].replace('', pd.NA).dropna()
                # Convert to numeric, coercing errors to NaN
                skill_values = pd.to_numeric(skill_values, errors='coerce').dropna()
                
                if len(skill_values) > 0:
                    skills[skill] = float(skill_values.mean())
        
        employee_skills[int(emp_id)] = skills
    
    return employee_skills


def update_employee_skills_from_history(
    employees: list,
    skill_averages: Dict[int, Dict[str, float]]
) -> None:
    """
    Update Employee objects with averaged skill points from historical data.
    
    Args:
        employees: List of Employee objects (will be modified in place)
        skill_averages: Dict from load_averaged_skills()
    """
    for emp in employees:
        if emp.employee_id in skill_averages:
            skills = skill_averages[emp.employee_id]
            
            # Update only if skill is not None
            if skills['coffee_rating'] is not None:
                emp.skill_coffee = skills['coffee_rating']
            if skills['sandwich_rating'] is not None:
                emp.skill_sandwich = skills['sandwich_rating']
            if skills['customer_service_rating'] is not None:
                emp.customer_service_rating = skills['customer_service_rating']
            if skills['speed_rating'] is not None:
                emp.skill_speed = skills['speed_rating']

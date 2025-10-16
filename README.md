# ☕ AI-Assisted Café Rostering System (v2 - Refactored)

**Professional Weekly Schedule Generator with Role-Based Architecture**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Pandas](https://img.shields.io/badge/Pandas-2.0+-green.svg)](https://pandas.pydata.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)

---

## 🎯 **Overview**

This system automatically generates optimized weekly work schedules for café operations using a **role-based architecture** with **SQLAlchemy ORM** as the source of truth. Each role (MANAGER, BARISTA, WAITER, SANDWICH) has its own dedicated scheduler class, eliminating monolithic code and enabling easy extensibility.

## ✨ **Key Features**

- 🎯 **Role-specific schedulers** (clean separation of concerns)
- 🗄️ **Database-first design** (SQLite + SQLAlchemy ORM)
- ⚖️ **Fair workload distribution** with hours policy enforcement
- 📅 **Automatic weekend coverage** with manager supervision
- 🕐 **Flexible time windows** (early SANDWICH prep, staggered shifts)
- 🔄 **Synthetic week generation** for future planning
- 📊 **Comprehensive validation** and reporting
- 🛡️ **Constraint satisfaction** (no overlaps, hours caps, role eligibility)

---

## 🏗️ **Architecture (v2)**

### **Clean Separation by Role**

```
scheduler/
├── domain/                      # Data models and persistence
│   ├── models.py               # SQLAlchemy models (Employee, Shift, Assignment, Feedback)
│   ├── repositories.py         # Data access layer
│   └── db.py                   # Database initialization
├── engine/                      # Role-specific schedulers
│   ├── base.py                 # BaseScheduler (ABC)
│   ├── manager.py              # ManagerScheduler
│   ├── sandwich.py             # SandwichScheduler
│   ├── cohort.py               # CohortScheduler (BARISTA/WAITER)
│   └── orchestrator.py         # Coordinates all schedulers
├── services/                    # Shared business logic
│   ├── constraints.py          # Hard constraint checking
│   ├── scoring.py              # Employee fitness scoring
│   └── timeplan.py             # Time window resolution
├── io/                          # Import/Export utilities
│   ├── config.py               # Configuration loading
│   ├── import_csv.py           # CSV → Database
│   └── export_csv.py           # Database → CSV
├── cli_v2.py                    # New CLI interface
└── (legacy files for backward compatibility)
```

### **Key Design Principles**

1. **No role if/elif blobs** - Each role handled by dedicated class
2. **Database-first** - SQLite as source of truth, CSV for import/export only
3. **Interface-driven** - All schedulers implement `BaseScheduler`
4. **Composable** - Orchestrator assembles schedulers
5. **Testable** - Each scheduler can be unit tested independently

---

## 🚀 **Quick Start**

### **Prerequisites**

```bash
pip install pandas pyyaml sqlalchemy
```

### **Step 1: Initialize Database**

```bash
# Create database and tables
python -m scheduler.cli_v2 init-db
```

### **Step 2: Import Data**

```bash
# Import employees and shifts from CSV
python -m scheduler.cli_v2 import-csv \
  --employees ./data/employees_new_12w_v2.csv \
  --shifts ./data/shift_new_12w_v2.csv
```

### **Step 3: Generate Schedule**

```bash
# Generate schedule for week 48
python -m scheduler.cli_v2 generate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml \
  --out ./schedule_2025_week_48.csv
```

### **Step 4: Validate & Export**

```bash
# Validate generated schedule
python -m scheduler.cli_v2 validate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml

# Export assignments to CSV
python -m scheduler.cli_v2 export \
  --assignments ./schedule_2025_week_48.csv \
  --week 2025-W48
```

---

## 🧠 **Role-Specific Schedulers**

### **1. ManagerScheduler**

```python
class ManagerScheduler(BaseScheduler):
    role = "MANAGER"
    
    def make_schedule(self, session, week_id, cfg):
        # 1 manager weekdays, 2 managers weekends
        # Target: 38-40h per manager
        # Uses default shift times (07:00-15:00)
```

**Responsibilities:**
- Full-time coverage (38-40h target)
- 1 manager per weekday
- 2 managers per weekend
- Balanced hour distribution

### **2. SandwichScheduler**

```python
class SandwichScheduler(BaseScheduler):
    role = "SANDWICH"
    
    def make_schedule(self, session, week_id, cfg):
        # Early morning prep (05:00-12:00)
        # Weekend extension to 13:30
        # Target: 16-32h per employee
```

**Responsibilities:**
- Early morning shifts (05:00 start)
- Weekend prep extension
- Flexible hours (16-32h target)

### **3. CohortScheduler (BARISTA/WAITER)**

```python
class CohortScheduler(BaseScheduler):
    def __init__(self, role: str):  # "BARISTA" or "WAITER"
        self.role = role
    
    def make_schedule(self, session, week_id, cfg):
        # Weekday: single 8h shift
        # Weekend: staggered shifts (07:00-12:00, 11:00-15:00)
        # Target: 16-40h per employee
```

**Responsibilities:**
- Part-time scheduling (16-40h target)
- Weekend staggered coverage
- Shared FOH logic

### **4. Orchestrator**

```python
orchestrator = Orchestrator(order=["MANAGER", "SANDWICH", "BARISTA", "WAITER"])
assignments = orchestrator.build_schedule(session, week_id, cfg)
```

**Responsibilities:**
- Coordinate all role schedulers
- Merge assignments
- Global validation
- Persist to database

---

## 📊 **Database Schema**

### **SQLAlchemy Models**

```python
class Employee(Base):
    employee_id: int (PK)
    first_name, last_name: str
    primary_role: str  # MANAGER, BARISTA, WAITER, SANDWICH
    skill_coffee, skill_sandwich, customer_service_rating, skill_speed: float

class Shift(Base):
    shift_id: int (PK)
    date: date
    week_id: str

class Assignment(Base):
    id: int (PK, autoincrement)
    shift_id: int (FK)
    emp_id: int (FK)
    start_time, end_time: datetime (timezone-aware)
    role, shift_type, day_type: str

class Feedback(Base):
    id: int (PK, autoincrement)
    week_id, date, shift_id, emp_id, role: ...
    overall_service_rating: int (1-5)
    traffic_level: str (quiet, normal, busy)
    comment, tags: str
    submitted_at: datetime
```

---

## 🎯 **Usage Examples**

### **Complete Workflow**

```bash
# 1. Initialize database
python -m scheduler.cli_v2 init-db

# 2. Import existing data
python -m scheduler.cli_v2 import-csv \
  --employees ./data/employees_new_12w_v2.csv \
  --shifts ./data/shift_new_12w_v2.csv

# 3. Generate schedule
python -m scheduler.cli_v2 generate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml \
  --out ./schedule_2025_week_48.csv

# 4. Validate
python -m scheduler.cli_v2 validate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml

# 5. Export
python -m scheduler.cli_v2 export \
  --assignments ./final_schedule.csv \
  --week 2025-W48
```

### **Custom Database**

```bash
# Use PostgreSQL instead of SQLite
python -m scheduler.cli_v2 --db postgresql://user:pass@localhost/scheduler generate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml
```

---

## 🔧 **Extending the System**

### **Adding a New Role**

```python
# 1. Create new scheduler class
from scheduler.engine.base import BaseScheduler

class BaristaTraineeScheduler(BaseScheduler):
    role = "BARISTA_TRAINEE"
    
    def make_schedule(self, session, week_id, cfg):
        # Your custom logic here
        return assignments

# 2. Add to orchestrator
orchestrator = Orchestrator(order=["MANAGER", "SANDWICH", "BARISTA", "WAITER", "BARISTA_TRAINEE"])
```

**No modifications needed to:**
- ❌ Other schedulers
- ❌ Orchestrator code
- ❌ Database models
- ❌ Validation logic

---

## 📈 **Benefits of v2 Architecture**

### **vs. v1 Monolithic Design:**

| Aspect | v1 (Monolithic) | v2 (Role-Based) |
|--------|-----------------|-----------------|
| **Code Organization** | Single 400-line function | 4 focused classes |
| **Role Logic** | if/elif blobs | Dedicated schedulers |
| **Testability** | Hard to isolate | Easy unit tests |
| **Extensibility** | Modify core function | Add new class |
| **Maintainability** | Complex nested loops | Clear separation |
| **Data Source** | CSV-first | Database-first (ORM) |

### **Advantages:**

- ✅ **Cleaner code**: Each scheduler ~100 lines vs 400-line monolith
- ✅ **Easier testing**: Test each role independently
- ✅ **Better extensibility**: Add roles without touching existing code
- ✅ **Database-backed**: Proper persistence and querying
- ✅ **ORM benefits**: Type safety, migrations, relationships

---

## 🛠️ **Development**

### **Running Tests**

```bash
# Run all tests
python -m pytest tests/

# Test specific scheduler
python -m pytest tests/test_manager_scheduler.py
```

### **Database Management**

```bash
# Reset database (WARNING: deletes all data)
python -c "from scheduler.domain.db import reset_database; reset_database()"

# Backup database
cp scheduler.db scheduler_backup_$(date +%Y%m%d).db
```

---

## 📝 **Migration Guide (v1 → v2)**

### **For Existing Users:**

```bash
# 1. Keep your existing v1 system working
#    (old CLI still available as scheduler.cli)

# 2. Initialize v2 database
python -m scheduler.cli_v2 init-db

# 3. Import your CSV data
python -m scheduler.cli_v2 import-csv \
  --employees ./data/employees_new_12w_v2.csv \
  --shifts ./data/shift_new_12w_v2.csv

# 4. Generate with v2 architecture
python -m scheduler.cli_v2 generate \
  --week 2025-W48 \
  --config ./scheduler_config.yaml \
  --out ./schedule_v2.csv

# 5. Compare outputs
#    Both should produce valid schedules!
```

---

## 🎉 **Summary**

The v2 refactored architecture provides:

- **Clean role separation** - No more nested if/elif blocks
- **Database-first design** - SQLAlchemy ORM for proper persistence
- **Extensible architecture** - Add new roles without modifying existing code
- **Better testing** - Unit test each scheduler independently
- **Production ready** - Proper data modeling and migrations

**Ready to optimize your café scheduling with clean, maintainable code!** 🚀

---

## 📞 **Support**

For questions or support, please open an issue on GitHub or contact the development team.

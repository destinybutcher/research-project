"""Configuration loading utility (reuses existing config.py)."""

# Re-export from original config module
from scheduler.config import load_config, SchedulerConfig

__all__ = ["load_config", "SchedulerConfig"]


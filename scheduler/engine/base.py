"""Base scheduler interface that all role-specific schedulers must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.orm import Session

from scheduler.domain.models import Assignment


class BaseScheduler(ABC):
    """
    Abstract base class for all role-specific schedulers.
    
    Each scheduler is responsible for generating assignments for a specific role
    (or group of roles) for a given week.
    """
    
    role: str | None = None  # Override in subclasses (e.g., "MANAGER", "SANDWICH")
    
    @abstractmethod
    def make_schedule(
        self,
        session: Session,
        week_id: str,
        cfg,
    ) -> List[Assignment]:
        """
        Generate assignments for this scheduler's role(s) for the specified week.
        
        Args:
            session: Database session for data access
            week_id: ISO week identifier (e.g., "2025-W36")
            cfg: SchedulerConfig with business rules
        
        Returns:
            List of Assignment objects (not yet persisted to database)
        
        Raises:
            RuntimeError: If scheduling fails due to insufficient staff or constraints
        """
        pass
    
    def get_role_name(self) -> str:
        """Get the role this scheduler handles."""
        return self.role or "UNKNOWN"


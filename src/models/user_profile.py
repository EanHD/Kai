"""User profile model with preferences, schedules, and goals."""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import List, Optional, Dict, Any
import uuid


@dataclass
class Schedule:
    """User schedule entry."""
    name: str  # e.g., "sleep", "work"
    start_time: time
    end_time: time
    days: List[int]  # 0=Monday, 6=Sunday
    
    def is_active_on_day(self, day: int) -> bool:
        """Check if schedule is active on given day."""
        return day in self.days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "days": self.days,
        }


@dataclass
class Goal:
    """User goal with tracking."""
    name: str
    target_value: float
    current_value: float
    unit: str  # e.g., "USD", "hours", "kg"
    deadline: Optional[datetime] = None
    
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.target_value == 0:
            return 0.0
        return (self.current_value / self.target_value) * 100
    
    def is_on_track(self) -> bool:
        """Check if goal is on track."""
        return self.current_value >= self.target_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "unit": self.unit,
            "deadline": self.deadline.isoformat() if self.deadline else None,
        }


@dataclass
class UserProfile:
    """User profile with preferences, schedules, and goals."""
    
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    preferences: Dict[str, Any] = field(default_factory=dict)
    schedules: List[Schedule] = field(default_factory=list)
    goals: List[Goal] = field(default_factory=list)
    encryption_key_hash: str = ""
    
    def add_schedule(self, schedule: Schedule) -> None:
        """Add a schedule."""
        self.schedules.append(schedule)
        self.updated_at = datetime.utcnow()
    
    def add_goal(self, goal: Goal) -> None:
        """Add a goal."""
        self.goals.append(goal)
        self.updated_at = datetime.utcnow()
    
    def update_preference(self, key: str, value: Any) -> None:
        """Update a preference."""
        self.preferences[key] = value
        self.updated_at = datetime.utcnow()
    
    def get_schedule_by_name(self, name: str) -> Optional[Schedule]:
        """Get schedule by name."""
        for schedule in self.schedules:
            if schedule.name.lower() == name.lower():
                return schedule
        return None
    
    def get_goal_by_name(self, name: str) -> Optional[Goal]:
        """Get goal by name."""
        for goal in self.goals:
            if goal.name.lower() == name.lower():
                return goal
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "preferences": self.preferences,
            "schedules": [s.to_dict() for s in self.schedules],
            "goals": [g.to_dict() for g in self.goals],
            "encryption_key_hash": self.encryption_key_hash,
        }

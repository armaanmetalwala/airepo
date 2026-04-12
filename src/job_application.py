from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from src.job import Job


@dataclass
class JobApplication:
    """Answers and artifacts for one job application."""

    job: Job
    application: Dict[str, Any] = field(default_factory=dict)
    resume_path: str = ""
    cover_letter_path: str = ""

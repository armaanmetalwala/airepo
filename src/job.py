from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from src.logging import logger


def _stable_job_id(link: str) -> str:
    if not link:
        return str(uuid.uuid4())[:10]
    m = re.search(r"/jobs/view/(\d+)", link)
    if m:
        return m.group(1)
    return str(abs(hash(link)) % 10_000_000_000)


@dataclass
class Job:
    role: str = ""
    company: str = ""
    location: str = ""
    link: str = ""
    apply_method: str = ""
    description: str = ""
    summarize_job_description: str = ""
    recruiter_link: str = ""
    resume_path: str = ""
    cover_letter_path: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = _stable_job_id(self.link)

    @property
    def title(self) -> str:
        return self.role

    def set_summarize_job_description(self, text: str) -> None:
        self.summarize_job_description = text

    def formatted_job_information(self):
        """
        Formats the job information as a markdown string.
        """
        logger.debug(f"Formatting job information for job: {self.role} at {self.company}")
        job_information = f"""
        # Job Description
        ## Job Information 
        - Position: {self.role}
        - At: {self.company}
        - Location: {self.location}
        - Recruiter Profile: {self.recruiter_link or 'Not available'}
        
        ## Description
        {self.description or 'No description provided.'}
        """
        formatted_information = job_information.strip()
        logger.debug(f"Formatted job information: {formatted_information}")
        return formatted_information

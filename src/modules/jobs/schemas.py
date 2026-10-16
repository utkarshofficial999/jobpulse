from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RemoteType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    INTERN = "intern"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    EXECUTIVE = "executive"
    UNSPECIFIED = "unspecified"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class NormalizedJob(BaseModel):
    external_id: str
    title: str
    company: str
    locations: list[str] = Field(default_factory=list)
    remote_type: RemoteType = RemoteType.UNKNOWN
    seniority: Seniority = Seniority.UNSPECIFIED
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    description: str
    apply_url: str
    posted_at: Optional[datetime] = None

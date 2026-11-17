from enum import Enum
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class Status(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"


class Finding(BaseModel):
    section: str
    category: str
    finding: str
    severity: Severity
    evidence_quote: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    regulation_ref: str | None = None
    source: str = "llm"
    evidence_verified: bool | None = None
    status: Status = Status.PENDING

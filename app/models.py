from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Finding(BaseModel):
    category: str
    severity: Severity
    title: str
    description: str
    file: str
    line: int | None = None
    suggestion: str | None = None


class PullRequestFile(BaseModel):
    filename: str
    status: str
    patch: str = ""


class ReviewReport(BaseModel):
    summary: str
    score: int = Field(ge=0, le=100)
    findings: list[Finding]


class PullRequestContext(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str = ""
    files: list[PullRequestFile]

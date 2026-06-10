from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class ReviewCategory(StrEnum):
    security = "security"
    performance = "performance"
    maintainability = "maintainability"
    quality = "quality"


class RepositoryRef(BaseModel):
    owner: str
    name: str
    full_name: str
    clone_url: HttpUrl | None = None
    default_branch: str = "main"


class PullRequestFile(BaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str = ""
    raw_url: str | None = None
    contents_url: str | None = None


class PullRequestContext(BaseModel):
    owner: str
    repo: str
    number: int
    title: str
    body: str = ""
    base_sha: str = ""
    head_sha: str = ""
    author: str = ""
    files: list[PullRequestFile] = Field(default_factory=list)
    repository: RepositoryRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    structure: list[str] = Field(default_factory=list)


class CodeChunk(BaseModel):
    id: str
    repository: str
    path: str
    language: str
    start_line: int
    end_line: int
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedContext(BaseModel):
    path: str
    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewFinding(BaseModel):
    category: ReviewCategory
    severity: Severity
    title: str
    description: str
    file: str
    line: int | None = None
    suggested_fix: str | None = None
    patch: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class AgentReview(BaseModel):
    agent: str
    summary: str
    findings: list[ReviewFinding] = Field(default_factory=list)


class ReviewReport(BaseModel):
    executive_summary: str
    security_summary: str = "No security issues found."
    performance_summary: str = "No performance issues found."
    maintainability_summary: str = "No maintainability issues found."
    suggested_fixes: list[str] = Field(default_factory=list)
    score: int = Field(ge=0, le=100)
    findings: list[ReviewFinding] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    owner: str
    repo: str
    pull_number: int


class ReindexRequest(BaseModel):
    owner: str
    repo: str
    branch: str | None = None


class StatusResponse(BaseModel):
    status: str
    indexed_repositories: list[str] = Field(default_factory=list)
    version: str

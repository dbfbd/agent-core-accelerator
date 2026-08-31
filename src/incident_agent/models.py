"""Validated data models at the incident-agent input boundary."""

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class IncidentRequest(BaseModel):
    """A validated request to investigate one service incident."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    service: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ServiceWindowQuery(BaseModel):
    """Fields shared by read-only service queries."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    service: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9-]*$")
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def end_must_follow_start(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        return self


class MetricsQuery(ServiceWindowQuery):
    """Input for service metric queries."""


class LogSearchQuery(ServiceWindowQuery):
    """Input for case-insensitive log searches."""

    query: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=100)


class DeploymentQuery(ServiceWindowQuery):
    """Input for recent deployment queries."""


class MetricPoint(BaseModel):
    """One service metric sample."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    timestamp: AwareDatetime
    request_count: int = Field(ge=0)
    error_rate: float = Field(ge=0, le=1)
    p95_latency_ms: int = Field(ge=0)


class ServiceMetrics(BaseModel):
    """Metric points returned for one service and time window."""

    service: str
    start: AwareDatetime
    end: AwareDatetime
    points: list[MetricPoint]


type LogLevel = Literal["INFO", "WARNING", "ERROR"]


class LogEntry(BaseModel):
    """One searchable log entry."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    timestamp: AwareDatetime
    level: LogLevel
    message: str


class LogSearchResult(BaseModel):
    """Matching logs returned for one query."""

    service: str
    query: str
    entries: list[LogEntry]


type DeploymentStatus = Literal["succeeded", "failed"]


class DeploymentRecord(BaseModel):
    """One deployment record."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    timestamp: AwareDatetime
    version: str
    commit_sha: str
    status: DeploymentStatus


class RecentDeployments(BaseModel):
    """Deployments returned for one service and time window."""

    service: str
    deployments: list[DeploymentRecord]

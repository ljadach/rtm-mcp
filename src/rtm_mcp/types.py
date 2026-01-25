"""RTM MCP Pydantic models for type safety."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RTMTask(BaseModel):
    """A single task instance."""

    id: str
    taskseries_id: str
    list_id: str
    name: str
    due: str | None = None
    has_due_time: bool = False
    completed: str | None = None
    deleted: str | None = None
    priority: str = "N"
    postponed: int = 0
    estimate: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)
    url: str | None = None
    location_id: str | None = None
    parent_task_id: str | None = None
    created: str | None = None
    modified: str | None = None


class RTMList(BaseModel):
    """An RTM list."""

    id: str
    name: str
    deleted: bool = False
    locked: bool = False
    archived: bool = False
    position: int = -1
    smart: bool = False
    sort_order: int | None = None


class RTMNote(BaseModel):
    """A note attached to a task."""

    id: str
    title: str = ""
    body: str = ""
    created: str | None = None
    modified: str | None = None


class RTMLocation(BaseModel):
    """A location."""

    id: str
    name: str
    longitude: float
    latitude: float
    zoom: int | None = None
    address: str | None = None
    viewable: bool = True


class RTMTag(BaseModel):
    """A tag with usage count."""

    name: str
    count: int = 0


class RTMContact(BaseModel):
    """A contact for task sharing."""

    id: str
    fullname: str
    username: str


class RTMGroup(BaseModel):
    """A contact group."""

    id: str
    name: str
    contacts: list[str] = Field(default_factory=list)


class RTMSettings(BaseModel):
    """User settings."""

    timezone: str
    dateformat: int  # 0=European, 1=American
    timeformat: int  # 0=12-hour, 1=24-hour
    defaultlist: str | None = None
    language: str | None = None


class TaskIdentifier(BaseModel):
    """Identifies a task for operations."""

    list_id: str
    taskseries_id: str
    task_id: str


class ResponseMetadata(BaseModel):
    """Metadata included in all responses."""

    fetched_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    transaction_id: str | None = None


class RTMResponse(BaseModel):
    """Standard response wrapper."""

    data: dict[str, Any]
    analysis: dict[str, Any] | None = None
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)

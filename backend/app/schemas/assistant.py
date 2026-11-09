from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class AssistantCourseOut(BaseModel):
    course_id: int
    code: str
    name: str
    indexed_materials: int   # 0 = the assistant has nothing to answer from yet


class SessionCreate(BaseModel):
    course_id: int
    title: Optional[str] = Field(default=None, max_length=255)


class SessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class SessionOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Citation(BaseModel):
    n: int
    material_id: int
    title: str
    section: Optional[str] = None
    location: str            # e.g. "slides 4-6"
    location_type: str
    location_start: int
    location_end: int
    snippet: str

    # Derived, so citations saved before T84 carry them too
    @computed_field
    @property
    def file_url(self) -> str:
        """API path that streams the cited file (FR-809)."""
        return f"/student/assistant/materials/{self.material_id}/file"

    @computed_field
    @property
    def open_page(self) -> int:
        """Page or slide (see location_type) to open the file at."""
        return self.location_start


class MessageOut(BaseModel):
    id: int
    role: str                # user | assistant
    content: str
    citations: list[Citation] = []
    source_type: Optional[str] = None   # course | general | refused (assistant messages)
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MaterialOut(BaseModel):
    id: int
    title: str
    file_name: str
    section_name: Optional[str]
    status: str              # pending | indexed | no_text | unsupported | error
    error_text: Optional[str]
    unit_count: Optional[int]
    chunk_count: int
    indexed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SyncOut(BaseModel):
    course_code: str
    added: int
    updated: int
    unchanged: int
    deleted: int
    failed: list[str]
    statuses: dict[str, int]

from datetime import datetime
from typing import Literal, Optional

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
    kind: str = "chat"       # chat | summary | study_guide | flashcards | practice_questions
    payload: Optional[dict] = None      # study tool data (cards / questions / last_score)
    topic: Optional[str] = None         # short topic label (assistant messages), e.g. for videos

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


class ChatToolCreate(BaseModel):
    """A study tool run inside a chat; the result is saved as a chat message."""
    kind: Literal["summary", "study_guide", "flashcards", "practice_questions"]
    topic: str = Field(min_length=1, max_length=200)


class PracticeScore(BaseModel):
    correct: int = Field(ge=0)
    total: int = Field(ge=1)


# ── LLM JSON output validation (internal; the endpoint validates the LLM's JSON) ──

class LLMCard(BaseModel):
    front: str
    back: str
    citation: Optional[int] = None


class LLMQuestion(BaseModel):
    stem: str
    options: list[str]
    answer: str
    explanation: str
    citation: Optional[int] = None


class LLMCards(BaseModel):
    cards: list[LLMCard] = []


class LLMQuestions(BaseModel):
    questions: list[LLMQuestion] = []


# ── API response ──────────────────────────────────────────────────────────────

class FlashcardOut(BaseModel):
    front: str
    back: str
    citation: Optional[Citation] = None


class PracticeQuestionOut(BaseModel):
    stem: str
    options: list[str]
    answer: str
    explanation: str
    citation: Optional[Citation] = None


class TopicCount(BaseModel):
    topic: str
    students: int


class MaterialCount(BaseModel):
    material_id: int
    title: str
    students: int


class TrendsOut(BaseModel):
    most_asked_topics: list[TopicCount]
    most_cited_materials: list[MaterialCount]
    topics_materials_dont_cover: list[TopicCount]


class BeforeClassOut(BaseModel):
    content: str                  # markdown note, or the "not enough questions yet" message
    citations: list[Citation] = []
    not_enough_data: bool = False


class YoutubeVideo(BaseModel):
    video_id: str
    title: str
    channel: str
    url: str
    thumbnail_url: Optional[str] = None


class YoutubeCreate(BaseModel):
    course_id: int
    topic: str = Field(min_length=1, max_length=200)


class YoutubeOut(BaseModel):
    enabled: bool                 # False when YOUTUBE_API_KEY is not configured
    videos: list[YoutubeVideo] = []
    keywords: list[str] = []

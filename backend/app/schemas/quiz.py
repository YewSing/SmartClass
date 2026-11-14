from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class GenerateQuizRequest(BaseModel):
    material_ids: list[int] = Field(min_length=1)
    type: str = Field(pattern="^(mcq|short_answer)$")
    level: str = Field(pattern="^(beginner|intermediate|advanced)$")
    count: int = Field(ge=1, le=50)


class GeneratedQuestion(BaseModel):
    """Shape the LLM must return when drafting one question (chat_json, validated)."""

    question: str
    options: list[str] = []
    correct_answer: Optional[str] = None
    suggested_answer: Optional[str] = None
    level: str
    topic: str

    @field_validator("level")
    @classmethod
    def _level(cls, v: str) -> str:
        if v not in ("beginner", "intermediate", "advanced"):
            raise ValueError("level must be beginner, intermediate or advanced")
        return v

    @field_validator("options")
    @classmethod
    def _options(cls, v: list[str]) -> list[str]:
        return [o.strip() for o in v if o.strip()]


class QuizQuestionOut(BaseModel):
    id: int
    quiz_id: Optional[int] = None
    course_id: int
    type: str
    question: str
    options: Optional[list[str]] = None
    correct_answer: Optional[str] = None
    suggested_answer: Optional[str] = None
    level: str
    source_material_id: Optional[int] = None
    topic: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── draft question lifecycle / publish (FR-604, FR-605, S31) ───────────────

class EditQuizQuestionRequest(BaseModel):
    question: Optional[str] = Field(None, min_length=1, max_length=2000)
    options: Optional[list[str]] = Field(None, min_length=2, max_length=5)
    correct_answer: Optional[str] = None
    suggested_answer: Optional[str] = None
    level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    topic: Optional[str] = Field(None, max_length=255)


class QuizOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    status: str
    created_by: int
    created_at: Optional[datetime] = None
    question_count: int = 0

    model_config = {"from_attributes": True}


class PublishQuizRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None


# ── taking quizzes + auto-grade (FR-606, FR-607, FR-608, S32) ───────────────
class StudentQuizOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    status: str
    has_attempt: bool = False
    attempt_id: Optional[int] = None
    deadline: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StartAttemptOut(BaseModel):
    attempt_id: int
    started_at: datetime
    deadline: datetime

    model_config = {"from_attributes": True}


class AnswerInput(BaseModel):
    question_id: int
    answer: Optional[str] = None


class SubmitAttemptRequest(BaseModel):
    answers: list[AnswerInput] = []


class QuizAnswerOut(BaseModel):
    question_id: int
    answer: Optional[str] = None
    score: Optional[float] = None
    auto_graded: bool

    model_config = {"from_attributes": True}


class SubmitAttemptOut(BaseModel):
    attempt_id: int
    status: str
    score: Optional[float] = None
    auto_submitted: bool
    answers: list[QuizAnswerOut] = []

    model_config = {"from_attributes": True}


# ── short-answer scoring + AI suggestion (FR-609, FR-610, FR-611, S33) ──────

class ScoreShortAnswerIn(BaseModel):
    score: float = Field(ge=0, le=100)


class SuggestScoreOut(BaseModel):
    suggested_score: float
    reasoning: Optional[str] = None


class QuizAttemptResultOut(BaseModel):
    attempt_id: int
    status: str
    score: Optional[float] = None
    auto_submitted: bool
    grading_complete: bool
    student_score_visible: bool
    answers: list[QuizAnswerOut] = []

    model_config = {"from_attributes": True}


class QuizAttemptSummaryOut(BaseModel):
    attempt_id: int
    student_id: int
    student_name: Optional[str] = None
    status: str
    score: Optional[float] = None
    auto_submitted: bool
    grading_complete: bool
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

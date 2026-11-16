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
    score: float = 1.0
    learning_hint: Optional[str] = None
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
    score: Optional[float] = Field(None, ge=0.1, le=100.0)


class QuizOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    attempts_allowed: int = 1
    review_visible: bool = True
    status: str
    created_by: int
    created_at: Optional[datetime] = None
    question_count: int = 0
    attempt_count: int = 0
    total_enrolled: Optional[int] = None

    model_config = {"from_attributes": True}


class PublishQuizRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1)
    title: Optional[str] = Field(None, max_length=255)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    attempts_allowed: int = Field(1, ge=1, le=10)
    review_visible: bool = True
    # Publish to additional courses too (one quiz per course, questions cloned).
    # The questions' own course is always included.
    course_ids: list[int] = Field(default_factory=list)


# ── draft quiz sets (S35: QuizList "Draft" + CreateQuiz "Save as draft") ─────

class SaveQuizDraftRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1)
    title: Optional[str] = Field(None, max_length=255)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    attempts_allowed: int = Field(1, ge=1, le=10)
    review_visible: bool = True


class UpdateQuizDraftRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    attempts_allowed: Optional[int] = Field(None, ge=1, le=10)
    review_visible: Optional[bool] = None
    question_ids: Optional[list[int]] = None


class PublishDraftQuizRequest(BaseModel):
    course_ids: list[int] = Field(default_factory=list)


# ── manual question add (review/edit/add flow, S35) ─────────────────────────

class CreateQuizQuestionRequest(BaseModel):
    course_id: int
    type: str = Field(pattern="^(mcq|short_answer)$")
    question: str = Field(min_length=1, max_length=2000)
    options: Optional[list[str]] = Field(None, min_length=2, max_length=5)
    correct_answer: Optional[str] = None
    suggested_answer: Optional[str] = None
    level: str = Field(pattern="^(beginner|intermediate|advanced)$")
    topic: Optional[str] = Field(None, max_length=255)
    score: float = Field(1.0, ge=0.1, le=100.0)


# ── LLM quick-add: "create 5 mcq, 2 short answer, 15min, valid two days" ────

class QuickAddRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    material_ids: list[int] = Field(default_factory=list)
    level: str = Field("intermediate", pattern="^(beginner|intermediate|advanced)$")


class QuickAddSpec(BaseModel):
    """Shape the LLM must return when parsing the lecturer's quick-add sentence."""

    title: Optional[str] = None
    mcq_count: int = Field(0, ge=0, le=50)
    short_answer_count: int = Field(0, ge=0, le=50)
    time_limit_minutes: Optional[int] = Field(None, ge=1, le=600)
    valid_days: Optional[int] = Field(None, ge=0, le=365)
    attempts_allowed: int = Field(1, ge=1, le=10)
    review_visible: bool = True

    @field_validator("mcq_count", "short_answer_count")
    @classmethod
    def _sum_nonzero(cls, v):
        return v


# ── taking quizzes + auto-grade (FR-606, FR-607, FR-608, S32) ───────────────
class StudentQuizOut(BaseModel):
    id: int
    course_id: int
    title: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    opens_at: Optional[datetime] = None
    closes_at: Optional[datetime] = None
    attempts_allowed: int = 1
    attempts_used: int = 0
    review_visible: bool = True
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
    max_score: Optional[float] = 1.0
    auto_graded: bool
    # per-question fields on the student result endpoint (hidden when review is off)
    question: Optional[str] = None
    type: Optional[str] = None
    options: Optional[list[str]] = None
    correct_answer: Optional[str] = None
    suggested_answer: Optional[str] = None
    learning_hint: Optional[str] = None

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
    percentage_score: Optional[float] = None
    raw_score: Optional[float] = None
    max_score: Optional[float] = None
    auto_submitted: bool
    grading_complete: bool
    student_score_visible: bool
    review_visible: bool = True
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
    total_enrolled: Optional[int] = None

    model_config = {"from_attributes": True}

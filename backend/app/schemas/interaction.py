from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class InteractionQuestionOut(BaseModel):
    id: int
    interaction_id: int
    text: str
    anonymous: bool
    answered: bool
    created_at: datetime
    # student_id / student_name are always stored but stripped from the response when
    # anonymous (FR-503). Populated only for non-anonymous questions.
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    answered_by: Optional[int] = None
    answered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AskQuestionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    anonymous: bool = False


class InteractionPollOptionOut(BaseModel):
    id: int
    poll_id: int
    option_text: str
    position: int
    votes: int = 0

    model_config = {"from_attributes": True}


class InteractionPollOut(BaseModel):
    id: int
    interaction_id: int
    question: str
    is_open: bool
    opened_by: int
    opened_at: datetime
    closed_by: Optional[int] = None
    closed_at: Optional[datetime] = None
    options: list[InteractionPollOptionOut] = []

    model_config = {"from_attributes": True}


class CreatePollRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=10)


class VoteRequest(BaseModel):
    option_id: int


# ── live question / reaction / IDU (FR-506, FR-507, FR-508, FR-509 part) ──────

# Predefined reaction set students may send (FR-507).
REACTION_SET = ("confused", "pace_too_fast", "pace_too_slow", "understood", "agree")


class InteractionLiveQuestionResponseOut(BaseModel):
    id: int
    live_question_id: int
    student_id: int
    student_name: str
    response: str
    responded_at: datetime

    model_config = {"from_attributes": True}


class InteractionLiveQuestionOut(BaseModel):
    id: int
    interaction_id: int
    question: str
    asked_by: int
    asked_at: datetime
    is_active: bool
    responses: list[InteractionLiveQuestionResponseOut] = []

    model_config = {"from_attributes": True}


class AskLiveQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class RespondLiveQuestionRequest(BaseModel):
    response: str = Field(min_length=1, max_length=2000)


class ReactionCountOut(BaseModel):
    reaction: str
    count: int            # distinct students currently sending this reaction


class SendReactionRequest(BaseModel):
    reaction: str


class InteractionIDUOut(BaseModel):
    distinct_students: int
    has_signal: bool      # whether the requesting student has already signalled


class SendIDURequest(BaseModel):
    pass


# ── student view of an open interaction (FR-502, FR-504, FR-506, FR-507, FR-508) ──


class StudentPollOptionOut(BaseModel):
    id: int
    option_text: str
    votes: int = 0


class StudentPollOut(BaseModel):
    id: int
    question: str
    is_open: bool = True
    my_option_id: Optional[int] = None
    options: list[StudentPollOptionOut] = []

    model_config = {"from_attributes": True}


class StudentLiveQuestionOut(BaseModel):
    id: int
    question: str
    is_active: bool = True
    my_response: Optional[str] = None

    model_config = {"from_attributes": True}


class StudentInteractionOut(BaseModel):
    id: int
    occurrence_id: int
    class_code: str
    class_name: str
    status: str
    opened_at: Optional[datetime] = None
    closed_by: Optional[int] = None
    closed_at: Optional[datetime] = None
    current_poll: Optional[StudentPollOut] = None
    live_question: Optional[StudentLiveQuestionOut] = None

    model_config = {"from_attributes": True}


class StudentInteractionStateOut(StudentInteractionOut):
    """Everything one student needs to paint an interaction screen (FR-502–FR-508)."""

    my_reaction: Optional[str] = None
    reaction_counts: dict[str, int] = {}
    idu_distinct_students: int = 0
    idu_has_signal: bool = False
    my_questions: list[InteractionQuestionOut] = []


class OpenInteractionRequest(BaseModel):
    occurrence_id: int



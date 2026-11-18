"""Student participation-history schemas (FR-509 read side, feeds the student app's
Participation summary screens). Read-only views over the interaction tables."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ParticipationSessionOut(BaseModel):
    """One interaction session the student took part in, with their own activity counts."""

    id: int
    occurrence_id: int
    class_code: str
    class_name: str
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    # The student's own counts in this session (FR-509)
    questions: int
    votes: int
    responses: int
    reactions: int
    idu_signals: int


class ParticipationPollItemOut(BaseModel):
    """A poll of the session with the class distribution and this student's choice."""

    id: int
    question: str
    is_open: bool
    my_option: Optional[str] = None
    options: list["ParticipationPollOptionOut"] = []


class ParticipationPollOptionOut(BaseModel):
    option_text: str
    votes: int


class ParticipationLiveItemOut(BaseModel):
    """A live question the lecturer asked and this student's response (if any)."""

    id: int
    question: str
    my_response: Optional[str] = None


class ParticipationQuestionItemOut(BaseModel):
    """A question the student asked in the session."""

    id: int
    text: str
    anonymous: bool
    answered: bool


class ParticipationSessionDetailOut(BaseModel):
    """Full participation detail of one session for the requesting student."""

    id: int
    occurrence_id: int
    class_code: str
    class_name: str
    status: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    stats: "ParticipationStatsOut"
    class_participants: int
    polls: list[ParticipationPollItemOut] = []
    live_questions: list[ParticipationLiveItemOut] = []
    my_questions: list[ParticipationQuestionItemOut] = []


class ParticipationStatsOut(BaseModel):
    questions: int
    votes: int
    responses: int
    reactions: int
    idu_signals: int

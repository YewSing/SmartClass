from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    anonymous: bool = False

    @field_validator("text")
    @classmethod
    def trim_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank")
        return value


class QuestionModerate(BaseModel):
    answered: bool | None = None
    pinned: bool | None = None
    hidden: bool | None = None

    @model_validator(mode="after")
    def at_least_one(self):
        if self.answered is None and self.pinned is None and self.hidden is None:
            raise ValueError("Provide at least one moderation change")
        return self


class PollCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=2, max_length=6)
    multiple: bool = False
    show_results: bool = False

    @field_validator("prompt")
    @classmethod
    def trim_prompt(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Poll prompt cannot be blank")
        return value

    @field_validator("options")
    @classmethod
    def clean_options(cls, values):
        cleaned = [v.strip() for v in values]
        if any(not v or len(v) > 255 for v in cleaned):
            raise ValueError("Poll options must contain 1-255 characters")
        if len({v.casefold() for v in cleaned}) != len(cleaned):
            raise ValueError("Poll options must be unique")
        return cleaned


class PollVisibility(BaseModel):
    show_results: bool


class PollVote(BaseModel):
    option_indexes: list[int] = Field(min_length=1, max_length=6)


class QuickPromptCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    max_length: int | None = Field(default=None, ge=1, le=1000)

    @field_validator("prompt")
    @classmethod
    def trim_prompt(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Quick question cannot be blank")
        return value


class QuickAnswerCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

    @field_validator("text")
    @classmethod
    def trim_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Answer cannot be blank")
        return value


class ReactionCreate(BaseModel):
    kind: Literal["thumbs_up", "clear", "too_fast", "too_slow"]


class ConfusionCreate(BaseModel):
    topic_tag: str | None = Field(default=None, max_length=100)

    @field_validator("topic_tag")
    @classmethod
    def trim_topic(cls, value):
        return value.strip() or None if value is not None else None


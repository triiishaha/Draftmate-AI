from typing import Optional
from pydantic import BaseModel, Field


class DraftRequest(BaseModel):
    skill_id: str
    instruction: str
    inputs: dict = Field(default_factory=dict)
    source_text: Optional[str] = None
    reference_text: Optional[str] = None
    context_chunks: list[str] = Field(default_factory=list)
    model: str = "default"


class Change(BaseModel):
    description: str
    location: Optional[str] = None


class DraftResult(BaseModel):
    skill_id: str
    draft_md: str
    changes: list[Change] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
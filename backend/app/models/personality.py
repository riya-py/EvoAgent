"""
Personality schema — Phase 2.

Deliberately has NO model field. The spec is explicit that
MODEL != PERSONALITY: a personality describes *how* an agent behaves,
a model provides the *capability* to generate text. The mapping between
the two lives in app/model_assignment.py, not here.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Personality(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    specialties: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    # Evolution lineage fields (used from Phase 10 onward). Generation 0
    # personalities are the original 8 and have no parent.
    generation: int = 0
    parent_agent: Optional[str] = None
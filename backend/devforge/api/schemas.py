"""
Pydantic response models for the DevForge API.

These are serialisation models only — separate from the SQLModel DB tables.
All fields reflect objective data sources; LLM-generated informational fields
(estimated_effort, expected_impact) are clearly annotated.
No estimated_manual_minutes.
"""
import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class RepositoryOut(BaseModel):
    id: str
    name: str
    path: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RepositorySnapshotOut(BaseModel):
    id: str
    repository_id: str
    taken_at: datetime
    snapshot_type: str

    # Objective metrics
    file_count: int
    test_file_count: int
    test_function_count: int
    todo_count: int
    lint_error_count: int
    documented_functions_pct: float

    # JSON fields — exposed as parsed types in the response
    languages: dict
    top_issues: list[str]
    analysis_summary: str

    model_config = {"from_attributes": True}

    @field_validator("languages", mode="before")
    @classmethod
    def parse_languages(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v or {}

    @field_validator("top_issues", mode="before")
    @classmethod
    def parse_top_issues(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []


class MissionOut(BaseModel):
    id: str
    repository_id: str
    title: str
    problem: str
    mission_type: str
    affected_files: list[str]
    priority: str
    estimated_effort: str   # informational only — LLM-generated text
    expected_impact: str    # informational only — LLM-generated text
    status: str
    verification_requirements: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("affected_files", mode="before")
    @classmethod
    def parse_affected_files(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

    @field_validator("verification_requirements", mode="before")
    @classmethod
    def parse_verification_requirements(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

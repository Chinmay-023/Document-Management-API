from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional
from enum import Enum


class PriorityEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskEnum(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


# ==========================================
# TEST CASE SCHEMA (LLM GENERATED)
# ==========================================

class TestCase(BaseModel):
    test_id: str = Field(..., description="Unique code (e.g. TC-001) for the test case")
    title: str = Field(..., min_length=1, description="Descriptive title of what is being tested")
    requirement_ref: str = Field(..., description="Title or header index of source requirement node")
    preconditions: List[str] = Field(..., description="Preconditions required before starting test execution")
    steps: List[str] = Field(..., description="Sequential list of actions to perform during test")
    expected_result: str = Field(..., description="Expected outcome to declare success")
    priority: PriorityEnum = Field(..., description="Level of test execution precedence")
    risk: RiskEnum = Field(..., description="Level of medical/product hazard impact if functionality fails")
    reason: str = Field(..., description="Brief rationale connecting testing parameters to medical risk factors")


# ==========================================
# GENERATION NODE SCHEMAS
# ==========================================

class GenerationNodeResponse(BaseModel):
    id: str
    generation_id: str
    node_id: str
    content_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# GENERATION RUN SCHEMAS
# ==========================================

class GenerationCreate(BaseModel):
    selection_id: str = Field(..., description="UUID of the pinned Selection to generate test cases for")
    llm_provider: Optional[str] = Field(
        default=None,
        description="Override default LLM provider (e.g. 'gemini', 'openai', 'mock')"
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Override default LLM model name (e.g. 'gemini-1.5-flash', 'gpt-4o')"
    )


class GenerationResponse(BaseModel):
    id: str
    selection_id: str
    selection_hash: str
    llm_provider: str
    model_name: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerationDetailResponse(GenerationResponse):
    nodes: List[GenerationNodeResponse] = []
    test_cases: List[TestCase] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# STALENESS SCHEMAS
# ==========================================

class StalenessStatusEnum(str, Enum):
    FRESH = "Fresh"
    POSSIBLY_STALE = "Possibly Stale"
    OUTDATED = "Outdated"


class StalenessResponse(BaseModel):
    status: StalenessStatusEnum = Field(..., description="Overall health of this generation against the latest version")
    reason: str = Field(..., description="Summary explanation of the evaluation")
    modified_node_ids: List[str] = Field(default_factory=list, description="IDs of nodes modified since generation")
    deleted_node_ids: List[str] = Field(default_factory=list, description="IDs of nodes deleted since generation")
    new_version_available: bool = Field(default=False, description="True if a newer document version has been uploaded")

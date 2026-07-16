from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List


# ==========================================
# SELECTION NODE SCHEMAS
# ==========================================

class SelectionNodeBase(BaseModel):
    node_id: str = Field(..., description="UUID of the selected DocumentNode")
    content_hash: str = Field(..., min_length=64, max_length=64, description="Captured content hash at time of selection")


class SelectionNodeCreate(SelectionNodeBase):
    pass


class SelectionNodeResponse(SelectionNodeBase):
    id: str
    selection_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# SELECTION SCHEMAS
# ==========================================

class SelectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the selection (e.g. 'Safety Critical Checks')")
    document_version_id: str = Field(..., description="UUID of the document version associated with this selection")


class SelectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    document_version_id: str = Field(...)
    node_ids: List[str] = Field(..., min_items=1, description="List of DocumentNode IDs to include in this selection")


class SelectionResponse(SelectionBase):
    id: str
    selection_hash: str = Field(..., description="Hash derived from the ordered list of selected node hashes")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SelectionDetailResponse(SelectionResponse):
    nodes: List[SelectionNodeResponse] = []

    model_config = ConfigDict(from_attributes=True)

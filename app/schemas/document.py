from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Optional


# ==========================================
# DOCUMENT NODE SCHEMAS
# ==========================================

class DocumentNodeBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="The structural title/heading")
    level: int = Field(..., ge=0, description="The indentation level of the heading")
    body: str = Field(..., description="The textual paragraph or table body content")
    page_number: int = Field(..., ge=1, description="The page number inside the source PDF")
    content_hash: str = Field(..., min_length=64, max_length=64, description="SHA256 of normalized title + body")


class DocumentNodeCreate(DocumentNodeBase):
    node_uuid: str = Field(..., description="Stable UUID correlating the node across versions")
    parent_id: Optional[str] = Field(default=None, description="UUID of the parent node if any")


class DocumentNodeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    level: Optional[int] = Field(default=None, ge=0)
    body: Optional[str] = None
    page_number: Optional[int] = Field(default=None, ge=1)
    content_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    parent_id: Optional[str] = None


class DocumentNodeResponse(DocumentNodeBase):
    id: str
    node_uuid: str
    document_version_id: str
    parent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentNodeTreeResponse(DocumentNodeResponse):
    children: List["DocumentNodeTreeResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# DOCUMENT VERSION SCHEMAS
# ==========================================

class DocumentVersionBase(BaseModel):
    version_number: int = Field(..., ge=1, description="Sequential version counter (e.g. 1, 2)")
    file_path: str = Field(..., min_length=1, max_length=512, description="Physical path of the PDF on disk")


class DocumentVersionCreate(DocumentVersionBase):
    pass


class DocumentVersionResponse(DocumentVersionBase):
    id: str
    document_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionDetailResponse(DocumentVersionResponse):
    nodes: List[DocumentNodeResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# DOCUMENT SCHEMAS
# ==========================================

class DocumentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Familiar name of the technical manual")


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    versions: List[DocumentVersionResponse] = []

    model_config = ConfigDict(from_attributes=True)

import uuid
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from app.models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """
    Represents an uploaded technical PDF document.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Relationships
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class DocumentVersion(Base, TimestampMixin):
    """
    Represents a specific parsed version of a Document.
    """
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="versions"
    )
    nodes: Mapped[List["DocumentNode"]] = relationship(
        "DocumentNode",
        back_populates="document_version",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class DocumentNode(Base, TimestampMixin):
    """
    Represents a single structural node in the parsed document hierarchy.
    """
    __tablename__ = "document_nodes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    node_uuid: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True
    )
    document_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("document_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion",
        back_populates="nodes"
    )
    
    # Self-referential relationship for parent-child tree hierarchy
    parent: Mapped[Optional["DocumentNode"]] = relationship(
        "DocumentNode",
        remote_side=[id],
        back_populates="children"
    )
    children: Mapped[List["DocumentNode"]] = relationship(
        "DocumentNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

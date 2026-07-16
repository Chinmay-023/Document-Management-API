import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from app.models.base import Base, TimestampMixin


class Selection(Base, TimestampMixin):
    """
    Represents a named, pinned selection of document nodes for generation.
    """
    __tablename__ = "selections"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    document_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    selection_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Relationships
    document_version: Mapped["DocumentVersion"] = relationship("DocumentVersion")
    nodes: Mapped[List["SelectionNode"]] = relationship(
        "SelectionNode",
        back_populates="selection",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class SelectionNode(Base, TimestampMixin):
    """
    Associates a specific DocumentNode to a Selection, capturing the node's hash at pin time.
    """
    __tablename__ = "selection_nodes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    selection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("selections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    selection: Mapped["Selection"] = relationship("Selection", back_populates="nodes")
    node: Mapped["DocumentNode"] = relationship("DocumentNode")

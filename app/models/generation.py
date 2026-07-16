import uuid
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from app.models.base import Base, TimestampMixin


class Generation(Base, TimestampMixin):
    """
    Represents an LLM-powered test case generation run.
    """
    __tablename__ = "generations"

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
    selection_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="SUCCESS",
        nullable=False,
        index=True
    )  # e.g., "SUCCESS", "FAILED"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    selection: Mapped["Selection"] = relationship("Selection")
    nodes: Mapped[List["GenerationNode"]] = relationship(
        "GenerationNode",
        back_populates="generation",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class GenerationNode(Base, TimestampMixin):
    """
    Tracks which specific nodes (and their specific versions/hashes) were consumed to yield the generation.
    """
    __tablename__ = "generation_nodes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    generation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("generations.id", ondelete="CASCADE"),
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
    generation: Mapped["Generation"] = relationship("Generation", back_populates="nodes")
    node: Mapped["DocumentNode"] = relationship("DocumentNode")

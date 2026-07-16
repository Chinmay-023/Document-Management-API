from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.selection import Selection, SelectionNode
from app.models.generation import Generation, GenerationNode


class SelectionRepository(BaseRepository[Selection]):
    def __init__(self, db: Session):
        super().__init__(Selection, db)

    def get_by_version_and_hash(self, version_id: str, selection_hash: str) -> Optional[Selection]:
        """
        Check if a selection with the exact same version and nodes already exists.
        """
        query = select(Selection).where(
            Selection.document_version_id == version_id,
            Selection.selection_hash == selection_hash
        )
        return self.db.scalars(query).first()


class SelectionNodeRepository(BaseRepository[SelectionNode]):
    def __init__(self, db: Session):
        super().__init__(SelectionNode, db)


class GenerationRepository(BaseRepository[Generation]):
    def __init__(self, db: Session):
        super().__init__(Generation, db)

    def get_by_selection_hash(self, selection_hash: str) -> List[Generation]:
        """
        Retrieve all generations matching a specific selection hash configuration.
        """
        query = select(Generation).where(Generation.selection_hash == selection_hash)
        return list(self.db.scalars(query).all())

    def get_by_node_uuid(self, node_uuid: str) -> List[Generation]:
        """
        Find all successful generation records that reference a specific DocumentNode UUID.
        """
        query = (
            select(Generation)
            .join(GenerationNode, GenerationNode.generation_id == Generation.id)
            .join(Generation.selection)  # Join to get node relationships
            .where(GenerationNode.node_id == node_uuid)
        )
        return list(self.db.scalars(query).all())


class GenerationNodeRepository(BaseRepository[GenerationNode]):
    def __init__(self, db: Session):
        super().__init__(GenerationNode, db)

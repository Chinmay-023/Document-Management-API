from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from app.repositories.base import BaseRepository
from app.models.document import Document, DocumentVersion, DocumentNode


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: Session):
        super().__init__(Document, db)

    def get_by_name(self, name: str) -> Optional[Document]:
        """
        Fetch a document by its exact name.
        """
        query = select(Document).where(Document.name == name)
        return self.db.scalars(query).first()


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    def __init__(self, db: Session):
        super().__init__(DocumentVersion, db)

    def get_version(self, document_id: str, version_number: int) -> Optional[DocumentVersion]:
        """
        Retrieve a specific version of a document.
        """
        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number
        )
        return self.db.scalars(query).first()

    def get_latest_version(self, document_id: str) -> Optional[DocumentVersion]:
        """
        Retrieve the highest version number available for a document.
        """
        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        ).order_by(desc(DocumentVersion.version_number)).limit(1)
        return self.db.scalars(query).first()


class DocumentNodeRepository(BaseRepository[DocumentNode]):
    def __init__(self, db: Session):
        super().__init__(DocumentNode, db)

    def get_nodes_by_version(self, version_id: str) -> List[DocumentNode]:
        """
        Retrieve all nodes belonging to a document version.
        """
        query = select(DocumentNode).where(
            DocumentNode.document_version_id == version_id
        ).order_by(DocumentNode.page_number, DocumentNode.id)
        return list(self.db.scalars(query).all())

    def get_nodes_by_ids(self, node_ids: List[str]) -> List[DocumentNode]:
        """
        Retrieve a list of nodes matching a list of UUIDs.
        """
        query = select(DocumentNode).where(DocumentNode.id.in_(node_ids))
        return list(self.db.scalars(query).all())

    def get_node_by_uuid(self, version_id: str, node_uuid: str) -> Optional[DocumentNode]:
        """
        Retrieve a node by its cross-version persistent UUID.
        """
        query = select(DocumentNode).where(
            DocumentNode.document_version_id == version_id,
            DocumentNode.node_uuid == node_uuid
        )
        return self.db.scalars(query).first()

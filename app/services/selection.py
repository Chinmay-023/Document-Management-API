import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.repositories.document import DocumentNodeRepository, DocumentVersionRepository
from app.repositories.generation import SelectionRepository, SelectionNodeRepository
from app.models.selection import Selection, SelectionNode
from app.utils.helpers import generate_selection_hash

logger = logging.getLogger("app.services.selection")


class SelectionService:
    def __init__(self, db: Session):
        self.db = db
        self.version_repo = DocumentVersionRepository(db)
        self.node_repo = DocumentNodeRepository(db)
        self.selection_repo = SelectionRepository(db)
        self.selection_node_repo = SelectionNodeRepository(db)

    def create_selection(self, name: str, version_id: str, node_ids: List[str]) -> Selection:
        """
        Creates and stores a pinned selection of document nodes for a specific version.
        Computes a cryptographic selection hash based on the child nodes.
        """
        logger.info(f"Creating selection '{name}' for version {version_id} with {len(node_ids)} nodes...")

        # 1. Validate that the version exists
        version = self.version_repo.get(version_id)
        if not version:
            raise ValueError(f"Document version '{version_id}' not found.")

        # 2. Retrieve and validate the selected nodes
        nodes = self.node_repo.get_nodes_by_ids(node_ids)
        if len(nodes) != len(node_ids):
            found_ids = {n.id for n in nodes}
            missing_ids = set(node_ids) - found_ids
            raise ValueError(f"One or more nodes not found: {missing_ids}")

        # Ensure all nodes belong to this document version
        for node in nodes:
            if node.document_version_id != version_id:
                raise ValueError(
                    f"Node '{node.id}' does not belong to document version '{version_id}'."
                )

        # 3. Calculate selection hash
        node_hashes = [node.content_hash for node in nodes]
        selection_hash = generate_selection_hash(node_hashes)

        # Check if an identical selection already exists
        existing = self.selection_repo.get_by_version_and_hash(version_id, selection_hash)
        if existing:
            logger.info(f"Identical selection already exists: Selection ID={existing.id}")
            return existing

        # 4. Save Selection
        selection = Selection(
            name=name,
            document_version_id=version_id,
            selection_hash=selection_hash
        )
        self.selection_repo.create(selection)

        # 5. Save SelectionNode mappings
        for node in nodes:
            sel_node = SelectionNode(
                selection_id=selection.id,
                node_id=node.id,
                content_hash=node.content_hash
            )
            self.selection_node_repo.create(sel_node)

        logger.info(f"Selection successfully saved. ID: {selection.id}")
        return selection

    def get_selection(self, selection_id: str) -> Optional[Selection]:
        """
        Fetch a Selection by its UUID.
        """
        return self.selection_repo.get(selection_id)

    def get_all_selections(self, skip: int = 0, limit: int = 100) -> List[Selection]:
        """
        Fetch list of all stored Selections.
        """
        return self.selection_repo.get_all(skip=skip, limit=limit)

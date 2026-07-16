import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.document import DocumentVersion, DocumentNode
from app.repositories.document import DocumentVersionRepository, DocumentNodeRepository
from app.repositories.generation import GenerationRepository
from app.schemas.generation import StalenessStatusEnum, StalenessResponse

logger = logging.getLogger("app.services.staleness")


class StalenessService:
    def __init__(self, db: Session):
        self.db = db
        self.version_repo = DocumentVersionRepository(db)
        self.node_repo = DocumentNodeRepository(db)
        self.gen_repo = GenerationRepository(db)

    def check_staleness(self, generation_id: str) -> StalenessResponse:
        """
        Determines if a generation run is Fresh, Possibly Stale, or Outdated
        by comparing pinned node states against the latest document version.
        """
        logger.info(f"Checking staleness for Generation ID: {generation_id}")

        # 1. Fetch generation
        generation = self.gen_repo.get(generation_id)
        if not generation:
            raise ValueError(f"Generation '{generation_id}' not found.")

        selection = generation.selection
        if not selection:
            raise ValueError(f"Selection associated with generation '{generation_id}' not found.")

        # 2. Get historical document version of the selection
        gen_version: DocumentVersion = selection.document_version
        document_id = gen_version.document_id

        # 3. Fetch latest document version published
        latest_version = self.version_repo.get_latest_version(document_id)
        if not latest_version:
            raise ValueError(f"No versions found for document ID '{document_id}'.")

        new_version_available = latest_version.version_number > gen_version.version_number

        # 4. Compare nodes from selection against the latest version
        modified_node_ids = []
        deleted_node_ids = []

        # Fetch pinned node details from the selection
        selection_nodes = selection.nodes

        for sel_node in selection_nodes:
            # Look up the actual DocumentNode that was selected
            original_node = self.node_repo.get(sel_node.node_id)
            if not original_node:
                # Node has been hard-deleted from DB entirely
                deleted_node_ids.append(sel_node.node_id)
                continue

            # Query the corresponding node in the LATEST version using node_uuid
            latest_node = self.node_repo.get_node_by_uuid(latest_version.id, original_node.node_uuid)
            
            if not latest_node:
                # Pinned requirement node no longer exists in the new version
                deleted_node_ids.append(original_node.id)
            elif latest_node.content_hash != sel_node.content_hash:
                # Content changed between versions
                modified_node_ids.append(original_node.id)

        # 5. Determine Staleness Status
        if deleted_node_ids or modified_node_ids:
            status = StalenessStatusEnum.OUTDATED
            reasons = []
            if deleted_node_ids:
                reasons.append(f"{len(deleted_node_ids)} selected node(s) were deleted")
            if modified_node_ids:
                reasons.append(f"{len(modified_node_ids)} selected node(s) were modified")
            reason = f"Generation is outdated because " + " and ".join(reasons) + f" in version {latest_version.version_number}."
        elif new_version_available:
            status = StalenessStatusEnum.POSSIBLY_STALE
            reason = (
                f"A newer document version (v{latest_version.version_number}) is available. "
                f"Selected requirement nodes are unchanged, but surrounding sections may have changed."
            )
        else:
            status = StalenessStatusEnum.FRESH
            reason = "Generation matches the latest document version and all selected nodes are unchanged."

        logger.info(f"Staleness check complete: Status={status.value}, Reason='{reason}'")
        return StalenessResponse(
            status=status,
            reason=reason,
            modified_node_ids=modified_node_ids,
            deleted_node_ids=deleted_node_ids,
            new_version_available=new_version_available
        )

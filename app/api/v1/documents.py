import os
import shutil
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.database.mongodb import get_mongodb
from app.schemas.document import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentVersionResponse,
    DocumentNodeTreeResponse,
    DocumentNodeResponse
)
from app.models.document import Document, DocumentVersion, DocumentNode
from app.repositories.document import DocumentRepository, DocumentVersionRepository, DocumentNodeRepository
from app.services.parser import PDFParserService
from app.services.versioning import VersioningService
from app.services.diff import DiffService
from app.services.search import SearchService

logger = logging.getLogger("app.api.v1.documents")
router = APIRouter()


@router.post("/upload", response_model=DocumentVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    name: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongodb)
):
    """
    Upload the initial version (v1) of a technical PDF document.
    Parses the layout directly, constructs the tree structure, and persists elements.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    doc_repo = DocumentRepository(db)
    version_repo = DocumentVersionRepository(db)
    node_repo = DocumentNodeRepository(db)

    # 1. Check if document name already exists
    existing_doc = doc_repo.get_by_name(name)
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document name '{name}' already exists. Use the /version endpoint to upload updates."
        )

    # 2. Create document record
    document = Document(name=name)
    doc_repo.create(document)

    # 3. Save physical file to disk
    version_num = 1
    safe_filename = f"{document.id}_v{version_num}.pdf"
    file_path = settings.documents_path / safe_filename

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        doc_repo.delete(document.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save file to disk."
        )

    # 4. Create document version record
    doc_version = DocumentVersion(
        document_id=document.id,
        version_number=version_num,
        file_path=str(file_path)
    )
    version_repo.create(doc_version)

    # 5. Parse PDF content
    try:
        parser = PDFParserService()
        parsed_nodes = parser.parse_pdf(str(file_path), version_num)
        
        # Keep track of generated IDs for tree saving
        sqlite_node_map = {}
        
        # Save to SQLite
        for node_dict in parsed_nodes:
            db_node = DocumentNode(
                id=node_dict["id"],
                node_uuid=node_dict["node_uuid"],
                document_version_id=doc_version.id,
                title=node_dict["title"],
                level=node_dict["level"],
                body=node_dict["body"],
                page_number=node_dict["page_number"],
                parent_id=node_dict["parent_id"],
                content_hash=node_dict["content_hash"]
            )
            node_repo.create(db_node)
            sqlite_node_map[node_dict["id"]] = db_node

        # 6. Save raw tree structure JSON into MongoDB
        if mongo_db is not None:
            try:
                await mongo_db.document_trees.insert_one({
                    "document_id": document.id,
                    "version_id": doc_version.id,
                    "version_number": version_num,
                    "nodes": parsed_nodes
                })
            except Exception as mongo_err:
                logger.warning(f"Could not connect to MongoDB. Saved relational structure to SQLite only. Details: {mongo_err}")

    except Exception as e:
        logger.error(f"Error during PDF parsing or storage: {e}", exc_info=True)
        # Roll back document creation on parser crash to preserve database integrity
        version_repo.delete(doc_version.id)
        doc_repo.delete(document.id)
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse and save PDF contents: {e}"
        )

    return doc_version


@router.post("/version", response_model=DocumentVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_version(
    document_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongodb)
):
    """
    Upload a subsequent version (v2+) of a technical PDF document.
    Aligns new requirement sections with previous versions to preserve node ID mappings.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported."
        )

    doc_repo = DocumentRepository(db)
    version_repo = DocumentVersionRepository(db)
    node_repo = DocumentNodeRepository(db)

    # 1. Validate parent document exists
    document = doc_repo.get(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found."
        )

    # Get latest version number to increment
    latest_v = version_repo.get_latest_version(document_id)
    if not latest_v:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No previous version found. Please use the /upload endpoint first."
        )
    
    next_version_num = latest_v.version_number + 1
    safe_filename = f"{document.id}_v{next_version_num}.pdf"
    file_path = settings.documents_path / safe_filename

    # 2. Save physical file to disk
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save file to disk."
        )

    # 3. Create document version record
    doc_version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_num,
        file_path=str(file_path)
    )
    version_repo.create(doc_version)

    # 4. Parse PDF content
    try:
        parser = PDFParserService()
        v2_parsed = parser.parse_pdf(str(file_path), next_version_num)

        # 5. Load and align nodes with previous version to maintain UUID continuity
        v1_db_nodes = node_repo.get_nodes_by_version(latest_v.id)
        
        # Convert DB models to dictionary arrays for the alignment algorithm
        v1_parsed = []
        for n in v1_db_nodes:
            v1_parsed.append({
                "id": n.id,
                "node_uuid": n.node_uuid,
                "title": n.title,
                "level": n.level,
                "body": n.body,
                "page_number": n.page_number,
                "parent_id": n.parent_id,
                "content_hash": n.content_hash
            })

        aligner = VersioningService()
        aligned_v2, alignment_statuses = aligner.align_versions(v1_parsed, v2_parsed)

        # 6. Save aligned nodes to SQLite
        # Map original parent ids to the newly generated database IDs of parent nodes
        id_mapping = {}  # {old_v2_id: new_v2_db_id}

        # First pass: Insert nodes with parent_id=None to avoid foreign key constraints
        for node_dict in aligned_v2:
            db_node = DocumentNode(
                node_uuid=node_dict["node_uuid"],
                document_version_id=doc_version.id,
                title=node_dict["title"],
                level=node_dict["level"],
                body=node_dict["body"],
                page_number=node_dict["page_number"],
                parent_id=None,
                content_hash=node_dict["content_hash"]
            )
            node_repo.create(db_node)
            id_mapping[node_dict["id"]] = db_node.id
            node_dict["new_db_id"] = db_node.id  # save reference

        # Second pass: Associate parents using the mapping
        for node_dict in aligned_v2:
            old_parent_id = node_dict["parent_id"]
            if old_parent_id and old_parent_id in id_mapping:
                new_db_id = node_dict["new_db_id"]
                db_node = node_repo.get(new_db_id)
                db_node.parent_id = id_mapping[old_parent_id]
                node_repo.update(db_node)

        # Update parent_id fields in JSON payload for MongoDB persistence
        for node_dict in aligned_v2:
            node_dict["id"] = node_dict["new_db_id"]
            if node_dict["parent_id"]:
                node_dict["parent_id"] = id_mapping.get(node_dict["parent_id"])
            del node_dict["new_db_id"]

        # 7. Save raw tree structure JSON into MongoDB
        if mongo_db is not None:
            try:
                await mongo_db.document_trees.insert_one({
                    "document_id": document.id,
                    "version_id": doc_version.id,
                    "version_number": next_version_num,
                    "nodes": aligned_v2
                })
            except Exception as mongo_err:
                logger.warning(f"Could not connect to MongoDB. Saved relational version structure to SQLite only. Details: {mongo_err}")

    except Exception as e:
        logger.error(f"Error during PDF parsing or storage: {e}", exc_info=True)
        version_repo.delete(doc_version.id)
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse and save version: {e}"
        )

    return doc_version


@router.get("", response_model=List[DocumentResponse])
async def list_documents(db: Session = Depends(get_db)):
    """
    Retrieve all uploaded documents and their details.
    """
    doc_repo = DocumentRepository(db)
    return doc_repo.get_all()


@router.get("/{id}", response_model=DocumentDetailResponse)
async def get_document_details(id: str, db: Session = Depends(get_db)):
    """
    Retrieve metadata for a specific document including all uploaded versions.
    """
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get(id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )
    return doc


@router.get("/search/", response_model=List[Dict[str, Any]])
async def search_document_nodes(
    version_id: str,
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Perform a ranked keyword and fuzzy string search inside a specific document version.
    """
    search_svc = SearchService(db)
    results = search_svc.search_nodes(version_id, query, limit)
    return results


@router.get("/tree/", response_model=List[DocumentNodeTreeResponse])
async def get_document_tree(version_id: str, db: Session = Depends(get_db)):
    """
    Reconstructs and returns the full hierarchical section tree for a document version.
    """
    node_repo = DocumentNodeRepository(db)
    nodes = node_repo.get_nodes_by_version(version_id)
    if not nodes:
        return []

    # Map flat node models into tree response objects
    nodes_map = {}
    for node in nodes:
        nodes_map[node.id] = DocumentNodeTreeResponse(
            id=node.id,
            node_uuid=node.node_uuid,
            document_version_id=node.document_version_id,
            title=node.title,
            level=node.level,
            body=node.body,
            page_number=node.page_number,
            parent_id=node.parent_id,
            content_hash=node.content_hash,
            created_at=node.created_at,
            updated_at=node.updated_at,
            children=[]
        )

    root_nodes = []
    for node_id, node_tree in nodes_map.items():
        if node_tree.parent_id and node_tree.parent_id in nodes_map:
            nodes_map[node_tree.parent_id].children.append(node_tree)
        else:
            root_nodes.append(node_tree)

    # Sort root and nested children by page number and then ID sequence
    def sort_tree(node_list: List[DocumentNodeTreeResponse]):
        node_list.sort(key=lambda x: (x.page_number, x.id))
        for item in node_list:
            if item.children:
                sort_tree(item.children)

    sort_tree(root_nodes)
    return root_nodes


@router.get("/diff/{node_id}", response_model=Dict[str, Any])
async def get_node_diff(node_id: str, db: Session = Depends(get_db)):
    """
    Compares a modified node to its corresponding version in the previous document release.
    Returns differences, additions, deletions, and a similarity score.
    """
    node_repo = DocumentNodeRepository(db)
    version_repo = DocumentVersionRepository(db)

    # 1. Fetch current node
    node = node_repo.get(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found."
        )

    # 2. Get details of the document version and locate the previous version number
    version = version_repo.get(node.document_version_id)
    if version.version_number <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node corresponds to version 1. Diffs are only supported from version 2 onwards."
        )

    prev_version = version_repo.get_version(version.document_id, version.version_number - 1)
    if not prev_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Previous version of the document was not found."
        )

    # 3. Fetch matched node in previous version via node_uuid
    prev_node = node_repo.get_node_by_uuid(prev_version.id, node.node_uuid)
    if not prev_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This node did not exist in the previous version of the document."
        )

    # 4. Generate diff report
    diff_svc = DiffService()
    report = diff_svc.compute_diff(
        old_title=prev_node.title,
        old_body=prev_node.body,
        new_title=node.title,
        new_body=node.body,
        new_hash=node.content_hash
    )
    
    return report

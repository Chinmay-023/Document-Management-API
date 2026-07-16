import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.selection import SelectionCreate, SelectionResponse, SelectionDetailResponse
from app.services.selection import SelectionService

logger = logging.getLogger("app.api.v1.selections")
router = APIRouter()


@router.post("", response_model=SelectionResponse, status_code=status.HTTP_201_CREATED)
async def create_selection(payload: SelectionCreate, db: Session = Depends(get_db)):
    """
    Saves a named, immutable configuration pinning a list of document node IDs.
    Returns the generated selection hash and record metadata.
    """
    try:
        svc = SelectionService(db)
        selection = svc.create_selection(
            name=payload.name,
            version_id=payload.document_version_id,
            node_ids=payload.node_ids
        )
        return selection
    except ValueError as ve:
        logger.warning(f"Validation failed while creating selection: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Failed to create selection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving the selection."
        )


@router.get("", response_model=List[SelectionResponse])
async def list_selections(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of all saved selections.
    """
    svc = SelectionService(db)
    return svc.get_all_selections(skip=skip, limit=limit)


@router.get("/{id}", response_model=SelectionDetailResponse)
async def get_selection_details(id: str, db: Session = Depends(get_db)):
    """
    Retrieve full details for a specific Selection ID, including the list of mapped nodes and their content hashes.
    """
    svc = SelectionService(db)
    selection = svc.get_selection(id)
    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selection not found."
        )
    return selection

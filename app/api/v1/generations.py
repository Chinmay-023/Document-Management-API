import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database.mongodb import get_mongodb
from app.schemas.generation import (
    GenerationCreate,
    GenerationResponse,
    GenerationDetailResponse,
    StalenessResponse,
    TestCase
)
from app.models.generation import Generation
from app.repositories.generation import GenerationRepository
from app.services.llm import LLMService
from app.services.staleness import StalenessService

logger = logging.getLogger("app.api.v1.generations")
router = APIRouter()


@router.post("/generate", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_test_cases(payload: GenerationCreate, db: Session = Depends(get_db)):
    """
    Triggers an asynchronous LLM call to generate 3-5 QA test cases from a pinned selection.
    Saves metadata inside the SQL database and full test details inside MongoDB.
    """
    try:
        svc = LLMService(db)
        generation, _ = await svc.generate_test_cases(
            selection_id=payload.selection_id,
            provider=payload.llm_provider,
            model=payload.model_name
        )
        return generation
    except ValueError as ve:
        logger.warning(f"Validation failed while starting generation: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Failed to generate test cases: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during test generation: {e}"
        )


@router.get("/generation/{id}", response_model=GenerationDetailResponse)
async def get_generation_details(
    id: str,
    db: Session = Depends(get_db),
    mongo_db = Depends(get_mongodb)
):
    """
    Retrieves execution metadata from the relational database and parses structured test cases from MongoDB.
    """
    gen_repo = GenerationRepository(db)
    generation = gen_repo.get(id)
    if not generation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation record not found."
        )

    # Fetch corresponding test cases from MongoDB
    test_cases_list = []
    if mongo_db is not None:
        try:
            mongo_record = await mongo_db.test_cases.find_one({"generation_id": id})
            if mongo_record and "test_cases" in mongo_record:
                # Map dict items to TestCase models
                for tc_dict in mongo_record["test_cases"]:
                    test_cases_list.append(TestCase(**tc_dict))
        except Exception as e:
            logger.error(f"Failed to query MongoDB for test cases: {e}")
            # Do not crash; return metadata even if MongoDB query fails
            pass

    # Map SQL model attributes to response schema
    return GenerationDetailResponse(
        id=generation.id,
        selection_id=generation.selection_id,
        selection_hash=generation.selection_hash,
        llm_provider=generation.llm_provider,
        model_name=generation.model_name,
        status=generation.status,
        error_message=generation.error_message,
        created_at=generation.created_at,
        nodes=[
            {
                "id": gn.id,
                "generation_id": gn.generation_id,
                "node_id": gn.node_id,
                "content_hash": gn.content_hash,
                "created_at": gn.created_at
            }
            for gn in generation.nodes
        ],
        test_cases=test_cases_list
    )


@router.get("/generation/node/{node_id}", response_model=List[GenerationResponse])
async def get_generations_by_node(node_id: str, db: Session = Depends(get_db)):
    """
    Finds all past generation runs that consumed a specific document requirement node ID.
    """
    gen_repo = GenerationRepository(db)
    results = gen_repo.get_by_node_uuid(node_id)
    return results


@router.get("/staleness/{generation_id}", response_model=StalenessResponse)
async def check_generation_staleness(generation_id: str, db: Session = Depends(get_db)):
    """
    Examines if a test case generation run is outdated relative to recent manual uploads.
    """
    try:
        svc = StalenessService(db)
        report = svc.check_staleness(generation_id)
        return report
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Staleness check crashed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform staleness check: {e}"
        )

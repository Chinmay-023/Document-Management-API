from fastapi import APIRouter, Depends
from app.api.v1 import documents, selections, generations
from app.database.session import get_db

# Central V1 API Router
api_router = APIRouter()

# Mount Documents router with '/documents' prefix
api_router.include_router(documents.router, prefix="/documents")

# Mount Selections router with '/selection' prefix
api_router.include_router(selections.router, prefix="/selection")

# Mount Generations router with no prefix (handles /generate, /generation/{id}, /generation/node/{node_id}, /staleness/{generation_id})
api_router.include_router(generations.router)

# Mount the /diff/{node_id} endpoint directly under root / if the route was defined inside documents.py
# To support exactly GET /diff/{node_id}, we can create a sub-router for it
diff_router = APIRouter()

@diff_router.get("/diff/{node_id}", tags=["Documents"])
async def get_diff_root(node_id: str, db = Depends(get_db)):
    """
    Proxy handler to retrieve node differences.
    """
    return await documents.get_node_diff(node_id, db)

api_router.include_router(diff_router)

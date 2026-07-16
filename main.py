import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.database.session import engine, Base
from app.database.mongodb import mongodb_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle:
    - Creates relational tables if they do not exist (SQLite development fallback)
    - Establishes connection pool for MongoDB on startup
    - Closes connection pools on shutdown
    """
    logger.info("Starting up QA Test Case Generator API...")
    
    # Ensure relational database tables are created (development auto-creation)
    try:
        logger.info("Initializing relational database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Relational database tables initialized.")
    except Exception as e:
        logger.critical(f"Failed to initialize relational database tables: {e}")
        raise e

    # Connect to MongoDB
    try:
        mongodb_manager.connect()
    except Exception as e:
        logger.warning(
            f"Could not connect to MongoDB during startup. "
            f"MongoDB-dependent services might fail: {e}"
        )

    yield

    logger.info("Shutting down QA Test Case Generator API...")
    # Close connections
    mongodb_manager.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade AI-powered QA Test Case Generation system for medical and technical PDFs.",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in a real production environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root():
    """
    Root API endpoint returning metadata.
    """
    return {
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENV,
        "status": "healthy"
    }


@app.get("/health", tags=["General"])
async def health_check():
    """
    Health check endpoint for container environments and status monitors.
    """
    mongodb_status = "connected" if mongodb_manager.client is not None else "disconnected"
    return {
        "status": "online",
        "relational_db": "available",
        "document_db": mongodb_status
    }


# Global Exception Handler Example
import traceback
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    # Do not swallow router HTTPExceptions (like 400, 404, 422, or explicitly raised 500s)
    if isinstance(exc, (FastAPIHTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    # For unexpected crashes, log and return the traceback
    logger.error(f"Unhandled exception caught globally: {exc}", exc_info=True)
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"Unhandled Exception: {str(exc)}",
            "traceback": tb
        }
    )


# Register central router
from app.api.v1.router import api_router
app.include_router(api_router)


if __name__ == "__main__":

    import uvicorn
    logger.info(f"Running application locally on {settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=(settings.ENV == "development"))

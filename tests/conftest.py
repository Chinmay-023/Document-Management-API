import pytest
import os
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.base import Base
from app.database.session import get_db
from app.database.mongodb import get_mongodb
from main import app as fastapi_app

# Set test environment settings
settings.ENV = "testing"
settings.LLM_PROVIDER = "mock"

# 1. Setup in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 2. Setup mock MongoDB
class MockCollection:
    def __init__(self):
        self.store = {}

    async def insert_one(self, document):
        # Generate an ID if not present
        if "_id" not in document:
            import uuid
            document["_id"] = str(uuid.uuid4())
        # Store by generation_id, document_id, or version_id depending on context
        key = document.get("generation_id") or document.get("version_id") or document["_id"]
        self.store[key] = document
        return type("InsertResult", (object,), {"inserted_id": document["_id"]})()

    async def find_one(self, filter_query):
        # Simple query matching
        for doc in self.store.values():
            match = True
            for k, v in filter_query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None


class MockMongoDB:
    def __init__(self):
        self.document_trees = MockCollection()
        self.test_cases = MockCollection()


mock_mongo_db = MockMongoDB()


async def override_get_mongodb():
    return mock_mongo_db

# Override the database module function globally for all imports in tests
import app.database.mongodb
app.database.mongodb.get_mongodb = override_get_mongodb


@pytest.fixture(scope="function", autouse=True)
def setup_db() -> Generator:
    """
    Creates SQL tables before each test and drops them afterwards.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator:
    """
    Provides an isolated SQL transaction session for testing repository operations.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """
    Overrides the database dependency and provides a test client.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_mongodb] = override_get_mongodb
    
    with TestClient(fastapi_app) as test_client:
        yield test_client
        
    fastapi_app.dependency_overrides.clear()

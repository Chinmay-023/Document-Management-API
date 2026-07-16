from motor.motor_asyncio import AsyncIOMotorClient
import logging
from app.core.config import settings

logger = logging.getLogger("app.database.mongodb")


class MongoDBManager:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db = None

    def connect(self) -> None:
        """
        Initializes the async MongoDB client connection pool.
        """
        try:
            logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000  # Fail fast (5s timeout)
            )
            # The client does not immediately connect. Force a connection check by accessing db properties.
            self.db = self.client[settings.MONGODB_DB_NAME]
            logger.info("MongoDB client session initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise e

    def close(self) -> None:
        """
        Closes the active MongoDB client connection pool.
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection pool closed.")
            self.client = None
            self.db = None


# Create a global instance of the MongoDBManager
mongodb_manager = MongoDBManager()


async def get_mongodb():
    """
    FastAPI dependency that returns the active MongoDB database object.
    """
    if mongodb_manager.db is None:
        # Fallback initialization check
        mongodb_manager.connect()
    return mongodb_manager.db

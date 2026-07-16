from typing import Generic, Type, TypeVar, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        """
        Base repository containing common CRUD operations.
        """
        self.model = model
        self.db = db

    def get(self, id: Any) -> Optional[ModelType]:
        """
        Retrieve a single record by primary key ID.
        """
        return self.db.get(self.model, id)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Retrieve all records with optional pagination.
        """
        query = select(self.model).offset(skip).limit(limit)
        return list(self.db.scalars(query).all())

    def create(self, obj: ModelType) -> ModelType:
        """
        Persist a new model instance.
        """
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType) -> ModelType:
        """
        Save updates to an existing model instance.
        """
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id: Any) -> bool:
        """
        Delete a record by ID. Returns True if found and deleted, False otherwise.
        """
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

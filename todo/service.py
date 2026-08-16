from typing import Optional

from sqlalchemy.orm import Session

from todo.cache import get_cache, set_cache, delete_pattern

from todo.models import Task as TaskModel  # SqlAlchemy db model or ORM model
from todo.schemas import TaskCreate, Task  # pydantic model (like POJO)

import logging

# get logger
logger = logging.getLogger(__name__)  # __name__ = "todo.service"


class TodoService:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, user_id: int, show_all: bool = False) -> list[Task]:
        """Return this user's tasks (cache-aside). Always list[Task]."""
        """updated to list Tasks for this user only"""
        cache_key = f"tasks:user:{user_id}:show_all:{show_all}"

        # 1. Try cache first
        # Cache HIT → rebuild Pydantic models from stored dicts
        cached = get_cache(cache_key)
        if cached is not None:
            logger.info("Cache HIT -> %s", cache_key)
            # .model_validate() validates and builds Task instance
            return [Task.model_validate(item) for item in cached]

        logger.info("Cache MISS -> %s", cache_key)

        # 2. Query database
        # Note: query is not executed yet, will only do so when .all() is called
        query = self.db.query(TaskModel).where(
            TaskModel.user_id == user_id)  # creates a query object for all records in the tasks table

        # where vs filter, functionally identical. where() is modern style
        if not show_all:
            query = query.where(TaskModel.done.is_(False))  # continue the same query object

            # DO not do this below, it creates 'new' query instead of continuing existing one
            # query = self.db.query(TaskModel).where(TaskModel.done == False)  # only pending tasks

        # executes the query and returns list of Task object
        # the SqlAlchemy object -> Pydantic model happens automatically
        # due to configuration in service: from_attributes = True
        rows = query.order_by(TaskModel.created_at.desc()).all()

        # 3) ORM → Pydantic (from_attributes / model_config)
        tasks = [Task.model_validate(row) for row in rows]

        # 4) Cache JSON-safe data only (not ORM, not live objects)
        set_cache(cache_key, [task.model_dump(mode="json") for task in tasks])

        return tasks  # list[dict], not list[Task]

    def create(self, user_id: int, task_create: TaskCreate) -> TaskModel:
        """Create a new task and invalidate cache"""
        db_task = TaskModel(
            title=task_create.title,
            done=False,
            user_id=user_id  # NOTE: do not put user_id on TaskCreate, owner must come from JWT, not client
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)

        # Invalidate all task caches
        delete_pattern(f"tasks:user:{user_id}:*")
        logger.info("Cache cleared for user_id=%s after create", user_id)

        return db_task

    # if we want Explicit conversion:
    # return Task.model_validate(db_task)   # or Task.from_orm(db_task) in older Pydantic

    def mark_done(self, user_id: int, task_id: int) -> Optional[TaskModel]:
        """Mark a task as done and invalidate cache"""
        # NOTE: Do not use python "and" here eg. where(TaskModel.id == task_id and TaskModel.user_id == user_id)
        task = self.db.query(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == user_id).first()
        if task:
            task.done = True
            self.db.commit()
            self.db.refresh(task)

            delete_pattern(f"tasks:user:{user_id}:*")
            logger.info("Cache cleared for user_id=%s after mark_done", user_id)

        return task

    def delete(self, user_id: int, task_id: int) -> bool:
        """Delete a task and invalidate cache"""
        task = (
            self.db.query(TaskModel)
            .where(TaskModel.id == task_id, TaskModel.user_id == user_id)
            .first()
        )
        if not task:
            return False

        self.db.delete(task)
        self.db.commit()

        delete_pattern(f"tasks:user:{user_id}:*")
        logger.info("Cache cleared for user_id=%s after delete", user_id)

        return True

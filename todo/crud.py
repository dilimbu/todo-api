from sqlalchemy.orm import Session

from todo.models import Task
from todo.schemas import TaskCreate


# Data Access Layer - All database operations

# NOTE: For simple data operations (often merged with Repository)
# Basic CRUD
# More realistically, we would use Service and Repository layers

def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Task).offset(skip).limit(limit).all()


def create_task(db: Session, task: TaskCreate):
    db_task = Task(title=task.title, done=False)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


def mark_done(db: Session, task_id: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.done = True
        db.commit()
        return task
    return None


def delete_task(db: Session, task_id: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
        return True
    return False

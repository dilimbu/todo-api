import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from todo.dependencies import get_current_user, get_todo_service
from todo.models import User as UserModel
from todo.rate_limiter import limiter
from todo.schemas import Task, TaskCreate
from todo.service import TodoService

# from wherever write_audit_log lives:
from todo.celery_tasks import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[Task])
@limiter.limit("30/minute")
async def list_tasks(
        request: Request,
        show_all: bool = False,
        service: TodoService = Depends(get_todo_service),
        curr_user: UserModel = Depends(get_current_user),
):
    """List tasks"""
    logger.info("User %s requested tasks (show_all=%s)", curr_user.username, show_all)
    return service.get_all(curr_user.id, show_all)


@router.post("", response_model=Task, status_code=201)
@limiter.limit("30/minute")
async def create_task(
        request: Request,
        task: TaskCreate,
        background_tasks: BackgroundTasks,
        service: TodoService = Depends(get_todo_service),
        current_user: UserModel = Depends(get_current_user),
):
    """Create a new task"""
    new_task = service.create(current_user.id, task)

    # logger.info("User %s created task: %s", current_user.username, task.title)

    # simple fast API background task, runs after response is sent
    background_tasks.add_task(
        write_audit_log,  # function to call
        current_user.username,  # first arg
        f"created_task:{new_task.id}",  # second arg
    )
    return new_task


@router.patch("/{task_id}/done", response_model=Task)
@limiter.limit("30/minute")
async def mark_as_done(
        request: Request,
        task_id: int,
        service: TodoService = Depends(get_todo_service),
        current_user: UserModel = Depends(get_current_user),
):
    """Mark task as done"""
    task = service.mark_done(current_user.id, task_id)
    if not task:
        logger.warning("Error setting task %s done", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("User %s marked task %s as done", current_user.username, task.title)
    return task


@router.delete("/{task_id}")
@limiter.limit("30/minute")
async def delete_task(
        request: Request,
        task_id: int,
        service: TodoService = Depends(get_todo_service),
        current_user: UserModel = Depends(get_current_user),
):
    """Delete a task"""
    if service.delete(current_user.id, task_id):
        logger.info("User %s deleted task %s", current_user.username, task_id)
        return {"message": "Task deleted successfully"}

    logger.warning("Task %s not found by user %s", task_id, current_user.username)
    raise HTTPException(status_code=404, detail="Task not found")

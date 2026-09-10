import asyncio

from fastapi import APIRouter, Depends

from todo.dependencies import get_current_user, get_todo_service
from todo.models import User as UserModel
from todo.redis_utils import ping_redis
from todo.service import TodoService

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(
        current_user: UserModel = Depends(get_current_user),
        service: TodoService = Depends(get_todo_service),
):
    stats, recent, redis_ok = await asyncio.gather(
        asyncio.to_thread(service.stats, current_user.id), # these are synchronous, wrap with asyncio.to_thread, so event loop isn't blocked
        asyncio.to_thread(service.recent, current_user.id, 5),
        ping_redis(),
    )
    return {
        "stats": stats,
        "recent_tasks": recent,
        "redis_available": redis_ok,
    }

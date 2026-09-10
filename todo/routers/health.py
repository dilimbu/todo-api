from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "service": "todo-api"}

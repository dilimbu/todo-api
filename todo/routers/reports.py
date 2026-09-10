import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"])

# Thread pool for short blocking work
blocking_pool = ThreadPoolExecutor(max_workers=4)


def blocking_report_job(user_id: int) -> dict:
    """
    Simulate blocking work (legacy SDK, file I/O, sync HTTP client, etc.).
    Runs in a worker thread — not on the asyncio event loop.
    """
    import time
    time.sleep(5)   # pretend slow blocking work
    return {"user_id": user_id, "report": "done", "source": "thread-pool"}


@router.get("/reports/blocking/{user_id}")
async def generate_report(user_id: int):
    """
    Offload blocking work to a thread so the asyncio event loop stays free.
    Other requests (e.g. GET /health) can still be handled while this runs.
    """

    # Blocking calls (e.g. time.sleep) freeze the event loop and block other requests.
    # run_in_executor() moves the work to a thread pool so the event loop stays free.
    # Note: async/await only helps with I/O waits — CPU-bound or blocking code
    # still needs run_in_executor, even inside async functions.

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(blocking_pool, blocking_report_job, user_id)
        return result
    except ValueError as e:
        # expected / business error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # unexpected failure
        logger.exception("Report failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Report generation failed")

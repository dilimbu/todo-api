import logging

from fastapi import Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


# request: the incoming HTTP request that caused the error
# exc: the actual exception object (contains all the validation details)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error("Validation error for %s: %s", request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Invalid input data",
            "errors": exc.errors()
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTP Exception [%s]: %s", exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    logger.warning("Rate limit exceeded for %s", request.client.host)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )

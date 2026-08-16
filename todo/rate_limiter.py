# Rate limiting restricts how many requests a user (or IP address)
# can make to your API in a given time window.
# It protects your API from abuse, brute-force attacks, and overload.
# we will use slowapi for rate limiting

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create global limiter that tracks requests per IP
limiter = Limiter(key_func=get_remote_address)  # get_remote_access uses client's IP as key for limiting


def get_rate_limiter():
    """Dependency to inject limiter if needed"""
    return limiter

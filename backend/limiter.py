from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance — imported by main.py (to register the handler)
# and by individual route modules (to apply per-route limits).
limiter = Limiter(key_func=get_remote_address, default_limits=["200/hour"])

"""
Rate limiting (spec section 20). Keyed by client IP. Applied selectively to
auth endpoints (register/login are the classic brute-force/enumeration
targets) rather than globally — a photo-heavy app's upload/search endpoints
see legitimate high-frequency use from a single logged-in user, so a global
limit would just be an annoyance without much security value there.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

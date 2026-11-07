"""Shared rate limiter instance. Keeps free-tier LLM quota from being burned
by a single abusive client and gives us basic DoS resistance for free.

Counts are kept in memory, so on a serverless host each warm instance counts on
its own: the limit is per client per instance, a floor rather than a guarantee.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_key(request: Request) -> str:
    """The client's address, as seen past the host's proxy.

    Behind a proxy, the socket peer is the proxy, and every user would share one
    bucket. On Vercel (which sets VERCEL=1) the edge writes `x-real-ip` itself and
    overwrites anything a client sends, so it can be trusted there. Anywhere else
    the header could be forged, so the socket address is used as before.
    """
    if os.environ.get("VERCEL") == "1":
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return get_remote_address(request)


limiter = Limiter(key_func=client_key)

"""Keep shared admin files unchanged while moving their backend reads off-loop."""
import asyncio
import threading

from src.admin_api import Backends


class CachedBackends(Backends):
    """Refresh in a worker; shared synchronous descriptions read memory only."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._guard = threading.RLock()

    def _load(self):
        pass  # Disk refresh is explicit at request boundaries.

    def refresh(self):
        with self._guard:
            Backends._load(self)

    def _row(self, key):
        with self._guard:
            return super()._row(key)

    def _write(self, data):
        with self._guard:
            super()._write(data)
            Backends._load(self)


class AdminRefreshMiddleware:
    """Serialize shared admin mutations and refresh persisted slots without blocking ASGI."""

    def __init__(self, app, backends):
        self.app, self.backends = app, backends
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/admin/"):
            async with self.lock:
                await asyncio.to_thread(self.backends.refresh)
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)

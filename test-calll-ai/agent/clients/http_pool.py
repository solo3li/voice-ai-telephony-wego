import aiohttp
import asyncio
from config import logger

_session: aiohttp.ClientSession = None
_lock = asyncio.Lock()

async def get_http_session() -> aiohttp.ClientSession:
    """Retrieve or initialize the shared persistent aiohttp.ClientSession."""
    global _session
    if _session is None or _session.closed:
        async with _lock:
            if _session is None or _session.closed:
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=20,
                    ttl_dns_cache=300,
                    enable_cleanup_closed=True
                )
                timeout = aiohttp.ClientTimeout(total=10, connect=3)
                _session = aiohttp.ClientSession(connector=connector, timeout=timeout)
                logger.info("Shared non-blocking aiohttp.ClientSession initialized.")
    return _session

async def close_http_session():
    """Cleanly close the shared persistent aiohttp.ClientSession."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
        # Allow underlying TCP transport connections to finish closing
        await asyncio.sleep(0.25)
        logger.info("Shared aiohttp.ClientSession closed cleanly.")

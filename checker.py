import asyncio
import logging
import ssl
import socket
from config import CHECK_TIMEOUT_SECONDS
from parser import ParsedConfig

logger = logging.getLogger(__name__)


async def check_tcp(server: str, port: int, timeout: float = CHECK_TIMEOUT_SECONDS) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def check_tls(server: str, port: int, timeout: float = CHECK_TIMEOUT_SECONDS) -> bool:
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port, ssl=ssl_ctx, server_hostname=server),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _uses_tls(config: ParsedConfig) -> bool:
    raw = config.raw.lower()
    if config.protocol == "trojan":
        return True
    if config.protocol == "vmess":
        try:
            import base64, json
            encoded = raw.replace("vmess://", "")
            padding = "=" * (4 - len(encoded) % 4) if len(encoded) % 4 else ""
            decoded = json.loads(base64.b64decode(encoded + padding))
            return decoded.get("tls", "") == "tls"
        except Exception:
            pass
    if config.protocol == "vless":
        return "tls" in raw or "security=tls" in raw
    return False


async def check_config(config: ParsedConfig) -> bool:
    uses_tls = _uses_tls(config)

    if uses_tls:
        if await check_tls(config.server, config.port):
            logger.info("TLS OK: %s:%d (%s)", config.server, config.port, config.name)
            return True
        if await check_tcp(config.server, config.port):
            logger.info("TCP OK (TLS failed): %s:%d (%s)", config.server, config.port, config.name)
            return True
    else:
        if await check_tcp(config.server, config.port):
            logger.info("TCP OK: %s:%d (%s)", config.server, config.port, config.name)
            return True

    logger.info("FAIL: %s:%d (%s)", config.server, config.port, config.name)
    return False


async def check_configs(configs: list[ParsedConfig], concurrency: int = 20) -> list[ParsedConfig]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[ParsedConfig] = []

    async def _check(cfg: ParsedConfig):
        async with semaphore:
            if await check_config(cfg):
                results.append(cfg)

    await asyncio.gather(*[_check(cfg) for cfg in configs])
    return results

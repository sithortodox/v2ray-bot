import asyncio
import json
import logging
import os
import socket
import tempfile

from parser import ParsedConfig
from xray_config import generate_xray_config
from config import CHECK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

XRAY_BIN = "/usr/local/bin/xray"
XRAY_START_DELAY = 3
MAX_CONCURRENT = 2
DELAY_BETWEEN_CHECKS = 3
RETRY_ATTEMPTS = 2
TEST_URLS = [
    "http://ip-api.com/json?fields=query",
    "https://api.ipify.org?format=json",
]
_local_port_counter = 30000


def _next_port() -> int:
    global _local_port_counter
    _local_port_counter += 1
    return _local_port_counter


def _is_private_ip(ip: str) -> bool:
    for prefix in ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                   "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                   "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                   "172.30.", "172.31.",
                   "192.168.", "127.", "0.", "localhost"):
        if ip.startswith(prefix):
            return True
    return False


async def _wait_for_port(port: int, timeout: float = 5) -> bool:
    for _ in range(int(timeout * 10)):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.1)
    return False


async def _test_proxy(port: int, timeout: int) -> bool:
    for url in TEST_URLS:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s",
                "--socks5-hostname", f"127.0.0.1:{port}",
                "--connect-timeout", str(timeout),
                "-m", str(timeout + 3),
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 5)
            body = stdout.decode().strip()
            if not body:
                continue
            try:
                data = json.loads(body)
                ip = data.get("query") or data.get("ip", "")
                if ip and not _is_private_ip(ip):
                    return True
            except json.JSONDecodeError:
                pass
        except Exception:
            continue
    return False


async def check_config(config: ParsedConfig) -> bool:
    if _is_private_ip(config.server):
        return False

    port = _next_port()
    xray_cfg = generate_xray_config(config.raw, port)
    if not xray_cfg:
        logger.debug("Cannot generate xray config for %s", config.name)
        return False

    config_file = None
    process = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(xray_cfg, f)
            config_file = f.name

        process = await asyncio.create_subprocess_exec(
            XRAY_BIN, "run", "-c", config_file,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        await asyncio.sleep(XRAY_START_DELAY)

        if process.returncode is not None:
            return False

        port_ready = await _wait_for_port(port, timeout=3)
        if not port_ready:
            logger.debug("Port %d not ready for %s", port, config.name)
            return False

        for attempt in range(RETRY_ATTEMPTS):
            if await _test_proxy(port, CHECK_TIMEOUT_SECONDS):
                logger.info("WORKING: %s:%d (%s) [%s]", config.server, config.port, config.name, config.protocol)
                return True
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(2)

        logger.debug("FAILED: %s:%d (%s) [%s]", config.server, config.port, config.name, config.protocol)
        return False

    except Exception as e:
        logger.error("check_config error for %s: %s", config.name, e)
        return False
    finally:
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if config_file:
            try:
                os.unlink(config_file)
            except OSError:
                pass


async def check_configs(configs: list[ParsedConfig], concurrency: int = MAX_CONCURRENT) -> list[ParsedConfig]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[ParsedConfig] = []

    async def _check(cfg: ParsedConfig):
        async with semaphore:
            if await check_config(cfg):
                results.append(cfg)
            await asyncio.sleep(DELAY_BETWEEN_CHECKS)

    await asyncio.gather(*[_check(cfg) for cfg in configs])
    return results

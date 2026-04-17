import asyncio
import json
import logging
import os
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
_local_port_counter = 50000

BLACKLIST_PASSWORDS = {
    "shadowsocks", "password", "123456", "passwd", "test", "admin",
    "pass", "1234", "0000", "1111", "abcd", "guest",
}


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


def is_blacklisted(config: ParsedConfig) -> bool:
    raw_lower = config.raw.lower()
    for pwd in BLACKLIST_PASSWORDS:
        if pwd in raw_lower:
            return True
    return False


def must_have_encryption(config: ParsedConfig) -> bool:
    if config.protocol == "ss":
        return False
    return config.has_encryption


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


async def _deep_https_verify(port: int, timeout: int) -> dict | None:
    test_url = "https://ip-api.com/json"
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s",
            "--socks5-hostname", f"127.0.0.1:{port}",
            "--connect-timeout", str(timeout),
            "-m", str(timeout + 5),
            test_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 8)
        if proc.returncode != 0:
            return None
        body = stdout.decode().strip()
        if not body:
            return None
        data = json.loads(body)
        if data.get("status") != "success":
            return None
        ip = data.get("query", "")
        if not ip or _is_private_ip(ip):
            return None
        return data
    except Exception:
        return None


async def _download_content_verify(port: int, timeout: int) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s",
            "--socks5-hostname", f"127.0.0.1:{port}",
            "--connect-timeout", str(timeout),
            "-m", str(timeout + 5),
            "https://raw.githubusercontent.com/sithortodox/v2ray-bot/main/.gitignore",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout + 8)
        if proc.returncode != 0:
            return False
        body = stdout.decode().strip()
        return len(body) > 10 and "__pycache__" in body
    except Exception:
        return False


async def check_config(config: ParsedConfig) -> bool:
    if _is_private_ip(config.server):
        return False

    if is_blacklisted(config):
        logger.debug("Blacklisted: %s", config.name)
        return False

    if not must_have_encryption(config):
        logger.debug("No encryption: %s [%s] - skipping", config.name, config.protocol)
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
            logger.debug("Xray crashed for %s", config.name)
            return False

        if not await _wait_for_port(port, timeout=4):
            logger.debug("Port not ready for %s", config.name)
            return False

        for attempt in range(RETRY_ATTEMPTS):
            ip_data = await _deep_https_verify(port, CHECK_TIMEOUT_SECONDS)
            if not ip_data:
                if attempt < RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(2)
                continue

            content_ok = await _download_content_verify(port, CHECK_TIMEOUT_SECONDS)
            if not content_ok:
                logger.debug("Content download failed for %s — proxy unusable", config.name)
                break

            country = ip_data.get("countryCode", "??")
            logger.info(
                "WORKING: %s:%d (%s) [%s] via %s",
                config.server, config.port, config.name, config.protocol, country,
            )
            return True

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

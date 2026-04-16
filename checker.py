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
XRAY_START_DELAY = 2
MAX_CONCURRENT = 3
DELAY_BETWEEN_CHECKS = 1.5
TEST_URL = "http://www.gstatic.com/generate_204"
_local_port_counter = 20000


def _next_port() -> int:
    global _local_port_counter
    _local_port_counter += 1
    return _local_port_counter


async def check_config(config: ParsedConfig) -> bool:
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
            stderr = await process.stderr.read()
            logger.debug("Xray exited for %s: %s", config.name, stderr[:200])
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                "--socks5", f"127.0.0.1:{port}",
                "--connect-timeout", str(CHECK_TIMEOUT_SECONDS),
                "-m", str(CHECK_TIMEOUT_SECONDS + 2),
                TEST_URL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=CHECK_TIMEOUT_SECONDS + 5)
            status = stdout.decode().strip()
            if status in ("200", "204"):
                logger.info("WORKING: %s:%d (%s) [%s]", config.server, config.port, config.name, config.protocol)
                return True
            else:
                logger.debug("HTTP %s for %s (%s)", status, config.name, config.protocol)
                return False
        except Exception as e:
            logger.debug("curl failed for %s: %s", config.name, e)
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

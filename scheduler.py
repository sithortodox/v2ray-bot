import asyncio
import logging
from datetime import datetime
from aiogram import Bot

from database import (
    add_config,
    update_config_status,
    delete_config,
    get_configs_to_recheck,
)
from scraper import scrape_all
from checker import check_config
from parser import ParsedConfig
from bot import broadcast_new_configs, broadcast_dead_configs
from config import CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

MAX_NEW_CONFIGS_PER_CYCLE = 80
DELAY_BETWEEN_CHECKS = 2

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def _get_existing(raw: str):
    from database import get_config_by_raw
    return await get_config_by_raw(raw)


async def _update_by_raw(raw: str, is_working: bool):
    from database import get_config_by_raw, update_config_status
    existing = await get_config_by_raw(raw)
    if existing:
        await update_config_status(existing["id"], is_working)


async def _run_check_cycle(bot: Bot):
    logger.info("=== Check cycle started at %s ===", datetime.utcnow().isoformat())

    logger.info("Phase 1: Scraping GitHub...")
    new_configs = await scrape_all()
    new_configs = new_configs[:MAX_NEW_CONFIGS_PER_CYCLE]
    logger.info("Scraped %d configs (limited to %d)", len(new_configs), MAX_NEW_CONFIGS_PER_CYCLE)

    new_working: list[dict] = []

    for i, cfg in enumerate(new_configs):
        existing = await _get_existing(cfg.raw)
        if existing:
            continue

        added = await add_config(
            protocol=cfg.protocol,
            raw_config=cfg.raw,
            server=cfg.server,
            port=cfg.port,
            name=cfg.name,
            source="github",
        )
        if not added:
            continue

        is_working = await check_config(cfg)
        if is_working:
            await _update_by_raw(cfg.raw, True)
            new_working.append({
                "protocol": cfg.protocol,
                "raw_config": cfg.raw,
                "name": cfg.name,
                "server": cfg.server,
                "source": "",
            })
            logger.info("[%d/%d] NEW WORKING: %s (%s)", i + 1, len(new_configs), cfg.name, cfg.protocol)
        else:
            logger.debug("[%d/%d] not working: %s (%s)", i + 1, len(new_configs), cfg.name, cfg.protocol)

        await asyncio.sleep(DELAY_BETWEEN_CHECKS)

    logger.info("Phase 1 done. New working: %d / %d checked", len(new_working), len(new_configs))

    logger.info("Phase 2: Rechecking existing working configs...")
    existing_working = await get_configs_to_recheck()
    dead_configs: list[dict] = []

    for i, cfg_row in enumerate(existing_working):
        parsed = ParsedConfig(
            protocol=cfg_row["protocol"],
            raw=cfg_row["raw_config"],
            server=cfg_row["server"],
            port=cfg_row["port"],
            name=cfg_row["name"],
        )
        is_working = await check_config(parsed)
        if is_working:
            await update_config_status(cfg_row["id"], True)
        else:
            dead_configs.append(dict(cfg_row))
            await delete_config(cfg_row["id"])
            logger.info("[%d/%d] DEAD: %s (%s)", i + 1, len(existing_working), cfg_row["name"], cfg_row["protocol"])

        await asyncio.sleep(DELAY_BETWEEN_CHECKS)

    logger.info("Phase 2 done. Dead: %d / %d rechecked", len(dead_configs), len(existing_working))

    if new_working:
        await broadcast_new_configs(bot, new_working)
    if dead_configs:
        await broadcast_dead_configs(bot, dead_configs)

    logger.info("=== Check cycle finished ===")


def start_scheduler(bot: Bot):
    scheduler.add_job(
        _run_check_cycle,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        args=[bot],
        id="check_cycle",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_check_cycle,
        "date",
        run_date=datetime.now(),
        args=[bot],
        id="initial_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Interval: %d minutes", CHECK_INTERVAL_MINUTES)


def stop_scheduler():
    scheduler.shutdown(wait=False)

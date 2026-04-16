import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    add_config,
    update_config_status,
    delete_config,
    get_configs_to_recheck,
    get_working_configs,
)
from scraper import scrape_all
from checker import check_config
from parser import ParsedConfig
from bot import broadcast_new_configs, broadcast_dead_configs
from config import CHECK_INTERVAL_MINUTES

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_check_cycle(bot: Bot):
    logger.info("=== Check cycle started at %s ===", datetime.utcnow().isoformat())

    # Phase 1: Scrape new configs from GitHub
    logger.info("Phase 1: Scraping GitHub...")
    new_configs = await scrape_all()
    new_working: list[dict] = []

    for cfg in new_configs:
        existing = await _get_existing(cfg)
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
            await update_config_status_by_raw(cfg.raw, True)
            new_working.append({
                "protocol": cfg.protocol,
                "raw_config": cfg.raw,
                "name": cfg.name,
                "server": cfg.server,
                "source": "",
            })
            logger.info("New working config: %s (%s)", cfg.name, cfg.protocol)

    logger.info("Phase 1 done. New working: %d / %d scraped", len(new_working), len(new_configs))

    # Phase 2: Recheck existing working configs
    logger.info("Phase 2: Rechecking existing configs...")
    existing_working = await get_configs_to_recheck()
    dead_configs: list[dict] = []

    for cfg_row in existing_working:
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
            logger.info("Dead config removed: %s (%s)", cfg_row["name"], cfg_row["protocol"])

    logger.info("Phase 2 done. Dead: %d / %d rechecked", len(dead_configs), len(existing_working))

    # Phase 3: Broadcast
    if new_working:
        await broadcast_new_configs(bot, new_working)
    if dead_configs:
        await broadcast_dead_configs(bot, dead_configs)

    logger.info("=== Check cycle finished ===")


async def _get_existing(cfg: ParsedConfig):
    from database import get_config_by_raw
    return await get_config_by_raw(cfg.raw)


async def update_config_status_by_raw(raw: str, is_working: bool):
    from database import get_config_by_raw, update_config_status
    existing = await get_config_by_raw(raw)
    if existing:
        await update_config_status(existing["id"], is_working)


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

import logging
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from database import add_user, get_working_configs, get_stats, get_all_users
from config import MAX_CONFIGS_PER_MESSAGE

logger = logging.getLogger(__name__)
router = Router()


def _format_config(cfg: dict) -> str:
    name = cfg.get("name", "unnamed")
    protocol = cfg.get("protocol", "unknown")
    source = cfg.get("source", "")
    raw = cfg.get("raw_config", "")
    lines = [
        f"<b>{name}</b>",
        f"Protocol: <code>{protocol}</code>",
    ]
    if source:
        lines.append(f"Source: <a href='{source}'>GitHub</a>")
    lines.append(f"<code>{raw}</code>")
    return "\n".join(lines)


def _split_configs(configs: list[dict], max_per_msg: int = MAX_CONFIGS_PER_MESSAGE) -> list[list[dict]]:
    chunks = []
    for i in range(0, len(configs), max_per_msg):
        chunks.append(configs[i : i + max_per_msg])
    return chunks


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id, message.from_user.username or "")
    await message.answer(
        "Привет! Я бот для мониторинга V2Ray конфигов с GitHub.\n\n"
        "Команды:\n"
        "/get — получить рабочие конфиги\n"
        "/status — статистика\n"
        "/subscribe — подписаться на уведомления\n"
        "/unsubscribe — отписаться от уведомлений"
    )


@router.message(Command("get"))
async def cmd_get(message: types.Message):
    configs = await get_working_configs()
    if not configs:
        await message.answer("Рабочих конфигов пока нет. Подожди, идёт сбор.")
        return
    chunks = _split_configs(configs)
    for chunk in chunks:
        text = "\n\n---\n\n".join(_format_config(c) for c in chunk)
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("status"))
async def cmd_status(message: types.Message):
    stats = await get_stats()
    await message.answer(
        f"Рабочих конфигов: {stats['working']}\n"
        f"Нерабочих (на проверке): {stats['not_working']}\n"
        f"Подписчиков: {stats['users']}"
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: types.Message):
    await add_user(message.from_user.id, message.from_user.username or "")
    await message.answer("Ты подписан на уведомления о новых конфигах.")


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: types.Message):
    from database import delete_user
    await delete_user(message.from_user.id)
    await message.answer("Подписка отменена.")


async def broadcast_new_configs(bot: Bot, configs: list[dict]):
    if not configs:
        return
    users = await get_all_users()
    chunks = _split_configs(configs)
    for user_id in users:
        for chunk in chunks:
            text = "<b>Новые рабочие конфиги:</b>\n\n" + "\n\n---\n\n".join(
                _format_config(c) for c in chunk
            )
            try:
                await bot.send_message(
                    user_id, text, parse_mode="HTML", disable_web_page_preview=True
                )
            except Exception as e:
                logger.error("Failed to send to %s: %s", user_id, e)


async def broadcast_dead_configs(bot: Bot, configs: list[dict]):
    if not configs:
        return
    users = await get_all_users()
    for user_id in users:
        text = f"<b>Удалены нерабочие конфиги ({len(configs)}):</b>\n"
        for c in configs:
            name = c.get("name", "unnamed")
            text += f"  - {name} ({c.get('protocol', '?')})\n"
        try:
            await bot.send_message(user_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to send to %s: %s", user_id, e)

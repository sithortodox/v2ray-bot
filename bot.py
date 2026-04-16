import asyncio
import logging
from aiogram import Bot, Router, types
from aiogram.filters import Command
from database import add_user, get_working_configs, get_stats, get_all_users

logger = logging.getLogger(__name__)
router = Router()

MAX_MSG_LEN = 3800


def _format_config(cfg: dict) -> str:
    name = cfg.get("name", "unnamed")
    protocol = cfg.get("protocol", "unknown")
    raw = cfg.get("raw_config", "")
    return f"{name} [{protocol}]\n{raw}"


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
    await _send_configs(message.from_user.id, configs, header="Рабочие конфиги:", bot=message.bot)


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


async def _send_configs(user_id: int, configs: list[dict], header: str, bot: Bot):
    text = f"{header}\n\n"
    for cfg in configs:
        entry = _format_config(cfg) + "\n\n"
        if len(text) + len(entry) > MAX_MSG_LEN:
            try:
                await bot.send_message(user_id, text.rstrip())
            except Exception as e:
                logger.error("Send error to %s: %s", user_id, e)
            text = f"{header} (продолжение)\n\n"
            await asyncio.sleep(0.3)
        text += entry
    if text.strip():
        try:
            await bot.send_message(user_id, text.rstrip())
        except Exception as e:
            logger.error("Send error to %s: %s", user_id, e)


async def broadcast_new_configs(bot: Bot, configs: list[dict]):
    if not configs:
        return
    users = await get_all_users()
    for user_id in users:
        await _send_configs(user_id, configs, header="Новые рабочие конфиги:", bot=bot)
        await asyncio.sleep(0.5)


async def broadcast_dead_configs(bot: Bot, configs: list[dict]):
    if not configs:
        return
    users = await get_all_users()
    for user_id in users:
        text = f"Удалены нерабочие конфиги ({len(configs)}):\n"
        for c in configs[:30]:
            name = c.get("name", "unnamed")
            text += f"  - {name} ({c.get('protocol', '?')})\n"
        try:
            await bot.send_message(user_id, text)
        except Exception as e:
            logger.error("Send error to %s: %s", user_id, e)

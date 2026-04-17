import asyncio
import logging
from aiogram import Bot, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import add_user, get_working_configs, get_stats, get_all_users, delete_config

logger = logging.getLogger(__name__)
router = Router()


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
    await _send_configs(message.from_user.id, configs, bot=message.bot)


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


def _config_keyboard(config_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Скопировать", callback_data=f"copy:{config_id}"),
            InlineKeyboardButton(text="❌ Не работает", callback_data=f"dead:{config_id}"),
        ]
    ])


@router.callback_query(lambda c: c.data and c.data.startswith("copy:"))
async def cb_copy(callback: CallbackQuery):
    config_id = int(callback.data.split(":", 1)[1])
    from database import get_config_by_id
    cfg = await get_config_by_id(config_id)
    if not cfg:
        await callback.answer("Конфиг уже удалён", show_alert=True)
        return
    raw = cfg["raw_config"]
    await callback.answer("Конфиг скопирован в буфер обмена!", show_alert=False)
    await callback.message.answer(f"<pre>{raw}</pre>", parse_mode="HTML")


@router.callback_query(lambda c: c.data and c.data.startswith("dead:"))
async def cb_dead(callback: CallbackQuery):
    config_id = int(callback.data.split(":", 1)[1])
    from database import get_config_by_id
    cfg = await get_config_by_id(config_id)
    if not cfg:
        await callback.answer("Конфиг уже удалён", show_alert=True)
        return
    name = cfg.get("name", "unnamed")
    await delete_config(config_id)
    await callback.answer(f"Конфиг «{name}» удалён как нерабочий", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_reply(reply_markup=None)


async def _send_configs(user_id: int, configs: list[dict], bot: Bot, header: str = ""):
    if header:
        try:
            await bot.send_message(user_id, header)
        except Exception as e:
            logger.error("Send error to %s: %s", user_id, e)

    for cfg in configs:
        name = cfg.get("name", "unnamed")
        protocol = cfg.get("protocol", "?")
        raw = cfg.get("raw_config", "")
        config_id = cfg.get("id", 0)
        label = f"{name} [{protocol}]"
        kb = _config_keyboard(config_id)
        try:
            await bot.send_message(
                user_id,
                f"<b>{label}</b>\n<pre>{raw}</pre>",
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception:
            try:
                await bot.send_message(
                    user_id,
                    f"{label}\n{raw}",
                    reply_markup=kb,
                )
            except Exception as e:
                logger.error("Send error to %s: %s", user_id, e)
        await asyncio.sleep(0.5)


async def broadcast_new_configs(bot: Bot, configs: list[dict]):
    if not configs:
        return
    users = await get_all_users()
    for user_id in users:
        await _send_configs(user_id, configs, bot=bot, header="Новые рабочие конфиги:")
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

import aiosqlite
from datetime import datetime
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                protocol TEXT NOT NULL,
                raw_config TEXT NOT NULL UNIQUE,
                server TEXT NOT NULL,
                port INTEGER NOT NULL,
                name TEXT DEFAULT '',
                is_working INTEGER DEFAULT 0,
                last_checked TEXT DEFAULT NULL,
                source TEXT DEFAULT '',
                added_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def add_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
            (user_id, username, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def add_config(protocol: str, raw_config: str, server: str, port: int, name: str, source: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO configs (protocol, raw_config, server, port, name, is_working, last_checked, source, added_at) VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)",
                (protocol, raw_config, server, port, name, source, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def update_config_status(config_id: int, is_working: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE configs SET is_working = ?, last_checked = ? WHERE id = ?",
            (1 if is_working else 0, datetime.utcnow().isoformat(), config_id),
        )
        await db.commit()


async def delete_config(config_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM configs WHERE id = ?", (config_id,))
        await db.commit()


async def get_working_configs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM configs WHERE is_working = 1 ORDER BY added_at DESC") as cursor:
            return [dict(row) async for row in cursor]


async def get_unchecked_configs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM configs WHERE is_working = 0 AND last_checked IS NULL") as cursor:
            return [dict(row) async for row in cursor]


async def get_configs_to_recheck():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM configs WHERE is_working = 1") as cursor:
            return [dict(row) async for row in cursor]


async def get_config_by_raw(raw_config: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM configs WHERE raw_config = ?", (raw_config,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM configs WHERE is_working = 1") as cursor:
            working = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM configs WHERE is_working = 0") as cursor:
            not_working = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users = (await cursor.fetchone())[0]
        return {"working": working, "not_working": not_working, "users": users}

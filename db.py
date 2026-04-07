import asyncpg
from config import DATABASE_URL, log

db_pool: asyncpg.Pool = None


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=50)

    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS parents (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                phone TEXT NOT NULL,
                registered_at TIMESTAMP DEFAULT NOW(),
                is_active INTEGER DEFAULT 1
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON parents(phone)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_tg ON parents(telegram_id)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications_log (
                id SERIAL PRIMARY KEY,
                student_name TEXT, mark TEXT, date TEXT,
                phone_matched TEXT, parent_telegram_id BIGINT,
                status TEXT DEFAULT 'sent', error_message TEXT,
                sheet_name TEXT,
                sent_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_status ON notifications_log(status)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_notif_date ON notifications_log(sent_at)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS known_phones (
                id SERIAL PRIMARY KEY,
                phone TEXT NOT NULL, student_name TEXT NOT NULL,
                sheet_name TEXT, last_seen TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_kp ON known_phones(phone)")

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS error_log (
                id SERIAL PRIMARY KEY,
                error_type TEXT, message TEXT, details TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    log.info("Database connected")


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()


async def log_error(etype: str, msg: str, details: str = ""):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO error_log (error_type, message, details) VALUES($1, $2, $3)",
                etype, msg, details)
    except Exception:
        pass

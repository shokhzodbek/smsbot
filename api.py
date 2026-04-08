import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import FileResponse

from config import WEBHOOK_SECRET, ADMIN_PASSWORD, API_PORT, normalize_phone, log
import db
import sender
from telegram_bot import create_bot_and_dispatcher, setup_bot_commands


# ─── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init_db()
    os.makedirs("static", exist_ok=True)

    # Start message queue + workers
    sender.init_queue()
    workers = []
    for i in range(3):
        task = asyncio.create_task(sender.telegram_sender_worker(i))
        workers.append(task)
    log.info("Started 3 Telegram sender workers")

    bot, dp = create_bot_and_dispatcher()
    app.state.bot = bot
    app.state.dp = dp

    await setup_bot_commands(bot)
    log.info("Telegram commands menu updated")

    # Start Aiogram polling in background
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    log.info("Telegram bot polling started")
    log.info(f"Dashboard: http://localhost:{API_PORT}/admin")

    yield

    # Shutdown
    polling_task.cancel()
    for w in workers:
        w.cancel()
    await app.state.dp.stop_polling()
    await app.state.bot.session.close()
    await db.close_db()
    log.info("Shutdown complete")


app = FastAPI(title="Fast Education Bot", lifespan=lifespan)


# ─── Auth dependency ─────────────────────────────────────
def check_auth(request: Request):
    if request.headers.get("Authorization") != f"Bearer {ADMIN_PASSWORD}":
        raise HTTPException(status_code=401, detail="unauthorized")


# ─── Webhook Endpoint ────────────────────────────────────
@app.post("/webhook/grade")
async def receive_grade(request: Request):
    data = await request.json()
    if not data:
        raise HTTPException(400, "no data")
    if data.get("secret") != WEBHOOK_SECRET:
        raise HTTPException(401, "unauthorized")

    student_name = str(data.get("student_name", "")).strip()
    phone_raw = str(data.get("phone", "")).strip()
    mark = str(data.get("mark", "")).strip()
    date_str = str(data.get("date", "")).strip()
    sheet_name = str(data.get("sheet_name", "")).strip()

    if not student_name or not mark:
        raise HTTPException(400, "missing fields")

    # Track known phones
    if phone_raw:
        norm = normalize_phone(phone_raw)
        async with db.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM known_phones WHERE phone=$1 AND student_name=$2",
                norm, student_name)
            if not existing:
                await conn.execute(
                    "INSERT INTO known_phones (phone, student_name, sheet_name) VALUES($1, $2, $3)",
                    norm, student_name, sheet_name)
            else:
                await conn.execute(
                    "UPDATE known_phones SET last_seen=NOW() WHERE phone=$1 AND student_name=$2",
                    norm, student_name)

    if not phone_raw:
        await db.log_error("no_phone", f"No phone for: {student_name}")
        return {"status": "ok", "notified": 0, "reason": "no_phone"}

    normalized = normalize_phone(phone_raw)

    async with db.db_pool.acquire() as conn:
        parents = await conn.fetch(
            "SELECT DISTINCT telegram_id FROM parents WHERE phone=$1 AND is_active=1",
            normalized)

        if not parents:
            await conn.execute("""
                INSERT INTO notifications_log
                (student_name, mark, date, phone_matched, status, error_message, sheet_name)
                VALUES($1, $2, $3, $4, $5, $6, $7)
            """, student_name, mark, date_str, normalized, "undelivered", "No parent registered", sheet_name)
            return {"status": "ok", "notified": 0}

    msg = f"📝 Yangi baho!\n\n🧑‍🎓 {student_name}\n📊 Baho: {mark}\n📅 Sana: {date_str}"

    # Queue messages (non-blocking)
    for p in parents:
        await sender.message_queue.put({
            "chat_id": p["telegram_id"],
            "text": msg,
            "log_data": {
                "student_name": student_name,
                "mark": mark,
                "date": date_str,
                "phone": normalized,
                "telegram_id": p["telegram_id"],
                "sheet_name": sheet_name
            }
        })

    return {"status": "ok", "queued": len(parents)}


# ─── Admin API ───────────────────────────────────────────
@app.get("/api/stats")
async def api_stats(request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        stats = {}
        stats["total_parents"] = await conn.fetchval("SELECT COUNT(*) FROM parents WHERE is_active=1")
        stats["total_phones"] = await conn.fetchval("SELECT COUNT(DISTINCT phone) FROM parents WHERE is_active=1")
        stats["total_notifications"] = await conn.fetchval("SELECT COUNT(*) FROM notifications_log")
        stats["sent"] = await conn.fetchval("SELECT COUNT(*) FROM notifications_log WHERE status='sent'")
        stats["failed"] = await conn.fetchval("SELECT COUNT(*) FROM notifications_log WHERE status='failed'")
        stats["undelivered"] = await conn.fetchval("SELECT COUNT(*) FROM notifications_log WHERE status='undelivered'")
        stats["today"] = await conn.fetchval("SELECT COUNT(*) FROM notifications_log WHERE DATE(sent_at)=CURRENT_DATE")
        stats["known_phones"] = await conn.fetchval("SELECT COUNT(DISTINCT phone) FROM known_phones")
        stats["errors"] = await conn.fetchval("SELECT COUNT(*) FROM error_log")
        stats["connected"] = await conn.fetchval("""
            SELECT COUNT(DISTINCT kp.phone) FROM known_phones kp
            INNER JOIN parents p ON kp.phone=p.phone AND p.is_active=1""")
        stats["unconnected"] = stats["known_phones"] - stats["connected"]
        stats["queue_size"] = sender.message_queue.qsize() if sender.message_queue else 0
    return stats


@app.get("/api/parents")
async def api_parents(request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, telegram_id, phone, registered_at, is_active FROM parents ORDER BY registered_at DESC")
    return [{"id": r["id"], "telegram_id": r["telegram_id"], "phone": r["phone"],
             "registered_at": str(r["registered_at"]), "is_active": r["is_active"]} for r in rows]


@app.delete("/api/parents/{pid}")
async def api_delete_parent(pid: int, request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE parents SET is_active=0 WHERE id=$1", pid)
    return {"status": "ok"}


@app.post("/api/parents/{pid}/activate")
async def api_activate_parent(pid: int, request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        await conn.execute("UPDATE parents SET is_active=1 WHERE id=$1", pid)
    return {"status": "ok"}


@app.get("/api/unconnected")
async def api_unconnected(request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT kp.phone, kp.student_name, kp.sheet_name, kp.last_seen
            FROM known_phones kp LEFT JOIN parents p ON kp.phone=p.phone AND p.is_active=1
            WHERE p.id IS NULL ORDER BY kp.last_seen DESC""")
    return [{"phone": r["phone"], "student_name": r["student_name"],
             "sheet_name": r["sheet_name"], "last_seen": str(r["last_seen"])} for r in rows]


@app.get("/api/notifications")
async def api_notifications(request: Request, limit: int = 100, status: str = "", _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM notifications_log WHERE status=$1 ORDER BY sent_at DESC LIMIT $2",
                status, limit)
        else:
            rows = await conn.fetch(
                "SELECT * FROM notifications_log ORDER BY sent_at DESC LIMIT $1", limit)
    return [dict(r) for r in rows]


@app.get("/api/errors")
async def api_errors(request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM error_log ORDER BY created_at DESC LIMIT 50")
    return [dict(r) for r in rows]


@app.post("/api/errors/clear")
async def api_clear_errors(request: Request, _=Depends(check_auth)):
    async with db.db_pool.acquire() as conn:
        await conn.execute("DELETE FROM error_log")
    return {"status": "ok"}


@app.get("/admin")
@app.get("/admin/")
async def admin_page():
    return FileResponse("static/admin.html")


@app.get("/health")
async def health():
    return {
        "status": "running",
        "queue_size": sender.message_queue.qsize() if sender.message_queue else 0,
        "db_pool": f"{db.db_pool.get_size()}/{db.db_pool.get_max_size()}" if db.db_pool else "N/A"
    }

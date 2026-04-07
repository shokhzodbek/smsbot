import asyncio
import httpx
from config import BOT_TOKEN, TG_RATE_LIMIT, TG_RETRY_ATTEMPTS, log
import db

message_queue: asyncio.Queue = None


def init_queue():
    global message_queue
    message_queue = asyncio.Queue()


async def telegram_sender_worker(worker_id: int):
    """Background worker that sends Telegram messages with rate limiting and retry"""
    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    min_interval = 1.0 / TG_RATE_LIMIT

    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                item = await message_queue.get()
            except asyncio.CancelledError:
                break

            chat_id = item["chat_id"]
            text = item["text"]
            log_data = item["log_data"]

            for attempt in range(TG_RETRY_ATTEMPTS):
                try:
                    resp = await client.post(tg_url, json={
                        "chat_id": chat_id,
                        "text": text
                    })
                    data = resp.json()

                    if resp.status_code == 200 and data.get("ok"):
                        await _log_notification(log_data, "sent", "")
                        break
                    elif resp.status_code == 429:
                        retry_after = data.get("parameters", {}).get("retry_after", 5)
                        log.warning(f"[Worker-{worker_id}] Rate limited, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                    else:
                        if attempt == TG_RETRY_ATTEMPTS - 1:
                            await _log_notification(log_data, "failed", resp.text)
                except Exception as e:
                    if attempt == TG_RETRY_ATTEMPTS - 1:
                        await _log_notification(log_data, "failed", str(e))
                        await db.log_error("send_failed", f"tg:{chat_id}", str(e))
                    await asyncio.sleep(1)

            await asyncio.sleep(min_interval)
            message_queue.task_done()


async def _log_notification(data: dict, status: str, error_msg: str):
    try:
        async with db.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO notifications_log
                (student_name, mark, date, phone_matched, parent_telegram_id, status, error_message, sheet_name)
                VALUES($1, $2, $3, $4, $5, $6, $7, $8)
            """, data["student_name"], data["mark"], data["date"],
                data["phone"], data.get("telegram_id"), status, error_msg,
                data.get("sheet_name", ""))
    except Exception as e:
        log.error(f"Failed to log notification: {e}")

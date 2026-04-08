from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, ReplyKeyboardRemove, BotCommand
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, normalize_phone
import db

router = Router()


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    return bot, dp


async def setup_bot_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushurish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="register", description="Ro'yxatdan o'tish"),
        BotCommand(command="status", description="Holatni ko'rish"),
        BotCommand(command="unregister", description="Bildirishnomani o'chirish"),
    ])


class Registration(StatesGroup):
    phone_input = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Assalomu alaykum!\n"
        "Fast Education bildirishnoma boti.\n\n"
        "📱 /register — Ro'yxatdan o'tish\n"
        "📋 /status — Holat\n"
        "🛑 /unregister — To'xtatish",
        reply_markup=ReplyKeyboardRemove())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 /register → jurnaldagi telefon raqamni kiriting.\n"
        "O'qituvchi baho qo'yadi → sizga xabar keladi.\n"
        "⚠️ Raqam jurnaldagi bilan bir xil bo'lishi shart!",
        reply_markup=ReplyKeyboardRemove())


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT phone FROM parents WHERE telegram_id=$1 AND is_active=1",
            message.from_user.id)
    if rows:
        phones = ", ".join([r["phone"] for r in rows])
        await message.answer(f"✅ Ro'yxatdasiz: {phones}\nYana qo'shish uchun davom eting. /cancel — bekor")

    await message.answer(
        "📱 Jurnaldagi telefon raqamni kiriting:\n"
        "Masalan: +998901234567\n\n"
        "⚠️ Google Sheets dagi raqam bilan BIR XIL bo'lishi kerak!",
        reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.phone_input)


@router.message(Registration.phone_input, Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())


@router.message(Registration.phone_input)
async def phone_received(message: Message, state: FSMContext):
    normalized = normalize_phone(message.text.strip())
    if len(normalized) < 12:
        await message.answer("❌ Raqam noto'g'ri. Masalan: +998901234567")
        return

    async with db.db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM parents WHERE telegram_id=$1 AND phone=$2 AND is_active=1",
            message.from_user.id, normalized)
        if existing:
            await message.answer(
                f"⚠️ {normalized} allaqachon ro'yxatda.",
                reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return

        await conn.execute(
            "INSERT INTO parents (telegram_id, phone) VALUES($1, $2)",
            message.from_user.id, normalized)

    await message.answer(
        f"✅ Ro'yxatdan o'tdingiz!\n📱 {normalized}",
        reply_markup=ReplyKeyboardRemove())
    await state.clear()


@router.message(Command("status"))
async def cmd_status(message: Message):
    async with db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT phone FROM parents WHERE telegram_id=$1 AND is_active=1",
            message.from_user.id)
    if not rows:
        await message.answer("❌ Ro'yxatda emassiz. /register", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        "✅ Raqamlaringiz:\n" + "\n".join([f"📱 {r['phone']}" for r in rows]),
        reply_markup=ReplyKeyboardRemove())


@router.message(Command("unregister"))
async def cmd_unregister(message: Message):
    async with db.db_pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE parents SET is_active=0 WHERE telegram_id=$1 AND is_active=1",
            message.from_user.id)
    count = int(result.split()[-1])
    await message.answer(
        "✅ To'xtatildi." if count else "❌ Ro'yxatda emassiz.",
        reply_markup=ReplyKeyboardRemove())



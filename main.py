import asyncio
import os
import time
from uuid import uuid4
from dotenv import load_dotenv

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, InlineQuery, InlineQueryResultArticle,
    InputTextMessageContent
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from database import (
    init_db, register_user, get_term, get_random_term, get_terms_by_level,
    add_search_history, get_user_history, add_favorite, remove_favorite,
    is_favorite, get_favorites, get_similar_terms, get_total_terms,
    get_total_users, get_top_terms, add_term, update_term, delete_term,
    get_level_label
)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@muxlissarajabboyeva")

# Faqat o'zingizning Telegram IDingizni yozing
ADMIN_IDS = [7918392848]

COOLDOWN_SECONDS = 1.0

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. Render Environment Variables ga qo‘ying.")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

user_data = {}
last_message_time = {}


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Random termin"), KeyboardButton(text="📚 Darajalar")],
            [KeyboardButton(text="⭐ Sevimlilar"), KeyboardButton(text="🕘 Tarix")],
            [KeyboardButton(text="ℹ️ Bot haqida"), KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )


def join_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga a'zo bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
        ]
    )


def levels_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 Boshlang‘ich", callback_data="level_beginner")],
            [InlineKeyboardButton(text="🟡 O‘rta", callback_data="level_intermediate")],
            [InlineKeyboardButton(text="🔴 Murakkab", callback_data="level_advanced")]
        ]
    )


def term_keyboard(user_id: int, english_word: str):
    fav_text = "💔 Saqlangan" if is_favorite(user_id, english_word) else "⭐ Saqlash"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📘 To‘liq nomi", callback_data="full"),
                InlineKeyboardButton(text="🌐 Tarjimasi", callback_data="uz")
            ],
            [
                InlineKeyboardButton(text="💬 Izohi", callback_data="exp"),
                InlineKeyboardButton(text="🧩 Misoli", callback_data="ex")
            ],
            [
                InlineKeyboardButton(text="📚 Barchasi", callback_data="all")
            ],
            [
                InlineKeyboardButton(text=fav_text, callback_data="fav_toggle")
            ]
        ]
    )


async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False


def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    last = last_message_time.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return True
    last_message_time[user_id] = now
    return False


def format_term(term, section: str = "preview") -> str:
    english = (term["english_word"] or "").upper()
    full_form = term["full_form"] or "—"
    uzbek_translation = term["uzbek_translation"] or "—"
    explanation = term["explanation"] or "—"
    example = term["example"] or "—"
    level = get_level_label(term["level"] or "—")

    if section == "preview":
        return (
            f"🔍 <b>Termin topildi:</b> <code>{english}</code>\n\n"
            "Kerakli bo‘limni tanlang."
        )
    if section == "full":
        return f"📘 <b>Termin:</b> <code>{english}</code>\n\n<b>To‘liq nomi:</b>\n{full_form}"
    if section == "uz":
        return f"🌐 <b>Termin:</b> <code>{english}</code>\n\n<b>Tarjimasi:</b>\n{uzbek_translation}"
    if section == "exp":
        return f"💬 <b>Termin:</b> <code>{english}</code>\n\n<b>Izohi:</b>\n{explanation}"
    if section == "ex":
        return f"🧩 <b>Termin:</b> <code>{english}</code>\n\n<b>Misoli:</b>\n{example}"
    if section == "all":
        return (
            f"📘 <b>Termin:</b> <code>{english}</code>\n\n"
            f"<b>To‘liq nomi:</b>\n{full_form}\n\n"
            f"<b>Tarjimasi:</b>\n{uzbek_translation}\n\n"
            f"<b>Izohi:</b>\n{explanation}\n\n"
            f"<b>Misoli:</b>\n{example}\n\n"
            f"<b>Daraja:</b>\n{level}"
        )
    return "Ma'lumot topilmadi."


async def ensure_access(message: Message) -> bool:
    register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "🔒 <b>Botdan foydalanish uchun avval kanalga a'zo bo‘ling.</b>\n\n"
            "A'zo bo‘lgach, <b>Tekshirish</b> tugmasini bosing.",
            reply_markup=join_keyboard()
        )
        return False

    if is_rate_limited(message.from_user.id):
        await message.answer("⏳ Juda tez xabar yuboryapsiz. Bir oz kutib, qayta urinib ko‘ring.")
        return False

    return True


@dp.message(CommandStart())
async def start_handler(message: Message):
    register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "🔒 <b>Botdan foydalanish uchun avval kanalga a'zo bo‘ling.</b>\n\n"
            "A'zo bo‘lgach, <b>Tekshirish</b> tugmasini bosing.",
            reply_markup=join_keyboard()
        )
        return

    await message.answer(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "Bu bot orqali IT terminlarning:\n"
        "• to‘liq nomi\n"
        "• tarjimasi\n"
        "• izohi\n"
        "• misoli\n"
        "bilan tanishishingiz mumkin.\n\n"
        "📌 Termin yuboring yoki pastdagi menyudan foydalaning.",
        reply_markup=main_menu()
    )


@dp.message(Command("about"))
@dp.message(F.text == "ℹ️ Bot haqida")
async def about_handler(message: Message):
    if not await ensure_access(message):
        return

    await message.answer(
        "ℹ️ <b>Bot haqida</b>\n\n"
        "Bu bot IT terminlarni o‘rganish uchun mo‘ljallangan.\n\n"
        "Imkoniyatlari:\n"
        "• termin qidirish\n"
        "• random termin\n"
        "• daraja bo‘yicha ko‘rish\n"
        "• sevimlilar\n"
        "• qidiruv tarixi\n"
        "• inline qidiruv\n\n"
        "Yangi terminlar uchun kanalni kuzatib boring."
    )


@dp.message(Command("random"))
@dp.message(F.text == "🎲 Random termin")
async def random_handler(message: Message):
    if not await ensure_access(message):
        return

    term = get_random_term()
    if not term:
        await message.answer("Hozircha bazada terminlar yo‘q.")
        return

    user_data[message.from_user.id] = term
    add_search_history(message.from_user.id, term["english_word"])

    await message.answer(
        format_term(term, "preview"),
        reply_markup=term_keyboard(message.from_user.id, term["english_word"])
    )


@dp.message(Command("levels"))
@dp.message(F.text == "📚 Darajalar")
async def levels_handler(message: Message):
    if not await ensure_access(message):
        return

    await message.answer(
        "📚 <b>Darajani tanlang:</b>",
        reply_markup=levels_keyboard()
    )


@dp.message(Command("favorites"))
@dp.message(F.text == "⭐ Sevimlilar")
async def favorites_handler(message: Message):
    if not await ensure_access(message):
        return

    favorites = get_favorites(message.from_user.id, limit=15)
    if not favorites:
        await message.answer("⭐ Hozircha sevimli terminlaringiz yo‘q.")
        return

    text = "⭐ <b>Sevimli terminlaringiz:</b>\n\n"
    text += "\n".join([f"• <code>{item['english_word'].upper()}</code>" for item in favorites])
    await message.answer(text)


@dp.message(Command("history"))
@dp.message(F.text == "🕘 Tarix")
async def history_handler(message: Message):
    if not await ensure_access(message):
        return

    history = get_user_history(message.from_user.id, limit=15)
    if not history:
        await message.answer("🕘 Hozircha qidiruv tarixi yo‘q.")
        return

    unique_terms = []
    seen = set()
    for item in history:
        word = item["english_word"]
        if word not in seen:
            seen.add(word)
            unique_terms.append(word)

    text = "🕘 <b>Oxirgi qidiruvlaringiz:</b>\n\n"
    text += "\n".join([f"• <code>{word.upper()}</code>" for word in unique_terms[:10]])
    await message.answer(text)


@dp.message(Command("stats"))
@dp.message(F.text == "📊 Statistika")
async def stats_handler(message: Message):
    if not await ensure_access(message):
        return

    total_terms = get_total_terms()
    total_users = get_total_users()
    top_terms = get_top_terms(limit=5)

    text = (
        "📊 <b>Bot statistikasi</b>\n\n"
        f"• Terminlar soni: <b>{total_terms}</b>\n"
        f"• Foydalanuvchilar soni: <b>{total_users}</b>\n\n"
        "<b>Eng ko‘p qidirilgan terminlar:</b>\n"
    )

    if top_terms:
        for i, item in enumerate(top_terms, start=1):
            text += f"{i}. <code>{item['english_word'].upper()}</code> — {item['search_count']} ta\n"
    else:
        text += "Hozircha ma'lumot yo‘q."

    await message.answer(text)


@dp.message(Command("addterm"))
async def addterm_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        payload = message.text.split(" ", 1)[1]
        english_word, full_form, uzbek_translation, explanation, example, level = payload.split("|", 5)
        add_term(english_word, full_form, uzbek_translation, explanation, example, level)
        await message.answer("✅ Termin qo‘shildi.")
    except Exception:
        await message.answer(
            "❌ Format xato.\n\n"
            "To‘g‘ri format:\n"
            "<code>/addterm english|full form|tarjima|izoh|misol|level</code>"
        )


@dp.message(Command("editterm"))
async def editterm_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        payload = message.text.split(" ", 1)[1]
        english_word, full_form, uzbek_translation, explanation, example, level = payload.split("|", 5)
        ok = update_term(english_word, full_form, uzbek_translation, explanation, example, level)
        await message.answer("✅ Termin yangilandi." if ok else "❌ Bunday termin topilmadi.")
    except Exception:
        await message.answer(
            "❌ Format xato.\n\n"
            "To‘g‘ri format:\n"
            "<code>/editterm english|full form|tarjima|izoh|misol|level</code>"
        )


@dp.message(Command("delterm"))
async def delterm_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        english_word = message.text.split(" ", 1)[1].strip()
        ok = delete_term(english_word)
        await message.answer("🗑 Termin o‘chirildi." if ok else "❌ Bunday termin topilmadi.")
    except Exception:
        await message.answer("❌ Format xato.\n\nTo‘g‘ri format:\n<code>/delterm api</code>")


@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: CallbackQuery):
    if await is_subscribed(callback.from_user.id):
        try:
            await callback.message.edit_text(
                "✅ <b>Obuna tasdiqlandi.</b>\n\n"
                "Endi istalgan IT terminni yuboring yoki pastdagi menyudan foydalaning."
            )
        except Exception:
            await callback.message.answer("✅ <b>Obuna tasdiqlandi.</b>")
        await callback.answer()
    else:
        await callback.answer("Siz hali kanalga a'zo bo‘lmagansiz.", show_alert=True)


@dp.callback_query(F.data.startswith("level_"))
async def level_callback_handler(callback: CallbackQuery):
    level = callback.data.replace("level_", "")
    terms = get_terms_by_level(level, limit=10)

    if not terms:
        await callback.answer("Bu darajada terminlar topilmadi.", show_alert=True)
        return

    text = f"📚 <b>{get_level_label(level)} darajadagi terminlar:</b>\n\n"
    text += "\n".join([f"• <code>{item['english_word'].upper()}</code>" for item in terms])
    text += "\n\nIstalganini yuboring."

    try:
        await callback.message.edit_text(text, reply_markup=levels_keyboard())
    except Exception:
        await callback.message.answer(text, reply_markup=levels_keyboard())

    await callback.answer()


@dp.message()
async def search_term(message: Message):
    if not await ensure_access(message):
        return

    text = message.text.strip()

    if text in ["🎲 Random termin", "📚 Darajalar", "⭐ Sevimlilar", "🕘 Tarix", "ℹ️ Bot haqida", "📊 Statistika"]:
        return

    term = get_term(text)

    if not term:
        similar = get_similar_terms(text, limit=5)
        if similar:
            suggestion_text = "\n".join([f"• <code>{w.upper()}</code>" for w in similar])
            await message.answer(
                "❌ <b>Bunday termin topilmadi.</b>\n\n"
                "Balki shulardan birini nazarda tutgandirsiz:\n\n"
                f"{suggestion_text}"
            )
        else:
            await message.answer(
                "❌ <b>Bunday termin topilmadi.</b>\n\n"
                "Iltimos, boshqa termin yuboring yoki yozilishini tekshirib ko‘ring."
            )
        return

    user_data[message.from_user.id] = term
    add_search_history(message.from_user.id, term["english_word"])

    await message.answer(
        format_term(term, "preview"),
        reply_markup=term_keyboard(message.from_user.id, term["english_word"])
    )


@dp.callback_query(F.data.in_(["full", "uz", "exp", "ex", "all", "fav_toggle"]))
async def term_buttons_handler(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in user_data:
        await callback.answer("Avval termin yuboring.", show_alert=True)
        return

    term = user_data[user_id]
    english_word = term["english_word"]

    if callback.data == "fav_toggle":
        if is_favorite(user_id, english_word):
            remove_favorite(user_id, english_word)
            await callback.answer("Sevimlilardan olib tashlandi.")
        else:
            add_favorite(user_id, english_word)
            await callback.answer("Sevimlilarga saqlandi.")

        try:
            await callback.message.edit_reply_markup(
                reply_markup=term_keyboard(user_id, english_word)
            )
        except Exception:
            pass
        return

    try:
        await callback.message.edit_text(
            format_term(term, callback.data),
            reply_markup=term_keyboard(user_id, english_word)
        )
    except Exception:
        await callback.message.answer(
            format_term(term, callback.data),
            reply_markup=term_keyboard(user_id, english_word)
        )

    await callback.answer()


@dp.inline_query()
async def inline_query_handler(inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query:
        return

    results = []
    term = get_term(query)

    if term:
        text = format_term(term, "all")
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=f"{term['english_word'].upper()}",
                description=term["uzbek_translation"],
                input_message_content=InputTextMessageContent(message_text=text)
            )
        )
    else:
        similar = get_similar_terms(query, limit=5)
        for word in similar:
            t = get_term(word)
            if t:
                text = format_term(t, "all")
                results.append(
                    InlineQueryResultArticle(
                        id=str(uuid4()),
                        title=f"{t['english_word'].upper()}",
                        description=t["uzbek_translation"],
                        input_message_content=InputTextMessageContent(message_text=text)
                    )
                )

    await inline_query.answer(results, cache_time=1, is_personal=True)


async def handle(request):
    return web.Response(text="Bot is running")


async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    init_db()
    await start_webserver()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import random
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# --- ВЕБ-СЕРВЕР ДЛЯ ОБХОДА БЛОКИРОВКИ RENDER ---
class SimpleWeb(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleWeb)
    server.serve_forever()
# -----------------------------------------------

TOKEN = '8787908421:AAGOCR_ka0qZWqHmtMMlBWVjexGrN9geQ2M'  # Сюда твой токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных прямо в памяти (без создания файлов)
users_db = {}
used_promos_db = {}
bonus_timers = {}
anti_spam = {} 

quiz_current = {"question": None, "answer": None, "reward": 0, "active": False}

PROMO_CODES = {
    "START2026": 500,
    "BONUS777": 1000,
    "FREECOINS": 300,
    "MILLION": 1000000
}

class PromoStates(StatesGroup):
    waiting_for_promo = State()

def get_ping(message: Message) -> str:
    if message.from_user.username:
        return f"@{message.from_user.username}"
    return f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"

# Намертво рабочий антиспам (интервал 2 секунды)
def is_spamming(user_id: int) -> bool:
    current_time = time.time()
    if user_id in anti_spam:
        last_time = anti_spam[user_id]
        if current_time - last_time < 2.0:
            return True
    anti_spam[user_id] = current_time
    return False

def get_user_data(user_id: int, username: str = None):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 1000, "bet": 100, "username": username}
    if username and users_db[user_id]["username"] != username:
        users_db[user_id]["username"] = username
    if user_id not in used_promos_db:
        used_promos_db[user_id] = []
    if user_id not in bonus_timers:
        bonus_timers[user_id] = {"hourly": 0, "daily": 0}
    return users_db[user_id]

def get_keyboard():
    kb = [
        [KeyboardButton(text="🎰 Рулетка"), KeyboardButton(text="⚽ Футбол"), KeyboardButton(text="🎯 Дартс")],
        [KeyboardButton(text="⏱ Часовой бонус"), KeyboardButton(text="📅 Дневной бонус")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🎁 Промокод")],
        [KeyboardButton(text="➕ Повысить ставку"), KeyboardButton(text="➖ Снизить ставку")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def try_trigger_quiz(message: Message):
    if quiz_current["active"] or random.random() > 0.3:
        return
    num1 = random.randint(10, 99)
    num2 = random.randint(10, 99)
    operation = random.choice(["+", "-"])
    ans = num1 + num2 if operation == "+" else num1 - num2
    
    quiz_current["question"] = f"{num1} {operation} {num2}"
    quiz_current["answer"] = str(ans)
    quiz_current["reward"] = random.randint(300, 1500)
    quiz_current["active"] = True
    
    await message.answer(
        f"🔔 *БЫСТРЫЙ ИВЕНТ ДЛЯ ВСЕХ!*\n\nКто первый решит пример, получит куш!\n📊 Пример: *{quiz_current['question']} = ?*\n💰 Награда: *{quiz_current['reward']}* коинов!\n\nНапишите просто число-ответ в чат!",
        parse_mode="Markdown"
    )

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    await state.clear()
    user = get_user_data(message.from_user.id, message.from_user.username)
    await message.answer(
        f"👋 Привет, {get_ping(message)}!\nБот работает в облаке 24/7. Включен антиспам и пинги!\n\n"
        f"💰 Твой баланс: *{user['balance']}* коинов.\n💵 Текущая ставка: *{user['bet']}* коинов.",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = get_user_data(message.from_user.id, message.from_user.username)
    await message.answer(f"💳 {get_ping(message)}, твой баланс: *{user['balance']}* коинов\n💵 Ставка: *{user['bet']}* коинов", parse_mode="Markdown")
    await try_trigger_quiz(message)

@dp.message(F.text == "➕ Повысить ставку")
async def raise_bet(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = get_user_data(message.from_user.id, message.from_user.username)
    user['bet'] += 50
    await message.answer(f"📈 {get_ping(message)}, ставка увеличена! Новая ставка: *{user['bet']}* коинов", parse_mode="Markdown")

@dp.message(F.text == "➖ Снизить ставку")
async def lower_bet(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = get_user_data(message.from_user.id, message.from_user.username)
    if user['bet'] <= 50:
        await message.answer(f"⚠️ {get_ping(message)}, минимальная ставка — 50 коинов!", parse_mode="Markdown")
        return
    user['bet'] -= 50
    await message.answer(f"📉 {get_ping(message)}, ставка снижена! Новая ставка: *{user['bet']}* коинов", parse_mode="Markdown")

@dp.message(F.text == "⏱ Часовой бонус")
async def hourly_bonus(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    if current_time - bonus_timers[user_id]["hourly"] < 3600:
        left = int(3600 - (current_time - bonus_timers[user_id]["hourly"]))
        await message.answer(f"⏳ {get_ping(message)}, рано! Подожди еще {left // 60} мин. {left % 60} сек.", parse_mode="Markdown")
        return
    user["balance"] += 500
    bonus_timers[user_id]["hourly"] = current_time
    await message.answer(f"🎉 {get_ping(message)}, ты получил +500 коинов!\n💰 Баланс: *{user['balance']}* коинов.", parse_mode="Markdown")

@dp.message(F.text == "📅 Дневной бонус")
async def daily_bonus(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    if current_time - bonus_timers[user_id]["daily"] < 86400:
        left = int(86400 - (current_time - bonus_timers[user_id]["daily"]))
        await message.answer(f"⏳ {get_ping(message)}, рано! Подожди еще {left // 3600} ч. {(left % 3600) // 60} мин.", parse_mode="Markdown")
        return
    user["balance"] += 5000
    bonus_timers[user_id]["daily"] = current_time
    await message.answer(f"🎉 {get_ping(message)}, ты получил +5000 коинов!\n💰 Баланс: *{user['balance']}* коинов.", parse_mode="Markdown")

@dp.message(F.text == "🎁 Промокод")
async def enter_promo_request(message: Message, state: FSMContext):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    await message.answer(f"✍️ {get_ping(message)}, введите промокод:", parse_mode="Markdown")
    await state.set_state(PromoStates.waiting_for_promo)

@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    promo_text = message.text.strip().upper()
    if promo_text not in PROMO_CODES:
        await message.answer(f"❌ {get_ping(message)}, такого промокода нет!", parse_mode="Markdown")
        await state.clear()
        return
    if promo_text in used_promos_db[user_id]:
        await message.answer(f"⚠️ {get_ping(message)}, вы уже активировали его!", parse_mode="Markdown")
        await state.clear()
        return
    bonus = PROMO_CODES[promo_text]
    user['balance'] += bonus
    used_promos_db[user_id].append(promo_text)
    await message.answer(f"🎉 {get_ping(message)}, активировано! +*{bonus}* коинов. Баланс: *{user['balance']}*", parse_mode="Markdown")
    await state.clear()

async def play_game(message: Message, emoji: str, win_values: list):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    bet = user['bet']
    if user['balance'] < bet:
        await message.answer(f"❌ {get_ping(message)}, недостаточно коинов для игры!", parse_mode="Markdown")
        return
    msg = await message.answer_dice(emoji=emoji)
    value = msg.dice.value
    await asyncio.sleep(4)
    if value in win_values:
        multiplier = random.randint(2, 10)
        win_amount = bet * multiplier
        user['balance'] += win_amount
        await message.answer(f"🎉 ПОБЕДА! {get_ping(message)}\n🎲 Выпало: {value}\n🔥 Множитель: **x{multiplier}**\n➕ Получено: +*{win_amount}* коинов\n💰 Баланс: *{user['balance']}* коинов", parse_mode="Markdown")
    else:
        user['balance'] -= bet
        if user['balance'] < 0: user['balance'] = 0

import asyncio
import random
import time
import os
import threading
import sqlite3
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

# --- РАБОТА С БАЗОЙ ДАННЫХ SQLITE ---
DB_FILE = "casino_base.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1000,
            bet INTEGER DEFAULT 100,
            last_hourly INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0
        )
    """)
    # Таблица использованных промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS used_promos (
            user_id INTEGER,
            promo TEXT,
            PRIMARY KEY (user_id, promo)
        )
    """)
    conn.commit()
    conn.close()

init_db()
# -----------------------------------------------

TOKEN = '8787908421:AAFEVIkl157AYeUGxGqSsEaCl8WSKJeMEao'  # Сюда твой токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

def is_spamming(user_id: int) -> bool:
    current_time = time.time()
    if user_id in anti_spam:
        last_time = anti_spam[user_id]
        if current_time - last_time < 2.0:
            return True
    anti_spam[user_id] = current_time
    return False

# Функции быстрого получения и обновления данных в БД
def db_get_user(user_id: int, username: str = None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, bet, last_hourly, last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        conn.commit()
        row = (1000, 100, 0, 0)
    elif username:
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()
    conn.close()
    return {"balance": row[0], "bet": row[1], "last_hourly": row[2], "last_daily": row[3]}

def db_update_user(user_id: int, balance: int, bet: int, last_hourly: int, last_daily: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET balance = ?, bet = ?, last_hourly = ?, last_daily = ? 
        WHERE user_id = ?
    """, (balance, bet, last_hourly, last_daily, user_id))
    conn.commit()
    conn.close()

def db_check_promo(user_id: int, promo: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM used_promos WHERE user_id = ? AND promo = ?", (user_id, promo))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def db_use_promo(user_id: int, promo: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO used_promos (user_id, promo) VALUES (?, ?)", (user_id, promo))
    conn.commit()
    conn.close()

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
    user = db_get_user(message.from_user.id, message.from_user.username)
    await message.answer(
        f"👋 Привет, {get_ping(message)}!\nБот работает 24/7. Включена база данных, антиспам и пинги!\n\n"
        f"💰 Твой реальный баланс: *{user['balance']}* коинов.\n💵 Ставка: *{user['bet']}* коинов.",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = db_get_user(message.from_user.id, message.from_user.username)
    await message.answer(f"💳 {get_ping(message)}, твой баланс: *{user['balance']}* коинов\n💵 Ставка: *{user['bet']}* коинов", parse_mode="Markdown")
    await try_trigger_quiz(message)

@dp.message(F.text == "➕ Повысить ставку")
async def raise_bet(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = db_get_user(message.from_user.id, message.from_user.username)
    user['bet'] += 50
    db_update_user(message.from_user.id, user['balance'], user['bet'], user['last_hourly'], user['last_daily'])
    await message.answer(f"📈 {get_ping(message)}, ставка увеличена! Новая ставка: *{user['bet']}* коинов", parse_mode="Markdown")

@dp.message(F.text == "➖ Снизить ставку")
async def lower_bet(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user = db_get_user(message.from_user.id, message.from_user.username)
    if user['bet'] <= 50:
        await message.answer(f"⚠️ {get_ping(message)}, минимальная ставка — 50 коинов!", parse_mode="Markdown")
        return
    user['bet'] -= 50
    db_update_user(message.from_user.id, user['balance'], user['bet'], user['last_hourly'], user['last_daily'])
    await message.answer(f"📉 {get_ping(message)}, ставка снижена! Новая ставка: *{user['bet']}* коинов", parse_mode="Markdown")

@dp.message(F.text == "⏱ Часовой бонус")
async def hourly_bonus(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    user = db_get_user(user_id, message.from_user.username)
    current_time = int(time.time())
    if current_time - user["last_hourly"] < 3600:
        left = 3600 - (current_time - user["last_hourly"])
        await message.answer(f"⏳ {get_ping(message)}, рано! Подожди еще {left // 60} мин. {left % 60} сек.", parse_mode="Markdown")
        return
    user["balance"] += 500
    db_update_user(user_id, user["balance"], user["bet"], current_time, user["last_daily"])
    await message.answer(f"🎉 {get_ping(message)}, ты получил +500 коинов!\n💰 Баланс: *{user['balance']}* коинов.", parse_mode="Markdown")

@dp.message(F.text == "📅 Дневной бонус")
async def daily_bonus(message: Message):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    user_id = message.from_user.id
    user = db_get_user(user_id, message.from_user.username)
    current_time = int(time.time())
    if current_time - user["last_daily"] < 86400:
        left = 86400 - (current_time - user["last_daily"])
        await message.answer(f"⏳ {get_ping(message)}, рано! Подожди еще {left // 3600} ч. {(left % 3600) // 60} мин.", parse_mode="Markdown")
        return
    user["balance"] += 5000
    db_update_user(user_id, user["balance"], user["bet"], user["last_hourly"], current_time)
    await message.answer(f"🎉 {get_ping(message)}, ты получил +5000 коинов!\n💰 Баланс: *{user['balance']}* коинов.", parse_mode="Markdown")

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("перевод"))
async def transfer_money(message: Message):
    if is_spamming(message.from_user.id): return
    if not message.reply_to_message:
        await message.answer(f"⚠️ {get_ping(message)}, команда работает как ответ на сообщение друга!", parse_mode="Markdown")
        return
    from_user_id = message.from_user.id

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

TOKEN = 'ВАШ_ТОКЕН_БОТА'  # Сюда ваш токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

users_db = {}
used_promos_db = {}
bonus_timers = {}

# Словари для антиспама и викторины
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

# Безопасный пинг пользователя (по username или по имени)
def get_ping(message: Message) -> str:
    if message.from_user.username:
        return f"@{message.from_user.username}"
    return f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"

# Проверка на спам (КД 2 секунды)
def is_spamming(user_id: int) -> bool:
    current_time = time.time()
    if user_id in anti_spam:
        last_time = anti_spam[user_id]
        if current_time - last_time < 2.0:
            anti_spam[user_id] = current_time
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

# Автоматическая генерация примеров в фоне
async def quiz_loop():
    await asyncio.sleep(10)  # Даем боту время запуститься
    while True:
        # Случайное время между примерами (от 3 до 7 минут, чтобы не спамило слишком часто)
        await asyncio.sleep(random.randint(180, 420))
        
        if quiz_current["active"]:
            continue
            
        num1 = random.randint(10, 99)
        num2 = random.randint(10, 99)
        operation = random.choice(["+", "-"])
        
        if operation == "+":
            ans = num1 + num2
        else:
            ans = num1 - num2
            
        quiz_current["question"] = f"{num1} {operation} {num2}"
        quiz_current["answer"] = str(ans)
        quiz_current["reward"] = random.randint(300, 1500)
        quiz_current["active"] = True
        
        # Рассылаем пример во все активные чаты, где зарегистрирован хоть один юзер
        for u_id in list(users_db.keys()):
            try:
                await bot.send_message(
                    chat_id=u_id,
                    text=f"🔔 *БЫСТРЫЙ ИВЕНТ!*\n\nКто первый решит пример, получит куш!\n📊 Пример: *{quiz_current['question']} = ?*\n💰 Награда: *{quiz_current['reward']}* коинов!\n\nНапишите просто число-ответ в чат!",
                    parse_mode="Markdown"
                )
                break # Отправляем один раз, если это группа — бот отправит в чат
            except Exception:
                pass

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    if is_spamming(message.from_user.id):
        await message.answer(f"⚠️ {get_ping(message)}, НЕ СПАМЬ ИПАТЬ!", parse_mode="Markdown")
        return
    await state.clear()
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    
    await message.answer(
        f"👋 Привет, {get_ping(message)}!\nБот полностью обновлен и защищен от багов.\n\n"
        f"💰 Твой баланс: {user['balance']} коинов.\n💵 Ставка: {user['bet']} коинов.",
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

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("перевод"))
async def transfer_money(message: Message):
    if is_spamming(message.from_user.id):
        return
    if not message.reply_to_message:
        await message.answer(f"⚠️ {get_ping(message)}, команда работает как ответ на сообщение друга!", parse_mode="Markdown")
        return
    from_user_id = message.from_user.id
    to_user_id = message.reply_to_message.from_user.id
    if from_user_id == to_user_id:
        await message.answer(f"❌ {get_ping(message)}, нельзя переводить коины самому себе!", parse_mode="Markdown")
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(f"✍️ {get_ping(message)}, пример команды: `Перевод 500`", parse_mode="Markdown")
        return
    amount = int(parts[1])
    if amount <= 0:
        await message.answer(f"⚠️ {get_ping(message)}, сумма должна быть больше 0!", parse_mode="Markdown")
        return
    sender = get_user_data(from_user_id, message.from_user.username)
    receiver = get_user_data(to_user_id, message.reply_to_message.from_user.username)
    if sender["balance"] < amount:
        await message.answer(f"❌ {get_ping(message)}, недостаточно коинов для перевода!", parse_mode="Markdown")
        return
    sender["balance"] -= amount
    receiver["balance"] += amount
    await message.answer(f"💸 {get_ping(message)} перевел *{amount}* коинов юзеру {get_ping(message.reply_to_message)}!", parse_mode="Markdown")

@dp.message(F.text == "🎁 Промокод")
async def enter_promo_request(message: Message, state: FSMContext):
    if is_spamming(message.from_user.id):




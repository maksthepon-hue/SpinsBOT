import asyncio
import random
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = '8787908421:AAFEVIkl157AYeUGxGqSsEaCl8WSKJeMEao'  # Сюда ваш токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

users_db = {}
used_promos_db = {}
bonus_timers = {}

PROMO_CODES = {
    "START2026": 500,
    "BONUS777": 1000,
    "FREECOINS": 300,
    "MILLION": 1000000  # Промик на миллион
}

class PromoStates(StatesGroup):
    waiting_for_promo = State()

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

# Новая переписанная клавиатура
def get_keyboard():
    kb = [
        [KeyboardButton(text="🎰 Рулетка"), KeyboardButton(text="⚽ Футбол"), KeyboardButton(text="🎯 Дартс")],
        [KeyboardButton(text="⏱ Часовой бонус"), KeyboardButton(text="📅 Дневной бонус")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🎁 Промокод")],
        [KeyboardButton(text="➕ Повысить ставку"), KeyboardButton(text="➖ Снизить ставку")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    
    if message.chat.type != "private":
        await message.answer("👋 Привет всем в чате! Я бот-казино.")
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Клавиатура обновлена. Проверь новые кнопки бонусов ниже!\n\n"
        f"💰 Твой баланс: {user['balance']} коинов.\n"
        f"💵 Ставка: {user['bet']} коинов.",
        reply_markup=get_keyboard()
    )

@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    user = get_user_data(message.from_user.id, message.from_user.username)
    await message.answer(f"💳 Ваш баланс: {user['balance']} коинов\n💵 Текущая ставка: {user['bet']} коинов")

@dp.message(F.text == "➕ Повысить ставку")
async def raise_bet(message: Message):
    user = get_user_data(message.from_user.id, message.from_user.username)
    user['bet'] += 50
    await message.answer(f"📈 Ставка увеличена! Новая ставка: {user['bet']} коинов")

@dp.message(F.text == "➖ Снизить ставку")
async def lower_bet(message: Message):
    user = get_user_data(message.from_user.id, message.from_user.username)
    if user['bet'] <= 50:
        await message.answer("⚠️ Минимальная ставка — 50 коинов!")
        return
    user['bet'] -= 50
    await message.answer(f"📉 Ставка снижена! Новая ставка: {user['bet']} коинов")

# Обработка кнопки часового бонуса
@dp.message(F.text == "⏱ Часовой бонус")
async def hourly_bonus(message: Message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    
    if current_time - bonus_timers[user_id]["hourly"] < 3600:
        left = int(3600 - (current_time - bonus_timers[user_id]["hourly"]))
        await message.answer(f"⏳ Рано! Подождите еще {left // 60} мин. {left % 60} сек.")
        return
        
    user["balance"] += 500
    bonus_timers[user_id]["hourly"] = current_time
    await message.answer(f"🎉 Вы получили +500 коинов!\n💰 Баланс: {user['balance']} коинов.")

# Обработка кнопки дневного бонуса
@dp.message(F.text == "📅 Дневной бонус")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    
    if current_time - bonus_timers[user_id]["daily"] < 86400:
        left = int(86400 - (current_time - bonus_timers[user_id]["daily"]))
        await message.answer(f"⏳ Рано! Подождите еще {left // 3600} ч. {(left % 3600) // 60} мин.")
        return
        
    user["balance"] += 5000
    bonus_timers[user_id]["daily"] = current_time
    await message.answer(f"🎉 Вы получили +5000 коинов!\n💰 Баланс: {user['balance']} коинов.")

@dp.message(lambda msg: msg.text and msg.text.lower().startswith("перевод"))
async def transfer_money(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Команда работает как ответ на сообщение друга!")
        return
        
    from_user_id = message.from_user.id
    to_user_id = message.reply_to_message.from_user.id
    
    if from_user_id == to_user_id:
        await message.answer("❌ Нельзя переводить себе!")
        return
        
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("✍️ Пример: `Перевод 500`")
        return
        
    amount = int(parts[1])
    if amount <= 0:
        await message.answer("⚠️ Сумма должна быть больше 0!")
        return
        
    sender = get_user_data(from_user_id, message.from_user.username)
    receiver = get_user_data(to_user_id, message.reply_to_message.from_user.username)
    
    if sender["balance"] < amount:
        await message.answer("❌ Недостаточно коинов!")
        return
        
    sender["balance"] -= amount
    receiver["balance"] += amount
    await message.answer(f"💸 Переведено {amount} коинов юзеру {message.reply_to_message.from_user.first_name}!")

@dp.message(F.text == "🎁 Промокод")
async def enter_promo_request(message: Message, state: FSMContext):
    await message.answer("✍️ Введите ваш промокод:")
    await state.set_state(PromoStates.waiting_for_promo)

@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    promo_text = message.text.strip().upper()

    if promo_text not in PROMO_CODES:
        await message.answer("❌ Такого промокода нет!")
        return

    if promo_text in used_promos_db[user_id]:
        await message.answer("⚠️ Вы уже активировали его!")
        await state.clear()
        return

    bonus = PROMO_CODES[promo_text]
    user['balance'] += bonus
    used_promos_db[user_id].append(promo_text)
    await message.answer(f"🎉 Активировано! +{bonus} коинов. Баланс: {user['balance']}")
    await state.clear()

async def play_game(message: Message, emoji: str, win_values: list):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    bet = user['bet']

    if user['balance'] < bet:
        await message.answer("❌ Недостаточно коинов!")
        return

    msg = await message.answer_dice(emoji=emoji)
    value = msg.dice.value
    await asyncio.sleep(4)

    if value in win_values:
        multiplier = round(random.uniform(1.5, 5.0), 1)
        win_amount = int(bet * multiplier)
        user['balance'] += win_amount
        await message.answer(f"🎉 Победа! Множитель: x{multiplier}\n➕ Получено: {win_amount}\n💰 Баланс: {user['balance']}")
    else:
        user['balance'] -= bet
        if user['balance'] < 0: user['balance'] = 0
        await message.answer(f"😢 Проигрыш! Выпало: {value}\n➖ Потеряно: {bet}\n💰 Баланс: {user['balance']}")

@dp.message(F.text == "🎰 Рулетка")
async def play_slots(message: Message): await play_game(message, emoji="🎰", win_values=[1, 22, 43, 64])

@dp.message(F.text == "⚽ Футбол")
async def play_football(message: Message): await play_game(message, emoji="⚽", win_values=[3, 4, 5])

@dp.message(F.text == "🎯 Дартс")
async def play_darts(message: Message): await play_game(message, emoji="🎯", win_values=[6])

async def main():
    print("Бот успешно запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())



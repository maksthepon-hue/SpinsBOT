import asyncio
import random
import time
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = 'ВАШ_ТОКЕН_БОТА'  # Замените на ваш токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Общая база данных (в оперативной памяти)
users_db = {}
used_promos_db = {}

# Таймеры для бонусов: {user_id: {"hourly": timestamp, "daily": timestamp}}
bonus_timers = {}

# Список промокодов и их награда (Добавлен промик на миллион!)
PROMO_CODES = {
    "START2026": 500,
    "BONUS777": 1000,
    "FREECOINS": 300,
    "MILLION": 1000000  # Ваш новый промокод на 1 000 000 коинов!
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

def get_keyboard():
    kb = [
        [KeyboardButton(text="🎰 Рулетка"), KeyboardButton(text="⚽ Футбол"), KeyboardButton(text="🎯 Дартс")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🎁 Промокод")],
        [KeyboardButton(text="⏱ Часовой бонус"), KeyboardButton(text="📅 Дневной бонус")],
        [KeyboardButton(text="➕ Повысить ставку"), KeyboardButton(text="➖ Снизить ставку")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    
    if message.chat.type != "private":
        await message.answer("👋 Привет всем в чате! Я бот-казино. Чтобы играть, используйте кнопки ниже или пишите команды.")
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в виртуальное казино.\n\n"
        f"💰 Твой стартовый баланс: {user['balance']} коинов.\n"
        f"💵 Текущая ставка: {user['bet']} коинов.\n\n"
        f"📌 Чтобы перевести коины другу в чате, ответьте на его сообщение командой:\n`Перевод [сумма]`",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
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

# Бонус каждый час (500 коинов)
@dp.message(F.text == "⏱ Часовой бонус")
async def hourly_bonus(message: Message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    
    if current_time - bonus_timers[user_id]["hourly"] < 3600:
        left = int(3600 - (current_time - bonus_timers[user_id]["hourly"]))
        await message.answer(f"⏳ Вы уже забирали часовой бонус! Подождите еще {left // 60} мин. {left % 60} сек.")
        return
        
    user["balance"] += 500
    bonus_timers[user_id]["hourly"] = current_time
    await message.answer(f"🎉 Вы получили часовой бонус: +500 коинов!\n💰 Баланс: {user['balance']} коинов.")

# Бонус каждые 24 часа (5000 коинов)
@dp.message(F.text == "📅 Дневной бонус")
async def daily_bonus(message: Message):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    current_time = time.time()
    
    if current_time - bonus_timers[user_id]["daily"] < 86400:
        left = int(86400 - (current_time - bonus_timers[user_id]["daily"]))
        await message.answer(f"⏳ Вы уже забирали дневной бонус! Подождите еще {left // 3600} ч. {(left % 3600) // 60} мин.")
        return
        
    user["balance"] += 5000
    bonus_timers[user_id]["daily"] = current_time
    await message.answer(f"🎉 Вы получили ежедневный бонус: +5000 коинов!\n💰 Баланс: {user['balance']} коинов.")

# Функция перевода денег в чатах через ответ на сообщение (Реплика)
@dp.message(lambda msg: msg.text and msg.text.lower().startswith("перевод"))
async def transfer_money(message: Message):
    if not message.reply_to_message:
        await message.answer("⚠️ Эта команда работает только как ответ на сообщение человека, которому вы хотите перевести коины!")
        return
        
    from_user_id = message.from_user.id
    to_user_id = message.reply_to_message.from_user.id
    
    if from_user_id == to_user_id:
        await message.answer("❌ Вы не можете перевести коины самому себе!")
        return
        
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("✍️ Укажите сумму правильно. Пример: `Перевод 500`")
        return
        
    amount = int(parts[1])
    if amount <= 0:
        await message.answer("⚠️ Сумма перевода должна быть больше нуля!")
        return
        
    sender = get_user_data(from_user_id, message.from_user.username)
    receiver = get_user_data(to_user_id, message.reply_to_message.from_user.username)
    
    if sender["balance"] < amount:
        await message.answer("❌ У вас недостаточно коинов для перевода!")
        return
        
    sender["balance"] -= amount
    receiver["balance"] += amount
    
    await message.answer(
        f"💸 Юзер *{message.from_user.first_name}* перевёл *{amount}* коинов "
        f"юзеру *{message.reply_to_message.from_user.first_name}*!\n"
        f"💰 Ваш остаток: {sender['balance']} коинов.",
        parse_mode="Markdown"
    )

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
        await message.answer("❌ Такого промокода не существует! Попробуйте еще раз или нажмите другую кнопку.")
        return

    if promo_text in used_promos_db[user_id]:
        await message.answer("⚠️ Вы уже активировали этот промокод ранее!")
        await state.clear()
        return

    bonus = PROMO_CODES[promo_text]
    user['balance'] += bonus
    used_promos_db[user_id].append(promo_text)
    
    await message.answer(f"🎉 Промокод успешно активирован!\n➕ Вам начислено: {bonus} коинов.\n💰 Новый баланс: {user['balance']} коинов.")
    await state.clear()

# Обновленная игра: Рандомный множитель выигрыша!
async def play_game(message: Message, emoji: str, win_values: list):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.username)
    bet = user['bet']

    if user['balance'] < bet:
        await message.answer("❌ У вас недостаточно коинов для этой ставки! Снизьте ставку или подождите бонуса.")
        return

    msg = await message.answer_dice(emoji=emoji)
    value = msg.dice.value
    await asyncio.sleep(4)

    if value in win_values:
        # Генерируем случайный коэффициент выигрыша от х1.5 до х5.0
        multiplier = round(random.uniform(1.5, 5.0), 1)
        win_amount = int(bet * multiplier)
        
        user['balance'] += win_amount
        await message.answer(
            f"🎉 Вы выиграли! Выпало значение: {value}\n"
            f"🔥 Рандомный множитель: **x{multiplier}**\n"
            f"➕ Получено: {win_amount} коинов.\n"
            f"💰 Баланс: {user['balance']} коинов.",
            parse_mode="Markdown"
        )
    else:
        user['balance'] -= bet
        if user['balance'] < 0:
            user['balance'] = 0
        await message.answer(f"😢 Вы проиграли! Выпало значение: {value}\n➖ Потеряно: {bet} коинов.\n💰 Баланс: {user['balance']} коинов.")

@dp.message(F.text == "🎰 Рулетка")
async def play_slots(message: Message):
    await play_game(message, emoji="🎰", win_values=[1, 22, 43, 64])

@dp.message(F.text == "⚽ Футбол")
async def play_football(message: Message):
    await play_game(message, emoji="⚽", win_values=[3, 4, 5])

@dp.message(F.text == "🎯 Дартс")
async def play_darts(message: Message):
    await play_game(message, emoji="🎯", win_values=[6])

async def main():
    print("Бот успешно запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())


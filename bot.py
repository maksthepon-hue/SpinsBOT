import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = '8787908421:AAElCNsdWLUYfkQ_tcOp5YP1OJNVnZLbVlU'

bot = Bot(token=TOKEN)
dp = Dispatcher()

users_db = {}
# База для отслеживания активированных промокодов: {user_id: ["ПРОМО1", "ПРОМО2"]}
used_promos_db = {}

# Список доступных промокодов и их награда
PROMO_CODES = {
    "START2026": 500,
    "BONUS777": 1000,
    "FREECOINS": 300
}

# Состояние для ожидания ввода промокода
class PromoStates(StatesGroup):
    waiting_for_promo = State()

def get_user_data(user_id: int):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 1000, "bet": 100}
    if user_id not in used_promos_db:
        used_promos_db[user_id] = []
    return users_db[user_id]

def get_keyboard():
    kb = [
        [KeyboardButton(text="🎰 Рулетка"), KeyboardButton(text="⚽ Футбол"), KeyboardButton(text="🎯 Дартс")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🎁 Промокод")],
        [KeyboardButton(text="➕ Повысить ставку"), KeyboardButton(text="➖ Снизить ставку")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear() # Сбрасываем состояния при старте
    user_id = message.from_user.id
    user = get_user_data(user_id)
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Добро пожаловать в виртуальное казино.\n\n"
        f"💰 Твой стартовый баланс: {user['balance']} коинов.\n"
        f"💵 Текущая ставка: {user['bet']} коинов.",
        reply_markup=get_keyboard()
    )

@dp.message(F.text == "💰 Баланс")
async def show_balance(message: Message):
    user = get_user_data(message.from_user.id)
    await message.answer(f"💳 Ваш баланс: {user['balance']} коинов\n💵 Текущая ставка: {user['bet']} коинов")

@dp.message(F.text == "➕ Повысить ставку")
async def raise_bet(message: Message):
    user = get_user_data(message.from_user.id)
    user['bet'] += 50
    await message.answer(f"📈 Ставка увеличена! Новая ставка: {user['bet']} коинов")

@dp.message(F.text == "➖ Снизить ставку")
async def lower_bet(message: Message):
    user = get_user_data(message.from_user.id)
    if user['bet'] <= 50:
        await message.answer("⚠️ Минимальная ставка — 50 коинов!")
        return
    user['bet'] -= 50
    await message.answer(f"📉 Ставка снижена! Новая ставка: {user['bet']} коинов")

# Нажатие на кнопку «Промокод»
@dp.message(F.text == "🎁 Промокод")
async def enter_promo_request(message: Message, state: FSMContext):
    await message.answer("✍️ Введите ваш промокод:")
    await state.set_state(PromoStates.waiting_for_promo)

# Обработка введенного промокода
@dp.message(PromoStates.waiting_for_promo)
async def process_promo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    promo_text = message.text.strip().upper() # Приводим к верхнему регистру

    if promo_text not in PROMO_CODES:
        await message.answer("❌ Такого промокода не существует! Попробуйте еще раз или нажмите другую кнопку.")
        return

    if promo_text in used_promos_db[user_id]:
        await message.answer("⚠️ Вы уже активировали этот промокод ранее!")
        await state.clear()
        return

    # Начисляем награду
    bonus = PROMO_CODES[promo_text]
    user['balance'] += bonus
    used_promos_db[user_id].append(promo_text)
    
    await message.answer(f"🎉 Промокод успешно активирован!\n➕ Вам начислено: {bonus} коинов.\n💰 Новый баланс: {user['balance']} коинов.")
    await state.clear() # Выходим из состояния ожидания

async def play_game(message: Message, emoji: str, win_values: list):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    bet = user['bet']

    if user['balance'] < bet:
        await message.answer("❌ У вас недостаточно коинов для этой ставки! Снизьте ставку или подождите.")
        return

    msg = await message.answer_dice(emoji=emoji)
    value = msg.dice.value
    await asyncio.sleep(4)

    if value in win_values:
        user['balance'] += bet
        await message.answer(f"🎉 Вы выиграли! Выпало значение: {value}\n➕ Получено: {bet} коинов.\n💰 Баланс: {user['balance']} коинов.")
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
    await play_game(message, emoji="🎯", win_values=[4, 5, 6])

async def main():
    print("Бот успешно запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

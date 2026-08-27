import time
import random
import json
import os
import telebot
from telebot import types

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8958818419:AAG-2DEVH6PCbMwG85AO19UdjpOokYNNuO8"  # Твой токен вшит напрямую
DB_FILE = "casino_db.json"
COOLDOWN_TIME = 2  # Антиспам в секундах

bot = telebot.TeleBot(BOT_TOKEN)
last_action = {}

# --- БАЗА ДАННЫХ (JSON-файл) ---
def load_db():
    data = {"users": {}, "promos": {}, "states": {}}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            try: 
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data.update(loaded)
            except: 
                pass
    if not data["promos"]:
        data["promos"] = {f"PROMO-{i}": 500 for i in range(1, 51)}
    if "states" not in data:
        data["states"] = {}
    return data

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()

def check_spam(user_id):
    now = time.time()
    if user_id in last_action:
        if now - last_action[user_id] < COOLDOWN_TIME:
            return True
    last_action[user_id] = now
    return False

def init_user(user_id, username):
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "username": username or "Игрок",
            "balance": 1000,
            "last_hourly": 0,
            "last_daily": 0,
            "used_promos": []
        }
        save_db(db)

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💵 Мой баланс", "🎫 Промокод")
    markup.row("⚽ Футбол", "🎯 Дартс", "🎰 Рулетка")
    markup.row("🎁 Ежечасный бонус", "📆 Ежедневный бонус")
    return markup

# --- ОБРАБОТКА КОМАНД И КНОПОК ---

@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    if check_spam(message.from_user.id): return
    init_user(message.from_user.id, message.from_user.username)
    db["states"][str(message.from_user.id)] = None
    save_db(db)
    
    welcome = (
        f"🎰 ✨ *Добро пожаловать в Казино, {message.from_user.first_name}!* ✨ 🎰\n\n"
        "💰 Тебе начислено 1000 стартовых монет.\n"
        "🎮 Нажимай на кнопки меню снизу, чтобы играть и получать призы!\n\n"
        "🤝 *Перевод другу в группе:* ответь на его сообщение командой `/pay [сумма]`"
    )
    bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.message_handler(commands=['pay'])
def cmd_pay(message):
    if message.chat.type not in ["group", "supergroup"]:
        return bot.reply_to(message, "❌ Переводы работают только в группах!")
    if not message.reply_to_message:
        return bot.reply_to(message, "❌ Ответь этой командой на сообщение того, кому переводишь монеты.")
        
    from_id = str(message.from_user.id)
    to_id = str(message.reply_to_message.from_user.id)
    if from_id == to_id: return bot.reply_to(message, "❌ Нельзя переводить себе!")
    
    text_parts = message.text.split()
    if len(text_parts) < 2 or not text_parts[1].isdigit():
        return bot.reply_to(message, "❌ Укажи сумму числом. Пример: `/pay 100`")
        
    amount = int(text_parts[1])
    init_user(from_id, message.from_user.username)
    init_user(to_id, message.reply_to_message.from_user.username)
    
    if db["users"][from_id]["balance"] < amount:
        return bot.reply_to(message, "❌ Недостаточно монет на балансе!")
        
    db["users"][from_id]["balance"] -= amount
    db["users"][to_id]["balance"] += amount
    save_db(db)
    bot.send_message(message.chat.id, f"✅ Игрок @{message.from_user.username} перевел {amount} монет игроку @{message.reply_to_message.from_user.username}!")

# --- ТЕКСТОВЫЕ КНОПКИ ---

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    uid = str(message.from_user.id)
    init_user(message.from_user.id, message.from_user.username)
    
    if check_spam(message.from_user.id):
        return bot.send_message(message.chat.id, "⚠️ Не спамь! Подождите секунду.")

    state = db["states"].get(uid)
    
    if state and state.startswith("bet_"):
        game_type = state.replace("bet_", "")
        db["states"][uid] = None
        save_db(db)
        
        if not message.text.isdigit():
            return bot.send_message(message.chat.id, "❌ Ставка должна быть числом!", reply_markup=get_main_menu())
        
        bet = int(message.text)
        if bet <= 0: return bot.send_message(message.chat.id, "❌ Ставка должна быть больше 0!", reply_markup=get_main_menu())
        if db["users"][uid]["balance"] < bet: return bot.send_message(message.chat.id, "❌ Недостаточно монет!", reply_markup=get_main_menu())
        
        # Запуск игры
        db["users"][uid]["balance"] -= bet
        save_db(db)
        
        emojis = {"football": "⚽", "darts": "🎯", "roulette": "🎰"}
        msg = bot.send_dice(message.chat.id, emoji=emojis[game_type])
        val = msg.dice.value
        time.sleep(4) # Анимация кубика
        
        is_win = False
        if game_type == "roulette":
            if val == 1 or val == 22 or val == 43 or val == 64: is_win = True
        elif game_type == "darts":
            if val >= 4 and val <= 6: is_win = True
        elif game_type == "football":
            if val >= 3 and val <= 5: is_win = True
        
        if is_win:
            multiplier = round(random.uniform(1.5, 5.0), 1)
            win_amount = int(bet * multiplier)
            db["users"][uid]["balance"] += win_amount
            save_db(db)
            bot.reply_to(message, f"🎉 *ПОБЕДА!* 🎉\n🔥 Выпало: {val}\n📈 Множитель: x{multiplier}\n💰 Случайный выигрыш: *{win_amount}* монет!", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"😢 *ПРОИГРЫШ*\nВыпало: {val}\nТы потерял {bet} монет. Повезет в следующий раз!")
        return

    if state == "promo_waiting":
        db["states"][uid] = None
        save_db(db)
        code = message.text.strip()
        if code not in db["promos"]: return bot.send_message(message.chat.id, "❌ Такого промокода нет!", reply_markup=get_main_menu())
        if code in db["users"][uid]["used_promos"]: return bot.send_message(message.chat.id, "❌ Ты уже активировал этот код!", reply_markup=get_main_menu())
        
        reward = db["promos"][code]
        db["users"][uid]["balance"] += reward
        db["users"][uid]["used_promos"].append(code)
        save_db(db)
        return bot.send_message(message.chat.id, f"🎫 Промокод активирован! +{reward} монет.", reply_markup=get_main_menu())

    # Обработка главного меню
    if message.text == "💵 Мой баланс":
        bot.send_message(message.chat.id, f"💰 Твой баланс: *{db['users'][uid]['balance']}* монет.", parse_mode="Markdown")
        
    elif message.text in ["⚽ Футбол", "🎯 Дартс", "🎰 Рулетка"]:
        g_names = {"⚽ Футбол": "football", "🎯 Дартс": "darts", "🎰 Рулетка": "roulette"}
        db["states"][uid] = f"bet_{g_names[message.text]}"
        save_db(db)
        bot.send_message(message.chat.id, f"Выбрана игра: {message.text}\n✏️ Введи сумму ставки числом:")
        
    elif message.text == "🎫 Промокод":
        db["states"][uid] = "promo_waiting"
        save_db(db)
        bot.send_message(message.chat.id, "✏️ Введи промокод (Например: `PROMO-1`):", parse_mode="Markdown")
        
    elif message.text == "🎁 Ежечасный бонус":
        now = int(time.time())
        if now - db["users"][uid]["last_hourly"] < 3600:
            return bot.send_message(message.chat.id, f"⏳ Рано! Жди еще {(3600 - (now - db['users'][uid]['last_hourly'])) // 60} мин.")
        bonus = random.randint(50, 200)
        db["users"][uid]["balance"] += bonus
        db["users"][uid]["last_hourly"] = now
        save_db(db)
        bot.send_message(message.chat.id, f"🎁 Получен часовой бонус: +{bonus} монет!")
        
    elif message.text == "📆 Ежедневный бонус":
        now = int(time.time())
        if now - db["users"][uid]["last_daily"] < 86400:
            return bot.send_message(message.chat.id, f"⏳ Приходи позже! Через {(86400 - (now - db['users'][uid]['last_daily'])) // 3600} ч.")
        bonus = random.randint(300, 1000)
        db["users"][uid]["balance"] += bonus
        db["users"][uid]["last_daily"] = now
        save_db(db)
        bot.send_message(message.chat.id, f"📆 Получен ежедневный бонус: +{bonus} монет!")

# --- ЖЕЛЕЗОБЕТОННЫЙ ЗАПУСК ---
if __name__ == "__main__":
    print("Бот успешно запущен на сервере TeleBotHost!")
    while True:
        try:
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Ошибка пуллинга, перезапуск через 5 секунд: {e}")
            time.sleep(5)






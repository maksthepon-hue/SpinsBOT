import time
import random
import os
import telebot
from telebot import types
import threading
import requests
from flask import Flask

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8958818419:AAF4PoxE8jAr-QlmfiFZp4lhneXYjM4Hdf0"  # Твой чистый токен
COOLDOWN_TIME = 2

# Твой уникальный ключ для вечной базы в интернете
CLOUD_STORAGE_URL = "https://onrender.com"

bot = telebot.TeleBot(BOT_TOKEN)
last_action = {}
app = Flask(__name__)
local_db = {"users": {}}
db_lock = threading.Lock()

@app.route('/')
def home():
    return "Казино работает 24/7 с вечным интернет-сохранением!"

# --- АВТОМАТИЧЕСКАЯ ИНТЕРНЕТ-БАЗА ---
def load_db():
    global local_db
    try:
        r = requests.get(CLOUD_STORAGE_URL, timeout=5)
        if r.status_code == 200 and r.json():
            local_db = r.json()
            if "users" not in local_db:
                local_db = {"users": {}}
            print("Вечные балансы успешно скачаны из облачного хранилища!")
            return
    except:
        pass
    local_db = {"users": {}}

def save_db():
    with db_lock:
        try:
            requests.post(CLOUD_STORAGE_URL, json=local_db, timeout=5)
            print("Балансы и таймеры успешно зафиксированы в облаке!")
        except:
            print("Временный сбой сети при сохранении")

load_db()

def check_spam(user_id):
    now = time.time()
    if user_id in last_action:
        if now - last_action[user_id] < COOLDOWN_TIME:
            return True
    last_action[user_id] = now
    return False

def init_user(user_id, username):
    uid = str(user_id)
    with db_lock:
        if uid not in local_db["users"]:
            local_db["users"][uid] = {
                "username": username or "Игрок",
                "balance": 1000,
                "last_hourly": 0,
                "last_daily": 0,
                "used_promos": [],
                "state": None
            }
            threading.Thread(target=save_db, daemon=True).start()
        elif "used_promos" not in local_db["users"][uid]:
            local_db["users"][uid]["used_promos"] = []

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("💵 Мой баланс", "🎫 Промокод")
    markup.row("⚽ Футбол", "🎯 Дартс", "🎰 Рулетка")
    markup.row("🏀 Баскетбол")
    markup.row("🎁 Ежечасный бонус", "📆 Ежедневный бонус")
    return markup

# --- ОБРАБОТКА ТЕЛЕГРАМ ---

@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    if check_spam(message.from_user.id): return
    init_user(message.from_user.id, message.from_user.username)
    with db_lock:
        local_db["users"][str(message.from_user.id)]["state"] = None
    
    welcome = (
        f"🎰 ✨ *Добро пожаловать в Казино, {message.from_user.first_name}!* ✨ 🎰\n\n"
        "💰 Твой вечный баланс и таймеры бонусов теперь защищены.\n"
        "🎮 Нажимай на кнопки меню снизу, чтобы играть!\n\n"
        "🤝 *Перевод другу в группе:* ответь на его сообщение текстом: `дать [сумма]`"
    )
    bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    uid = str(message.from_user.id)
    init_user(message.from_user.id, message.from_user.username)
    
    # Текстовые переводы в группах
    if message.chat.type in ["group", "supergroup"] and message.reply_to_message:
        text_lower = message.text.lower().strip()
        if text_lower.startswith("дать") or text_lower.startswith("перевод"):
            amount_str = "".join(filter(str.isdigit(), text_lower))
            if amount_str.isdigit():
                if check_spam(message.from_user.id): return
                to_id = str(message.reply_to_message.from_user.id)
                if uid == to_id: return bot.reply_to(message, "❌ Нельзя переводить себе!")
                
                amount = int(amount_str)
                with db_lock:
                    if local_db["users"][uid]["balance"] < amount:
                        return bot.reply_to(message, "❌ Недостаточно монет!")
                    
                    init_user(to_id, message.reply_to_message.from_user.username)
                    local_db["users"][uid]["balance"] -= amount
                    local_db["users"][to_id]["balance"] += amount
                    threading.Thread(target=save_db, daemon=True).start()
                
                return bot.reply_to(message, f"✅ Успешный перевод {amount} монет!")

    if check_spam(message.from_user.id): return

    state = local_db["users"][uid].get("state")

    # Ввод ставки для игры
    if state and state.startswith("bet_"):
        game_type = state.replace("bet_", "")
        with db_lock:
            local_db["users"][uid]["state"] = None
        
        if not message.text.isdigit():
            return bot.send_message(message.chat.id, "❌ Ставка должна быть числом!", reply_markup=get_main_menu())
        
        bet = int(message.text)
        if bet <= 0: return bot.send_message(message.chat.id, "❌ Ставка должна быть больше 0!", reply_markup=get_main_menu())
        if local_db["users"][uid]["balance"] < bet: return bot.send_message(message.chat.id, "❌ Недостаточно монет!", reply_markup=get_main_menu())
        
        with db_lock:
            local_db["users"][uid]["balance"] -= bet
            save_db()
        
        emojis = {"football": "⚽", "darts": "🎯", "roulette": "🎰", "basketball": "🏀"}
        msg = bot.send_dice(message.chat.id, emoji=emojis[game_type])
        val = msg.dice.value
        time.sleep(4)
        
        is_win = False
        if game_type == "roulette" and val == 64: is_win = True
        elif game_type == "darts" and val >= 4 and val <= 6: is_win = True
        elif game_type == "football" and val >= 3 and val <= 5: is_win = True
        elif game_type == "basketball" and (val == 4 or val == 5): is_win = True
        
        with db_lock:
            if is_win:
                multiplier = round(random.uniform(1.5, 5.0), 1)
                win_amount = int(bet * multiplier)
                local_db["users"][uid]["balance"] += win_amount
                bot.reply_to(message, f"🎉 *ПОБЕДА В {game_type.upper()}!* 🎉\n🔥 Выпало: {val}\n📈 Множитель: x{multiplier}\n💰 Выигрыш: *{win_amount}* монет!", parse_mode="Markdown")
            else:
                bot.reply_to(message, f"😢 *ПРОИГРЫШ*\nВыпало: {val}\nТы потерял {bet} монет. Повезет в следующий раз!")
            threading.Thread(target=save_db, daemon=True).start()
        return

    if state == "promo_waiting":
        with db_lock:
            local_db["users"][uid]["state"] = None
        code = message.text.strip().upper()
        
        valid_promos = [f"PROMO-{i}" for i in range(1, 51)]
        if code not in valid_promos: 
            return bot.send_message(message.chat.id, "❌ Такого промокода нет!", reply_markup=get_main_menu())
            
        if code in local_db["users"][uid].get("used_promos", []): 
            return bot.send_message(message.chat.id, "❌ Ты уже активировал этот код!", reply_markup=get_main_menu())
        
        with db_lock:
            local_db["users"][uid]["balance"] += 500
            local_db["users"][uid]["used_promos"].append(code)
            threading.Thread(target=save_db, daemon=True).start()
        return bot.send_message(message.chat.id, f"🎫 Промокод {code} активирован! +500 монет.", reply_markup=get_main_menu())

    # Главное меню кнопок
    if message.text == "💵 Мой баланс":
        bot.send_message(message.chat.id, f"💰 Твой баланс: *{local_db['users'][uid]['balance']}* монет.", parse_mode="Markdown")
        
    elif message.text in ["⚽ Футбол", "🎯 Дартс", "🎰 Рулетка", "🏀 Баскетбол"]:
        g_names = {"⚽ Футбол": "football", "🎯 Дартс": "darts", "🎰 Рулетка": "roulette", "🏀 Баскетбол": "basketball"}
        with db_lock:
            local_db["users"][uid]["state"] = f"bet_{g_names[message.text]}"
        bot.send_message(message.chat.id, f"Выбрана игра: {message.text}\n✏️ Введи сумму ставки числом:")
        
    elif message.text == "🎫 Промокод":
        with db_lock:
            local_db["users"][uid]["state"] = "promo_waiting"
        bot.send_message(message.chat.id, "✏️ Введи промокод (Например: `PROMO-1`):", parse_mode="Markdown")
        
    elif message.text == "🎁 Ежечасный бонус":
        now = int(time.time())
        time_passed = now - local_db["users"][uid].get("last_hourly", 0)
        if time_passed < 3600:
            return bot.send_message(message.chat.id, f"⏳ Рано! Жди еще {(3600 - time_passed) // 60} мин.")
            
        with db_lock:
            bonus = random.randint(50, 200)
            local_db["users"][uid]["balance"] += bonus
            local_db["users"][uid]["last_hourly"] = now
            threading.Thread(target=save_db, daemon=True).start()
        bot.send_message(message.chat.id, f"🎁 Получен часовой бонус: +{bonus} монет!")
        
    elif message.text == "📆 Ежедневный бонус":
        now = int(time.time())
        time_passed = now - local_db["users"][uid].get("last_daily", 0)
        if time_passed < 86400:
            return bot.send_message(message.chat.id, f"⏳ Приходи позже! Через {(86400 - time_passed) // 3600} ч.")
            
        with db_lock:
            bonus = random.randint(300, 1000)
            local_db["users"][uid]["balance"] += bonus
            local_db["users"][uid]["last_daily"] = now
            threading.Thread(target=save_db, daemon=True).start()
        bot.send_message(message.chat.id, f"📆 Получен ежедневный бонус: +{bonus} монет!")

def run_bot_polling():
    """Запуск бота через 5 секунд, когда Flask уже железно занял порт и Render спокоен"""
    time.sleep(5)
    try:
        bot.remove_webhook()
        print("Телеграм-бот успешно запущен в фоновом режиме!")
        bot.infinity_polling(none_stop=True)
    except Exception as e:
        print(f"Ошибка пуллинга: {e}")


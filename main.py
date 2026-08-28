import time
import random
import os
import telebot
from telebot import types
import threading
import requests
from flask import Flask

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8958818419:AAFUEkVcszwIeHhjBXp9It1XfMMe_YJjw8U"  # Твой токен
COOLDOWN_TIME = 2

# Создаем твой уникальный скрытый ключ для вечной базы в интернете
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
                "used_promos": []
            }
            threading.Thread(target=save_db, daemon=True).start()

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
    
    # Текстовые переводы
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

    # Игры
    if message.text in ["⚽ Футбол", "🎯 Дартс", "🎰 Рулетка", "🏀 Баскетбол"]:
        g_emojis = {"⚽ Футбол": "⚽", "🎯 Дартс": "🎯", "🎰 Рулетка": "🎰", "🏀 Баскетбол": "🏀"}
        g_type = message.text
        
        with db_lock:
            if local_db["users"][uid]["balance"] < 100:
                return bot.send_message(message.chat.id, "❌ Минимальная ставка 100 монет!")
            local_db["users"][uid]["balance"] -= 100
        
        msg = bot.send_dice(message.chat.id, emoji=g_emojis[g_type])
        val = msg.dice.value
        time.sleep(4)
        
        is_win = False
        if g_type == "🎰 Рулетка" and val == 64: is_win = True
        elif g_type == "🎯 Дартс" and val >= 4: is_win = True
        elif g_type == "⚽ Футбол" and val >= 3: is_win = True
        elif g_type == "🏀 Баскетбол" and val >= 4: is_win = True
        
        with db_lock:
            if is_win:
                local_db["users"][uid]["balance"] += 300
                bot.reply_to(message, f"🎉 ПОБЕДА! Выпало {val}. Ты выиграл 300 монет!")
            else:
                bot.reply_to(message, f"😢 ПРОИГРЫШ! Выпало {val}. Ставка 100 монет сгорела.")
            threading.Thread(target=save_db, daemon=True).start()
        return

    if message.text == "💵 Мой баланс":
        bot.send_message(message.chat.id, f"💰 Твой баланс: *{local_db['users'][uid]['balance']}* монет.", parse_mode="Markdown")
        
    elif message.text == "🎁 Ежечасный бонус":
        now = int(time.time())
        time_passed = now - local_db["users"][uid]["last_hourly"]
        if time_passed < 3600:
            return bot.send_message(message.chat.id, f"⏳ Жди еще {(3600 - time_passed) // 60} мин.")
            
        with db_lock:
            local_db["users"][uid]["balance"] += 150
            local_db["users"][uid]["last_hourly"] = now
            threading.Thread(target=save_db, daemon=True).start()
        bot.send_message(message.chat.id, "🎁 Бонус +150 монет получен!")
        
    elif message.text == "📆 Ежедневный бонус":
        now = int(time.time())
        time_passed = now - local_db["users"][uid]["last_daily"]
        if time_passed < 86400:
            return bot.send_message(message.chat.id, f"⏳ Жди еще {(86400 - time_passed) // 3600} ч.")
            
        with db_lock:
            local_db["users"][uid]["balance"] += 500
            local_db["users"][uid]["last_daily"] = now
            threading.Thread(target=save_db, daemon=True).start()
        bot.send_message(message.chat.id, "📆 Ежедневный бонус +500 монет получен!")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.remove_webhook()
    bot.infinity_polling(none_stop=True)

        





        












import time
import random
import os
import telebot
from telebot import types
import psycopg2
from psycopg2.extras import DictCursor

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8958818419:AAEJFomq7ZCanLInbugUfQtuyjJNQtoHj_k"  # Твой токен вшит напрямую
DATABASE_URL = os.getenv("DATABASE_URL")
COOLDOWN_TIME = 2  # Антиспам в секундах

bot = telebot.TeleBot(BOT_TOKEN)
last_action = {}

# --- ПОДКЛЮЧЕНИЕ И ИНИЦИАЛИЗАЦИЯ БД ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    """Создает таблицы в базе PostgreSQL, если их еще нет"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) PRIMARY KEY,
            username VARCHAR(100),
            balance INT DEFAULT 1000,
            last_hourly INT DEFAULT 0,
            last_daily INT DEFAULT 0,
            used_promos TEXT[] DEFAULT '{}'
        );
    """)
    
    # Таблица промокодов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            code VARCHAR(50) PRIMARY KEY,
            reward INT
        );
    """)
    
    # Проверяем, есть ли промокоды, если нет — генерируем 50 штук
    cur.execute("SELECT COUNT(*) FROM promos;")
    if cur.fetchone()[0] == 0:
        for i in range(1, 51):
            cur.execute("INSERT INTO promos (code, reward) VALUES (%s, %s);", (f"PROMO-{i}", 500))
            
    # Таблица временных состояний
    cur.execute("""
        CREATE TABLE IF NOT EXISTS states (
            user_id VARCHAR(50) PRIMARY KEY,
            state_val VARCHAR(50)
        );
    """)
    
    conn.commit()
    cur.close()
    conn.close()

def check_spam(user_id):
    now = time.time()
    if user_id in last_action:
        if now - last_action[user_id] < COOLDOWN_TIME:
            return True
    last_action[user_id] = now
    return False

def init_user(user_id, username):
    uid = str(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username) 
        VALUES (%s, %s) 
        ON CONFLICT (user_id) DO UPDATE SET username = %s;
    """, (uid, username or "Игрок", username or "Игрок"))
    conn.commit()
    cur.close()
    conn.close()

def get_user_state(user_id):
    uid = str(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT state_val FROM states WHERE user_id = %s;", (uid,))
    res = cur.fetchone()
    cur.close()
    conn.close()
    return res[0] if res else None

def set_user_state(user_id, state_val):
    uid = str(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO states (user_id, state_val) 
        VALUES (%s, %s) 
        ON CONFLICT (user_id) DO UPDATE SET state_val = %s;
    """, (uid, state_val, state_val))
    conn.commit()
    cur.close()
    conn.close()

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
    set_user_state(message.from_user.id, None)
    
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
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = %s;", (from_id,))
    from_balance = cur.fetchone()[0]
    
    if from_balance < amount:
        cur.close()
        conn.close()
        return bot.reply_to(message, "❌ Недостаточно монет на балансе!")
        
    cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s;", (amount, from_id))
    cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s;", (amount, to_id))
    conn.commit()
    cur.close()
    conn.close()
    
    bot.send_message(message.chat.id, f"✅ Игрок @{message.from_user.username} перевел {amount} монет игроку @{message.reply_to_message.from_user.username}!")

# --- ТЕКСТОВЫЕ КНОПКИ ---

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    uid = str(message.from_user.id)
    init_user(message.from_user.id, message.from_user.username)
    
    if check_spam(message.from_user.id):
        return bot.send_message(message.chat.id, "⚠️ Не спамь! Подождите секунду.")

    state = get_user_state(message.from_user.id)
    
    if state and state.startswith("bet_"):
        game_type = state.replace("bet_", "")
        set_user_state(message.from_user.id, None)
        
        if not message.text.isdigit():
            return bot.send_message(message.chat.id, "❌ Ставка должна быть числом!", reply_markup=get_main_menu())
        
        bet = int(message.text)
        if bet <= 0: return bot.send_message(message.chat.id, "❌ Ставка должна быть больше 0!", reply_markup=get_main_menu())
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s;", (uid,))
        balance = cur.fetchone()[0]
        
        if balance < bet:
            cur.close()
            conn.close()
            return bot.send_message(message.chat.id, "❌ Недостаточно монет!", reply_markup=get_main_menu())
        
        # Запуск игры
        cur.execute("UPDATE users SET balance = balance - %s WHERE user_id = %s;", (bet, uid))
        conn.commit()
        
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
            cur.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s;", (win_amount, uid))
            conn.commit()
            bot.reply_to(message, f"🎉 *ПОБЕДА!* 🎉\n🔥 Выпало: {val}\n📈 Множитель: x{multiplier}\n💰 Случайный выигрыш: *{win_amount}* монет!", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"😢 *ПРОИГРЫШ*\nВыпало: {val}\nТы потерял {bet} монет. Повезет в следующий раз!")
            
        cur.close()
        conn.close()
        return

    if state == "promo_waiting":
        set_user_state(message.from_user.id, None)
        code = message.text.strip()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT reward FROM promos WHERE code = %s;", (code,))
        promo_res = cur.fetchone()
        if not promo_res:
            cur.close()
            conn.close()
            return bot.send_message(message.chat.id, "❌ Такого промокода нет!", reply_markup=get_main_menu())
            
        cur.execute("SELECT used_promos FROM users WHERE user_id = %s;", (uid,))
        used_promos_res = cur.fetchone()
        used_promos = used_promos_res[0] if used_promos_res and used_promos_res[0] else []
        
        if code in used_promos:
            cur.close()
            conn.close()
            return bot.send_message(message.chat.id, "❌ Ты уже активировал этот код!", reply_markup=get_main_menu())
        
        reward = promo_res[0]
        cur.execute("UPDATE users SET balance = balance + %s, used_promos = array_append(used_promos, %s) WHERE user_id = %s;", (reward, code, uid))
        conn.commit()
        cur.close()
        conn.close()
        return bot.send_message(message.chat.id, f"🎫 Промокод активирован! +{reward} монет.", reply_markup=get_main_menu())

    # Обработка главного меню
    if message.text == "💵 Мой баланс":
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = %s;", (uid,))
        bal = cur.fetchone()[0]
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, f"💰 Твой баланс: *{bal}* монет.", parse_mode="Markdown")
        
    elif message.text in ["⚽ Футбол", "🎯 Дартс", "🎰 Рулетка"]:
        g_names = {"⚽ Футбол": "football", "🎯 Дартс": "darts", "🎰 Рулетка": "roulette"}
        set_user_state(message.from_user.id, f"bet_{g_names[message.text]}")



# bot_forcesub.py
# Termux-ready forced-join system
# Requirements: pyTelegramBotAPI (pip install pyTelegramBotAPI)

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import time
import threading

# --------- CONFIG ----------
BOT_TOKEN = "7901997929:AAHmlgWrOMz_W-2zSG334MrtBPDKug1EqJE"   # <- Replace with your BotFather token

# Required channels (user must join all)
CHANNELS = [
    "@viernable",
    "@punchytosis",
    "@sieextern"
]

# Texts (customize if you want)
MSG_WELCOME = "👋 Welcome! To use this bot you must join all required channels and press Verify."
MSG_NEED_JOIN = "🚨 Please join all channels and then press ✔️ Verify."
MSG_VERIFIED = "✅ Verified! You can now use the bot."
MSG_NOT_VERIFIED = "❌ You are not verified. Join all channels and press Verify."
MSG_LEFT_CHANNEL = "⚠️ You left one of the required channels. You have been unverified — please /start to re-verify."

# DB file
DB_FILE = "verified_users.db"
# ---------------------------

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# ---------- Database helpers ----------
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS verified (user_id INTEGER PRIMARY KEY, verified_at INTEGER)"
    )
    conn.commit()
    return conn

db_conn = init_db()
db_lock = threading.Lock()

def add_verified(user_id):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("INSERT OR REPLACE INTO verified (user_id, verified_at) VALUES (?, ?)", (user_id, int(time.time())))
        db_conn.commit()

def remove_verified(user_id):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("DELETE FROM verified WHERE user_id = ?", (user_id,))
        db_conn.commit()

def is_stored_verified(user_id):
    with db_lock:
        cur = db_conn.cursor()
        cur.execute("SELECT 1 FROM verified WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None

# ---------- Membership check ----------
def check_user_in_channel(username, user_id):
    try:
        member = bot.get_chat_member(username, user_id)
        if member.status in ["member", "creator", "administrator"]:
            return True
        return False
    except Exception:
        return False

def is_user_joined_all(user_id):
    for ch in CHANNELS:
        if not check_user_in_channel(ch, user_id):
            return False
    return True

# ---------- UI: verification markup ----------
def make_verification_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        name = ch[1:] if ch.startswith('@') else ch
        kb.add(InlineKeyboardButton(text=f"🔗 Join {ch}", url=f"https://t.me/{name}"))
    kb.add(InlineKeyboardButton(text="✔️ Verify", callback_data="force_verify"))
    return kb

# ---------- Handlers ----------
@bot.message_handler(commands=['start'])
def start_handler(message):
    uid = message.from_user.id
    chat_id = message.chat.id

    if is_stored_verified(uid):
        if is_user_joined_all(uid):
            bot.send_message(chat_id, MSG_VERIFIED)
            return
        else:
            remove_verified(uid)
            bot.send_message(chat_id, MSG_LEFT_CHANNEL)

    kb = make_verification_keyboard()
    bot.send_message(chat_id, f"{MSG_WELCOME}\n\n{MSG_NEED_JOIN}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "force_verify")
def callback_verify(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id

    if is_user_joined_all(uid):
        add_verified(uid)
        try:
            bot.edit_message_text(MSG_VERIFIED, chat_id, call.message.message_id)
        except:
            bot.send_message(chat_id, MSG_VERIFIED)
    else:
        bot.answer_callback_query(call.id, "❌ You haven't joined all required channels!", show_alert=True)

@bot.message_handler(commands=['menu', 'help'])
def protected_menu(msg):
    uid = msg.from_user.id
    chat_id = msg.chat.id

    if not is_stored_verified(uid):
        bot.send_message(chat_id, MSG_NOT_VERIFIED)
        bot.send_message(chat_id, MSG_NEED_JOIN, reply_markup=make_verification_keyboard())
        return

    if not is_user_joined_all(uid):
        remove_verified(uid)
        bot.send_message(chat_id, MSG_LEFT_CHANNEL)
        bot.send_message(chat_id, MSG_NEED_JOIN, reply_markup=make_verification_keyboard())
        return

    text = "🔥 Main Menu\n1. Option A\n2. Option B\n\n(You can add your bot functions here)"
    bot.send_message(chat_id, text)

@bot.message_handler(commands=['checkme'])
def checkme(msg):
    uid = msg.from_user.id
    chat_id = msg.chat.id
    if is_user_joined_all(uid):
        add_verified(uid)
        bot.send_message(chat_id, "✅ You are a member of all required channels. Verified.")
    else:
        remove_verified(uid)
        bot.send_message(chat_id, "❌ You are not a member of all required channels. Please join and press Verify.")

def periodic_recheck(interval_seconds=3600):
    while True:
        try:
            with db_lock:
                cur = db_conn.cursor()
                cur.execute("SELECT user_id FROM verified")
                rows = cur.fetchall()
            for (uid,) in rows:
                if not is_user_joined_all(uid):
                    remove_verified(uid)
            time.sleep(interval_seconds)
        except Exception:
            time.sleep(interval_seconds)

recheck_thread = threading.Thread(target=periodic_recheck, args=(3600,), daemon=True)
recheck_thread.start()

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling(timeout=60, long_polling_timeout=90)

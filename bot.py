import telebot
from telebot import types
import sqlite3
import os

# --- CONFIGURATION ---
API_TOKEN = '8380168360:AAGHMYAWiZfRc-DLYSQrNjDocjD1x4GHqYA'
CHANNELS = ['@roni_here', '@black_mrket'] # Dono channels ki list
ADMIN_ID = 5097298890 
REQUIRED_REFERS = 3

bot = telebot.TeleBot(API_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, ref_count INTEGER, 
                       referred_by INTEGER, has_joined INTEGER)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- HELPERS ---
def is_member(user_id):
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

# Safe Send Function (Fixes Line 193/403 Error)
def safe_send(chat_id, text, markup=None):
    try:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print(f"Bhejne mein galti (ID: {chat_id}): {e}")

def get_join_markup():
    markup = types.InlineKeyboardMarkup()
    for channel in CHANNELS:
        markup.add(types.InlineKeyboardButton(f"📢 Join {channel}", url=f"https://t.me/{channel.replace('@','')}"))
    markup.add(types.InlineKeyboardButton("🔄 I Have Joined Both", callback_data="check_join"))
    return markup

# --- USER HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    args = message.text.split()
    
    user = get_user(user_id)
    if not user:
        ref_by = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        conn = sqlite3.connect('bot_data.db')
        conn.execute("INSERT OR IGNORE INTO users VALUES (?, 0, ?, 0)", (user_id, ref_by))
        conn.commit()
        conn.close()
        # Safe Admin Notification
        safe_send(ADMIN_ID, f"🆕 **Naya User:** {user_name}\n🆔 ID: `{user_id}`")
    
    if not is_member(user_id):
        safe_send(user_id, "🛑 **Access Denied!**\n\nBot use karne ke liye neeche diye gaye **Dono** channels join karein.", markup=get_join_markup())
        return

    user = get_user(user_id)
    if user and user[3] == 0:
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
        if user[2]:
            conn.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (user[2],))
            safe_send(user[2], "🎉 **Referral Success!** Aapko +1 point mila.")
        conn.commit()
        conn.close()

    ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    p = get_user(user_id)[1] if get_user(user_id) else 0
    safe_send(user_id, f"📊 **Points:** `{p}/{REQUIRED_REFERS}`\n🔗 **Link:** `{ref_link}`")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check(call):
    if is_member(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verified!", show_alert=True)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Dono channels join nahi kiye!", show_alert=True)

@bot.message_handler(commands=['claim'])
def claim(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not is_member(user_id):
        safe_send(user_id, "⚠️ Join channels first!", markup=get_join_markup())
        return

    if user and user[1] >= REQUIRED_REFERS:
        if not os.path.exists("accounts.txt"):
            safe_send(user_id, "❌ Error: Stock file missing.")
            return
        with open("accounts.txt", "r") as f:
            accounts = f.readlines()
        if not accounts:
            safe_send(user_id, "⚠️ Stock empty hai!")
            return

        gift = accounts[0].strip()
        with open("accounts.txt", "w") as f:
            f.writelines(accounts[1:])

        safe_send(user_id, f"🎁 **Aapka Reward:**\n\n`{gift}`")
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET ref_count = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    else:
        safe_send(user_id, f"❌ Points kam hain. ({user[1] if user else 0}/{REQUIRED_REFERS})")

# --- ADMIN COMMANDS ---

@bot.message_handler(commands=['admin'])
def admin_p(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('bot_data.db')
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        msg = (f"🛠 **Admin Panel**\nUsers: {count}\nLimit: {REQUIRED_REFERS}\n\n"
               f"/addpoint [ID] [N]\n/add [email:pass]\n/setlimit [n]\n/broadcast [msg]")
        safe_send(ADMIN_ID, msg)

@bot.message_handler(commands=['addpoint'])
def manual_points(message):
    if message.from_user.id == ADMIN_ID:
        try:
            args = message.text.split()
            uid, pts = int(args[1]), int(args[2])
            conn = sqlite3.connect('bot_data.db')
            conn.execute("UPDATE users SET ref_count = ref_count + ? WHERE user_id = ?", (pts, uid))
            conn.commit()
            conn.close()
            safe_send(ADMIN_ID, f"✅ User `{uid}` ko {pts} points de diye.")
            safe_send(uid, f"🎁 Admin ne aapko {pts} points bonus diye hain!")
        except: safe_send(ADMIN_ID, "Format: `/addpoint 12345 5`")

@bot.message_handler(commands=['add'])
def add_acc(message):
    if message.from_user.id == ADMIN_ID:
        acc = message.text.replace('/add ', '').strip()
        with open("accounts.txt", "a") as f:
            f.write(acc + "\n")
        safe_send(ADMIN_ID, "✅ Account Added!")

# --- RUN ---
init_db()
print("Bot Started (2 Channels - No Proxy)...")
bot.polling(none_stop=True)

import telebot
from telebot import types
import sqlite3
import os

# --- CONFIGURATION ---
API_TOKEN = '8380168360:AAGHMYAWiZfRc-DLYSQrNjDocjD1x4GHqYA'
CHANNEL_ID = '@roni_here' 
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
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def get_join_markup():
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")
    btn2 = types.InlineKeyboardButton("🔄 I Have Joined", callback_data="check_join")
    markup.add(btn1)
    markup.add(btn2)
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
        try:
            bot.send_message(ADMIN_ID, f"🆕 **Naya User:** {user_name}\n🆔 ID: `{user_id}`", parse_mode="Markdown")
        except: pass
    
    if not is_member(user_id):
        bot.send_message(user_id, "🛑 **Access Denied!**\n\nBot use karne ke liye channel join karein.", 
                         reply_markup=get_join_markup(), parse_mode="Markdown")
        return

    user = get_user(user_id)
    if user and user[3] == 0:
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
        if user[2]:
            conn.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (user[2],))
            try: bot.send_message(user[2], "🎉 **Referral Success!** +1 point mila.")
            except: pass
        conn.commit()
        conn.close()

    ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    p = get_user(user_id)[1]
    bot.send_message(user_id, f"📊 **Points:** `{p}/{REQUIRED_REFERS}`\n🔗 **Link:** `{ref_link}`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check(call):
    if is_member(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verified!", show_alert=True)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Join nahi kiya!", show_alert=True)

@bot.message_handler(commands=['claim'])
def claim(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not is_member(user_id):
        bot.send_message(user_id, "⚠️ Join channel first!", reply_markup=get_join_markup())
        return

    if user and user[1] >= REQUIRED_REFERS:
        if not os.path.exists("accounts.txt"):
            bot.send_message(user_id, "❌ Error: Stock file missing.")
            return
        with open("accounts.txt", "r") as f:
            accounts = f.readlines()
        if not accounts:
            bot.send_message(user_id, "⚠️ Stock empty hai!")
            return

        gift = accounts[0].strip()
        with open("accounts.txt", "w") as f:
            f.writelines(accounts[1:])

        bot.send_message(user_id, f"🎁 **Netflix Account:**\n\n`{gift}`", parse_mode="Markdown")
        conn = sqlite3.connect('bot_data.db')
        conn.execute("UPDATE users SET ref_count = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    else:
        bot.send_message(user_id, f"❌ Points kam hain ({user[1] if user else 0}/{REQUIRED_REFERS})")

# --- ADMIN COMMANDS ---

@bot.message_handler(commands=['admin'])
def admin_p(message):
    if message.from_user.id == ADMIN_ID:
        conn = sqlite3.connect('bot_data.db')
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        msg = (f"🛠 **Admin Panel**\nUsers: {count}\nLimit: {REQUIRED_REFERS}\n\n"
               f"/addpoint [ID] [N] - Points dene ke liye\n"
               f"/add [email:pass] - Stock add karein\n"
               f"/setlimit [n] - Target change karein\n"
               f"/broadcast [msg] - Announcement")
        bot.send_message(ADMIN_ID, msg)

@bot.message_handler(commands=['addpoint'])
def manual_points(message):
    if message.from_user.id == ADMIN_ID:
        try:
            args = message.text.split()
            uid = int(args[1])
            pts = int(args[2])
            conn = sqlite3.connect('bot_data.db')
            conn.execute("UPDATE users SET ref_count = ref_count + ? WHERE user_id = ?", (pts, uid))
            conn.commit()
            conn.close()
            bot.send_message(ADMIN_ID, f"✅ User `{uid}` ko {pts} points de diye gaye.")
            bot.send_message(uid, f"🎁 Admin ne aapko {pts} points bonus diye hain!")
        except: bot.send_message(ADMIN_ID, "Usage: `/addpoint 12345 5`")

@bot.message_handler(commands=['add'])
def add_acc(message):
    if message.from_user.id == ADMIN_ID:
        acc = message.text.replace('/add ', '').strip()
        if acc and ":" in acc:
            with open("accounts.txt", "a") as f:
                f.write(acc + "\n")
            bot.send_message(ADMIN_ID, "✅ Account Added!")
        else: bot.send_message(ADMIN_ID, "Usage: `/add email:pass`")

@bot.message_handler(commands=['setlimit'])
def set_limit(message):
    global REQUIRED_REFERS
    if message.from_user.id == ADMIN_ID:
        try:
            REQUIRED_REFERS = int(message.text.split()[1])
            bot.send_message(ADMIN_ID, f"✅ Limit changed to {REQUIRED_REFERS}")
        except: bot.send_message(ADMIN_ID, "Usage: `/setlimit 10`")

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id == ADMIN_ID:
        msg_text = message.text.replace('/broadcast ', '')
        conn = sqlite3.connect('bot_data.db')
        users = conn.execute("SELECT user_id FROM users").fetchall()
        conn.close()
        for u in users:
            try: bot.send_message(u[0], f"📢 **Announcement:**\n\n{msg_text}", parse_mode="Markdown")
            except: pass
        bot.send_message(ADMIN_ID, "✅ Broadcast completed.")

# --- RUN ---
init_db()
print("Bot Started (All Features Active)...")
bot.polling(none_stop=True)

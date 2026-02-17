const TelegramBot = require('node-telegram-bot-api');
const express = require('express');
const fs = require('fs');
const path = require('path');

// --- CONFIGURATION ---
const TOKEN = '8380168360:AAGHMYAWiZfRc-DLYSQrNjDocjD1x4GHqYA';
const ADMIN_ID = 5097298890;
const CHANNELS = ['@roni_here', '@black_mrket'];
let REQUIRED_REFERS = 3;

// Bot instance (Polling mode)
const bot = new TelegramBot(TOKEN, { polling: true });
const app = express();

// --- DATABASE SETUP (JSON based for easy hosting) ---
const dbPath = path.join(__dirname, 'database.json');
if (!fs.existsSync(dbPath)) {
    fs.writeFileSync(dbPath, JSON.stringify({ users: {} }));
}

function getDB() {
    return JSON.parse(fs.readFileSync(dbPath));
}

function saveDB(data) {
    fs.writeFileSync(dbPath, JSON.stringify(data, null, 2));
}

// --- HELPERS ---

// Channel Join Check
async function isMember(userId) {
    for (const channel of CHANNELS) {
        try {
            const member = await bot.getChatMember(channel, userId);
            const status = member.status;
            if (!['member', 'administrator', 'creator'].includes(status)) return false;
        } catch (e) {
            return false;
        }
    }
    return true;
}

// Safe Message Sender (Fixes 403 Forbidden/Line 193 error)
async function safeSend(chatId, text, markup = {}) {
    try {
        return await bot.sendMessage(chatId, text, { parse_mode: 'Markdown', ...markup });
    } catch (e) {
        console.log(`Error sending to ${chatId}: ${e.message}`);
        return null;
    }
}

function getJoinMarkup() {
    const keyboard = CHANNELS.map(ch => [{ text: `📢 Join ${ch}`, url: `https://t.me/${ch.replace('@', '')}` }]);
    keyboard.push([{ text: "🔄 I Have Joined Both", callback_data: "check_join" }]);
    return { reply_markup: { inline_keyboard: keyboard } };
}

// --- HANDLERS ---

bot.onText(/\/start (.+)?/, async (msg, match) => {
    const userId = msg.from.id;
    const userName = msg.from.first_name;
    const refBy = match[1]; // Referral ID from link
    let db = getDB();

    // New User Registration
    if (!db.users[userId]) {
        db.users[userId] = {
            points: 0,
            referredBy: (refBy && !isNaN(refBy)) ? parseInt(refBy) : null,
            hasJoined: false,
            name: userName
        };
        saveDB(db);
        safeSend(ADMIN_ID, `🆕 **Naya User:** ${userName}\n🆔 ID: \`${userId}\``);
    }

    // Check Membership
    if (!(await isMember(userId))) {
        return safeSend(userId, "🛑 **Access Denied!**\n\nBot use karne ke liye dono channels join karein.", getJoin_markup());
    }

    // Referral Point Credit
    if (db.users[userId] && !db.users[userId].hasJoined) {
        db.users[userId].hasJoined = true;
        const referrerId = db.users[userId].referredBy;
        if (referrerId && db.users[referrerId]) {
            db.users[referrerId].points += 1;
            safeSend(referrerId, "🎉 **Referral Success!** Aapko +1 point mila.");
        }
        saveDB(db);
    }

    const refLink = `https://t.me/${(await bot.getMe()).username}?start=${userId}`;
    const p = db.users[userId].points;
    safeSend(userId, `📊 **Points:** \`${p}/${REQUIRED_REFERS}\`\n🔗 **Link:** \`${refLink}\``);
});

// Callback for "I Have Joined"
bot.on('callback_query', async (query) => {
    if (query.data === 'check_join') {
        if (await isMember(query.from.id)) {
            bot.answerCallbackQuery(query.id, { text: "✅ Verified!", show_alert: true });
            bot.deleteMessage(query.message.chat.id, query.message.message_id).catch(() => {});
            // Restart start logic
            bot.processUpdate({ message: { ...query.message, from: query.from, text: '/start' } });
        } else {
            bot.answerCallbackQuery(query.id, { text: "❌ Dono channels join nahi kiye!", show_alert: true });
        }
    }
});

// Claim Handler
bot.onText(/\/claim/, async (msg) => {
    const userId = msg.from.id;
    const db = getDB();
    const user = db.users[userId];

    if (!(await isMember(userId))) return safeSend(userId, "⚠️ Join channels first!", getJoinMarkup());

    if (user && user.points >= REQUIRED_REFERS) {
        const stockPath = path.join(__dirname, 'accounts.txt');
        if (!fs.existsSync(stockPath)) return safeSend(userId, "❌ Error: Stock file missing.");

        let accounts = fs.readFileSync(stockPath, 'utf8').split('\n').filter(line => line.trim() !== '');
        if (accounts.length === 0) return safeSend(userId, "⚠️ Stock empty hai!");

        const gift = accounts.shift();
        fs.writeFileSync(stockPath, accounts.join('\n'));

        safeSend(userId, `🎁 **Aapka Reward:**\n\n\`${gift}\``);
        user.points = 0;
        saveDB(db);
        safeSend(ADMIN_ID, `💰 User \`${userId}\` ne reward claim kiya.`);
    } else {
        safeSend(userId, `❌ Points kam hain. (${user ? user.points : 0}/${REQUIRED_REFERS})`);
    }
});

// --- ADMIN COMMANDS ---

// Add Point
bot.onText(/\/addpoint (\d+) (\d+)/, (msg, match) => {
    if (msg.from.id !== ADMIN_ID) return;
    const targetId = match[1];
    const pts = parseInt(match[2]);
    let db = getDB();

    if (db.users[targetId]) {
        db.users[targetId].points += pts;
        saveDB(db);
        safeSend(ADMIN_ID, `✅ User \`${targetId}\` ko ${pts} points diye.`);
        safeSend(targetId, `🎁 Admin ne aapko ${pts} points bonus diye hain!`);
    }
});

// Broadcast
bot.onText(/\/broadcast (.+)/, (msg, match) => {
    if (msg.from.id !== ADMIN_ID) return;
    const text = match[1];
    const db = getDB();
    Object.keys(db.users).forEach(uid => {
        safeSend(uid, `📢 **Announcement:**\n\n${text}`);
    });
    safeSend(ADMIN_ID, "✅ Broadcast completed.");
});

// Set Limit
bot.onText(/\/setlimit (\d+)/, (msg, match) => {
    if (msg.from.id !== ADMIN_ID) return;
    REQUIRED_REFERS = parseInt(match[1]);
    safeSend(ADMIN_ID, `✅ Limit changed to ${REQUIRED_REFERS}`);
});

// --- RENDER/VERCEL KEEP-ALIVE ---
app.get('/', (req, res) => res.send('Bot is Running!'));
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Server active on port ${PORT}`));

console.log("Node.js Bot Started...");

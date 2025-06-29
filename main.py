import os
import re
import telebot
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from google_auth_helper import get_credentials
from googleapiclient.discovery import build
from flask import Flask
from threading import Thread

# === НАСТРОЙКИ ===
TOKEN = os.environ['TELEGRAM_TOKEN']
ADMIN_IDS = [531492235, 1272080338]
EXEMPT_USERS = set(map(str, ADMIN_IDS + [6515051323]))
GROUP_CHAT_ID = -1002619892652
SPREADSHEET_ID = "1zqUIE7aNMnt5NaG0SzHXu5uqJnUaSiSQ2Tx78J6r7PI"
USERS_SHEET = "users"
CRM_SHEET = "crm"
PAYMENTS_SHEET = "payments"

bot = telebot.TeleBot(TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = get_credentials(SCOPES)
service = build('sheets', 'v4', credentials=creds)

# === FLASK: для UptimeRobot ===
app = Flask('')

@app.route('/ping')
def ping():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_flask).start()

# === GOOGLE SHEETS ===
def get_sheet(sheet):
    return service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{sheet}!A:Z").execute().get("values", [])

def append_sheet(sheet, values):
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A:Z",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]}
    ).execute()

def update_sheet_row(sheet, row_index, values):
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A{row_index}:Z{row_index}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]}
    ).execute()

def find_row(sheet, user_id):
    rows = get_sheet(sheet)
    for i, row in enumerate(rows):
        if row and row[0] == str(user_id):
            return i + 1, row
    return None, None

def update_or_append_user(uid, username, paid, access_until, whatsapp, invite_link):
    values = [str(uid), username, str(paid), access_until, whatsapp, invite_link or ""]
    row_index, _ = find_row(USERS_SHEET, uid)
    if row_index:
        update_sheet_row(USERS_SHEET, row_index, values)
    else:
        append_sheet(USERS_SHEET, values)

# === СОСТОЯНИЯ РЕГИСТРАЦИИ ===
STATES = {}

@bot.message_handler(commands=['start'])
def start(msg):
    STATES[msg.chat.id] = {"step": "last_name"}
    bot.reply_to(msg, "Введите вашу фамилию:")

@bot.message_handler(commands=['admin'])
def handle_admin(msg):
    if msg.from_user.id not in ADMIN_IDS:
        return
    users = get_sheet(USERS_SHEET)
    total = len(users) - 1
    active = [row for row in users[1:] if len(row) > 3 and row[2].lower() == "true" and datetime.fromisoformat(row[3]) > datetime.now()]
    bot.reply_to(msg, f"📊 Всего пользователей: {total}\n✅ Активных подписок: {len(active)}")

@bot.message_handler(func=lambda m: m.chat.id in STATES)
def handle_flow(msg):
    user_id = msg.chat.id
    state = STATES.get(user_id, {})
    step = state.get("step")

    if step == "last_name":
        state["last_name"] = msg.text.strip()
        state["step"] = "name"
        bot.send_message(user_id, "Введите ваше имя:")

    elif step == "name":
        state["name"] = msg.text.strip()
        state["step"] = "whatsapp"
        bot.send_message(user_id, "Введите номер WhatsApp в формате +7XXXXXXXXXX")

    elif step == "whatsapp":
        phone = msg.text.strip().replace(" ", "")
        if not re.match(r"^\+7\d{10}$", phone):
            return bot.send_message(user_id, "❗ Номер должен быть в формате +7XXXXXXXXXX")
        state["whatsapp"] = phone

        row_idx, row = find_row(USERS_SHEET, user_id)
        if row and row[2].lower() == "true" and row[3] and datetime.fromisoformat(row[3]) > datetime.now():
            return bot.send_message(user_id, f"✅ У вас уже есть активная подписка до {row[3]}.")

        state["step"] = "level"
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for lvl in ["Beginner (Начальный)", "Elementary (Элементарный)", "Pre-Intermediate", "Intermediate", "Upper-Intermediate", "Advanced", "Native Speaker"]:
            markup.add(lvl)
        bot.send_message(user_id, "Выберите уровень английского:", reply_markup=markup)

    elif step == "level":
        state["level"] = msg.text.strip()
        state["step"] = "done"

        append_sheet(CRM_SHEET, [
            user_id, msg.from_user.username or "no_username", state['last_name'], state['name'],
            state['whatsapp'], state['level'], datetime.now().isoformat()
        ])

        update_or_append_user(
            uid=user_id,
            username=msg.from_user.username or "no_username",
            paid=False,
            access_until="",
            whatsapp=state['whatsapp'],
            invite_link=""
        )

        bot.send_message(user_id, "Спасибо! Ожидаем подтверждения оплаты.", reply_markup=telebot.types.ReplyKeyboardRemove())
        kb = telebot.types.InlineKeyboardMarkup()
        kb.add(telebot.types.InlineKeyboardButton("✅ Оплата получена", callback_data=f"confirm_{user_id}"))
        kb.add(telebot.types.InlineKeyboardButton("❌ Оплата НЕ получена", callback_data=f"notpaid_{user_id}"))
        bot.send_message(ADMIN_IDS[0], f"Новый пользователь @{msg.from_user.username} ({user_id})\nИмя: {state['name']} {state['last_name']}\nWhatsApp: {state['whatsapp']}\nУровень: {state['level']}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_"))
def handle_confirm(call):
    uid = int(call.data.split("_")[1])
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("Kaspi (Даулет) — 10990", callback_data=f"paid_daulet_{uid}"))
    kb.add(telebot.types.InlineKeyboardButton("Kaspi (Жанибек) — 10990", callback_data=f"paid_zhanibek_{uid}"))
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
    bot.answer_callback_query(call.id, "Выберите источник оплаты")

@bot.callback_query_handler(func=lambda c: c.data.startswith("notpaid_"))
def handle_notpaid(call):
    uid = int(call.data.split("_")[1])
    update_or_append_user(uid, "", False, "", "", "")
    bot.send_message(uid, "Оплата не подтверждена.")
    bot.answer_callback_query(call.id, "Отклонено")

@bot.callback_query_handler(func=lambda c: c.data.startswith("paid_"))
def confirm_paid(call):
    _, method, uid = call.data.split("_")
    uid = int(uid)
    link = requests.post(f"https://api.telegram.org/bot{TOKEN}/createChatInviteLink", json={"chat_id": GROUP_CHAT_ID, "member_limit": 1}).json().get("result", {}).get("invite_link")
    expiry = datetime.now() + timedelta(days=100)
    _, old = find_row(USERS_SHEET, uid)
    username = old[1] if old else ""
    whatsapp = old[4] if old else ""
    update_or_append_user(uid, username, True, expiry.isoformat(), whatsapp, link)
    append_sheet(PAYMENTS_SHEET, [uid, datetime.now().isoformat(), f"Kaspi ({'Даулет' if method == 'daulet' else 'Жанибек'})", "10990"])
    bot.send_message(uid, f"Оплата подтверждена. Вот ссылка в группу:\n{link}")
    bot.answer_callback_query(call.id, "Ссылка отправлена")

# === КАЖДЫЙ ДЕНЬ КИК НЕПЛАТЕЛЬЩИКОВ ===
def daily_kick():
    rows = get_sheet(USERS_SHEET)
    for row in rows[1:]:
        if len(row) < 4 or not row[2].lower() == "true":
            continue
        uid, username, _, until, whatsapp, *_ = row + [""] * 6
        if uid in EXEMPT_USERS:
            continue
        try:
            if datetime.fromisoformat(until) < datetime.now():
                bot.kick_chat_member(GROUP_CHAT_ID, int(uid))
                bot.unban_chat_member(GROUP_CHAT_ID, int(uid))
                update_or_append_user(uid, username, False, "", whatsapp, "")
        except Exception as e:
            print(f"Ошибка кика {uid}: {e}")

scheduler.add_job(daily_kick, 'cron', hour=0, minute=1)

# === СТАРТ ПОЛЛИНГА ===
bot.remove_webhook()
bot.infinity_polling()

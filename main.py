import os
import telebot
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from replit import db

# === НАСТРОЙКИ ===
TOKEN = os.environ['TELEGRAM_TOKEN']
ADMIN_ID = 531492235                # Твой Telegram user_id
GROUP_CHAT_ID = -1002619892652     # ID закрытой группы
bot = telebot.TeleBot(TOKEN)

# === ПОДКЛЮЧЕНИЕ ПЛАНИРОВЩИКА ===
scheduler = BackgroundScheduler()
scheduler.start()

# === ФУНКЦИЯ: создать одноразовую ссылку ===
def create_oneuse_link():
    url = f"https://api.telegram.org/bot{TOKEN}/createChatInviteLink"
    payload = {
        "chat_id": GROUP_CHAT_ID,
        "member_limit": 1,
        "expire_date": None
    }
    resp = requests.post(url, json=payload).json()
    return resp.get("result", {}).get("invite_link")

# === ФУНКЦИЯ: сохраняем пользователя при /start ===
def save_user(user_id, username):
    if str(user_id) not in db:
        db[str(user_id)] = {
            "username": username,
            "paid": False,
            "invite_link": None,
            "access_until": None
        }

# === Клавиатура для подтверждения ===
def payment_keyboard(user_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        "✅ Оплата получена", callback_data=f"paid_{user_id}"
    ))
    markup.add(telebot.types.InlineKeyboardButton(
        "❌ Оплата НЕ получена", callback_data=f"notpaid_{user_id}"
    ))
    return markup

# === Обработчик команды /start ===
@bot.message_handler(commands=['start'])
def on_start(message):
    u = message.from_user
    save_user(u.id, u.username or "no_username")
    bot.reply_to(message, "Привет! Ожидаем подтверждения оплаты.")
    bot.send_message(ADMIN_ID,
                     f"Пользователь @{u.username or u.first_name} (ID: {u.id}) подключился. Подтверждаете оплату?",
                     reply_markup=payment_keyboard(u.id))

# === Обработчик кнопок "оплачено / не оплачено" ===
@bot.callback_query_handler(func=lambda c: c.data.startswith(("paid_", "notpaid_")))
def on_payment_callback(call):
    if call.from_user.id != ADMIN_ID:
        return bot.answer_callback_query(call.id, "Только админ может подтверждать оплату.")
    raw = call.data
    uid = raw.split("_")[1]
    user = db.get(uid)
    if not user:
        return bot.answer_callback_query(call.id, "Пользователь не найден.")

    if raw.startswith("paid_"):
        link = create_oneuse_link()
        user["paid"] = True
        user["invite_link"] = link
        user["access_until"] = (datetime.now() + timedelta(days=100)).isoformat()
        db[uid] = user

        bot.send_message(int(uid), f"Оплата подтверждена. Ваша ссылка на группу:\n{link}")
        bot.answer_callback_query(call.id, "✅ Ссылка отправлена пользователю.")

    else:
        user["paid"] = False
        user["invite_link"] = None
        user["access_until"] = None
        db[uid] = user

        bot.send_message(int(uid), "Оплата НЕ подтверждена. Доступ не выдан.")
        bot.answer_callback_query(call.id, "❌ Отменено")

# === Периодическая проверка истёкших доступов ===
def daily_kick_check():
    now = datetime.now()
    expired = []
    for uid in db.keys():
        rec = db[uid]
        if rec.get("paid") and rec.get("access_until"):
            if datetime.fromisoformat(rec["access_until"]) < now:
                try:
                    bot.kick_chat_member(GROUP_CHAT_ID, int(uid))
                    rec["paid"] = False
                    rec["invite_link"] = None
                    rec["access_until"] = None
                    db[uid] = rec
                    expired.append(rec["username"])
                except Exception as e:
                    print("Ошибка при кике:", e)
    if expired:
        bot.send_message(ADMIN_ID, "Кикнуты: " + ", ".join(expired))

# Запускаем проверку каждый день в 00:01
scheduler.add_job(daily_kick_check, 'cron', hour=0, minute=1)

# === Запуск бота ===
bot.infinity_polling()

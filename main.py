from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext, Dispatcher
import threading
import time
import os

TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

admin_list = {}
abuse_filter = {}
delay_time = {}
DEFAULT_DELAY = 3600

BAD_WORDS = [
    "suar","harami","chutiya","bkl","mkl","c","bc","mc","betichodd","betichod","sexy","sex","sux","bitch",
    "lode","lwde","lwda","lund","boobs","boobies","gand","gandu","chut","madarchodo","madhrchod","madharchod",
    "randi","randiii","kuttiya","x","xx","xxx","mkc","burr","haramzadi","haramzada","kamina","bsdk","bhosdike",
    "bhoshda","boslike"
]

# ---------------- Helper ----------------
def is_admin(update: Update) -> bool:
    try:
        chat_member = update.effective_chat.get_member(update.effective_user.id)
        return chat_member.status in ["administrator", "creator"]
    except:
        return False


# ---------------- UI ----------------
def send_welcome_message(update: Update, context: CallbackContext):
    user = update.effective_user.first_name
    keyboard = [[InlineKeyboardButton("📜 Help & Commands", callback_data="help")]]
    msg = (
        f"🔒 Hello {user}, welcome back to *Security Bot!*\n\n"
        f"✨ Tagline: Keep your group clean, safe, and abuse-free — automatically!\n\n"
        f"Use the buttons below to navigate."
    )
    update.effective_message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def start(update: Update, context: CallbackContext):
    user = update.effective_user.first_name
    keyboard = [
        [InlineKeyboardButton("➕ Add to Group", url="https://t.me/YOUR_BOT_USERNAME?startgroup=true")],
        [InlineKeyboardButton("📜 Help & Commands", callback_data="help")]
    ]
    msg = (
        f"✨ Hello {user}, welcome to *Security Bot v3!*\n\n"
        f"🛡 Your Personal Group Guardian is ready.\n\n"
        f"🚀 *Features:*\n"
        f"• Auto delete media after 1 hour\n"
        f"• Delete edited messages (non-admin)\n"
        f"• Auto remove abusive messages\n"
        f"• Admin-only protection controls\n\n"
        f"💡 Use /help or button below."
    )
    update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def show_help(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
    help_text = (
        "📜 *Security Bot Commands*\n\n"
        "🛡 *Admin Only:*\n"
        "• `/authadmin` — Exempt yourself from deletions\n"
        "• `/unauthadmin` — Remove exemption\n"
        "• `/abuse on/off` — Toggle abuse filter\n"
        "• `/setdelay <minutes>` — Set media auto-delete time\n\n"
        "👁 *Auto Protections:*\n"
        "• Deletes non-admin edited messages\n"
        "• Deletes abusive words automatically\n"
        "• Deletes media after 1 hour (default)\n\n"
        "💡 Use `/start` anytime to reopen main menu."
    )
    update.effective_message.reply_text(help_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    if query.data == "help":
        show_help(update, context)
    elif query.data == "back":
        send_welcome_message(update, context)


# ---------------- Commands ----------------
def authadmin(update: Update, context: CallbackContext):
    if not is_admin(update):
        update.message.reply_text("❌ Only admins can use this command.")
        return
    chat_id = update.effective_chat.id
    admin_list.setdefault(chat_id, [])
    if update.effective_user.id not in admin_list[chat_id]:
        admin_list[chat_id].append(update.effective_user.id)
        update.message.reply_text("✅ You’re exempted from deletions.")
    else:
        update.message.reply_text("⚠️ Already exempted.")


def unauthadmin(update: Update, context: CallbackContext):
    if not is_admin(update):
        update.message.reply_text("❌ Only admins can use this command.")
        return
    chat_id = update.effective_chat.id
    if chat_id in admin_list and update.effective_user.id in admin_list[chat_id]:
        admin_list[chat_id].remove(update.effective_user.id)
        update.message.reply_text("🚫 Exemption removed.")
    else:
        update.message.reply_text("⚠️ You’re not exempted yet.")


def abuse(update: Update, context: CallbackContext):
    if not is_admin(update):
        update.message.reply_text("❌ Only admins can use this command.")
        return
    if len(context.args) == 0:
        update.message.reply_text("Usage: /abuse on or /abuse off")
        return
    mode = context.args[0].lower()
    chat_id = update.effective_chat.id
    abuse_filter[chat_id] = (mode == "on")
    update.message.reply_text(f"🧹 Abusive filter turned {'ON' if mode == 'on' else 'OFF'}.")


def setdelay(update: Update, context: CallbackContext):
    if not is_admin(update):
        update.message.reply_text("❌ Only admins can use this command.")
        return
    if len(context.args) == 0 or not context.args[0].isdigit():
        update.message.reply_text("Usage: /setdelay <minutes>")
        return
    chat_id = update.effective_chat.id
    delay_time[chat_id] = int(context.args[0]) * 60
    update.message.reply_text(f"⏳ Media deletion delay set to {context.args[0]} minutes.")


# ---------------- Auto Delete ----------------
def delete_abuse(update: Update, context: CallbackContext):
    message = update.message
    chat_id = message.chat_id
    if abuse_filter.get(chat_id, True):
        text = message.text.lower()
        if any(word in text for word in BAD_WORDS):
            try:
                message.delete()
            except:
                pass


def delete_edited(update: Update, context: CallbackContext):
    edited_message = update.edited_message
    chat_id = edited_message.chat_id
    user_id = edited_message.from_user.id
    if chat_id in admin_list and user_id in admin_list[chat_id]:
        return
    try:
        member = edited_message.chat.get_member(user_id)
        if member.status not in ["administrator", "creator"]:
            edited_message.delete()
    except:
        pass


def auto_delete_media(update: Update, context: CallbackContext):
    message = update.message
    chat_id = message.chat_id
    user_id = message.from_user.id
    try:
        member = message.chat.get_member(user_id)
        if member.status in ["administrator", "creator"]:
            return
    except:
        return

    delay = delay_time.get(chat_id, DEFAULT_DELAY)

    def delete_later(msg):
        time.sleep(delay)
        try:
            msg.delete()
        except:
            pass

    threading.Thread(target=delete_later, args=(message,)).start()


# ---------------- Flask Webhook ----------------
@app.route("/")
def home():
    return "✅ Security Bot v3 is active on Render!"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "ok"


if __name__ == "__main__":
    updater = Updater(TOKEN, use_context=True)
    bot = updater.bot
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", show_help))
    dp.add_handler(CommandHandler("authadmin", authadmin))
    dp.add_handler(CommandHandler("unauthadmin", unauthadmin))
    dp.add_handler(CommandHandler("abuse", abuse, pass_args=True))
    dp.add_handler(CommandHandler("setdelay", setdelay, pass_args=True))
    dp.add_handler(CallbackQueryHandler(button_callback))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, delete_abuse))
    dp.add_handler(MessageHandler(Filters.update.edited_message, delete_edited))
    dp.add_handler(MessageHandler(Filters.photo | Filters.video | Filters.document | Filters.sticker | Filters.animation, auto_delete_media))

    bot.set_webhook(f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=PORT)
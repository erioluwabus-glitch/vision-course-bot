from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging

# Bot token and admin ID 
TOKEN = "8138720265:AAHtklkJUBfb8Z9haLJylvcNad56lWT-WiE"
ADMIN_ID = 7109534825

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import json
import os
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(os.environ.get('GOOGLE_CREDENTIALS')), scope)
import logging
logging.basicConfig(level=logging.INFO)
logging.info("Credentials loaded successfully")
client = gspread.authorize(creds)
assignment_sheet = client.open("VisionCourseSupport").worksheet("Assignments")
wins_sheet = client.open("VisionCourseSupport").worksheet("Wins")

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! DM me for assignments/small wins: /submit [Module] or /sharewin. Post Major Wins/Testimonials in the group with 'Major Win' or 'Testimonial'. Use /status for progress."
    )

async def submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        await update.message.reply_text("Please DM me privately for assignments.")
        return
    args = context.args
    if not args or not args[0].isdigit() or int(args[0]) not in range(1, 13):
        await update.message.reply_text("Use /submit [Module Number] (1-12), e.g., /submit 4")
        return
    module = args[0]
    user = update.message.from_user.username or str(update.message.from_user.id)
    context.user_data['module'] = module
    context.user_data['mode'] = 'assignment'  # Track mode for submission
    await update.message.reply_text(f"Received @{user}'s Module {module} assignment. Post it now (text/video/etc.).")

async def sharewin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        await update.message.reply_text("DM me for small wins. Post Major Wins in the group!")
        return
    user = update.message.from_user.username or str(update.message.from_user.id)
    context.user_data['mode'] = 'small_win'  # Track mode for submission
    await update.message.reply_text(f"Thanks @{user}! Post your small win now (text/video/etc.).")

async def handle_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username or str(update.message.from_user.id)
    content_type = "Text" if update.message.text else "Video" if update.message.video else "Photo" if update.message.photo else "Link"
    content = update.message.text or "Media/Link"
    
    if update.message.chat.type == 'private':
        mode = context.user_data.get('mode', '')
        if mode == 'assignment':
            module = context.user_data.get('module', 'Unknown')
            status = "Submitted"
            grade = "Auto-Graded: 8/10 - Complete" if content_type == "Video" else "Auto-Graded: 6/10 - Submit a video for full marks"
            try:
                assignment_sheet.append_row([user, module, status, content_type, content, grade, update.message.date.isoformat()])
                await update.message.reply_text(f"Stored @{user}'s Module {module} assignment: {content_type}. {grade}. Share a Major Win in the group!")
            except Exception as e:
                logger.error(f"Assignment sheet write error: {e}")
                await update.message.reply_text("Error saving assignment. Check logs or contact admin.")
            del context.user_data['mode']
            del context.user_data['module']
        elif mode == 'small_win':
            try:
                wins_sheet.append_row([user, "Small " + content_type, content, update.message.date.isoformat()])
                await update.message.reply_text(f"Stored @{user}'s small win: {content_type}. Post Major Wins in the group!")
            except Exception as e:
                logger.error(f"Wins sheet write error: {e}")
                await update.message.reply_text("Error saving win. Check logs or contact admin.")
            del context.user_data['mode']
    elif update.message.chat.type in ['group', 'supergroup']:
        if update.message.text and ("major win" in update.message.text.lower() or "testimonial" in update.message.text.lower()):
            try:
                wins_sheet.append_row([user, "Major " + content_type, content, update.message.date.isoformat()])
                await update.message.reply_text(f"Congrats @{user} on the Major Win/Testimonial! Stored for admin review. Everyone, cheer with 👍!")
            except Exception as e:
                logger.error(f"Wins sheet write error: {e}")
                await update.message.reply_text("Error saving win. Contact admin.")

async def grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("Admin-only command.")
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /grade [Username] [Module] [Score/Feedback]")
        return
    user, module, feedback = args[0], args[1], " ".join(args[2:])
    try:
        assignment_sheet.append_row([user, module, "Graded", "", feedback, update.message.date.isoformat()])
        await update.message.reply_text(f"Graded @{user}'s Module {module}: {feedback}. Recorded for certification.")
    except Exception as e:
        logger.error(f"Grade sheet write error: {e}")
        await update.message.reply_text("Error grading. Contact admin.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user.username or str(update.message.from_user.id)
    try:
        assignments = assignment_sheet.get_all_records()
        user_assignments = [row for row in assignments if row.get("Username") == user]
        wins = wins_sheet.get_all_records()
        user_wins = [row for row in wins if row.get("Username") == user]
        small_wins = sum(1 for w in user_wins if w.get("Type", '').startswith("Small"))
        major_wins = sum(1 for w in user_wins if w.get("Type", '').startswith("Major"))
        response = f"@{user}'s Status:\nAssignments: {len(user_assignments)} submitted\nSmall Wins: {small_wins} shared\nMajor Wins/Testimonials: {major_wins} shared\nCheck certification progress in admin records."
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text("Error fetching status. Contact admin.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update:
        await update.message.reply_text("Error occurred. Try again or contact admin.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("submit", submit))
logging.info("Sheet updated for command: %s", update.message.text)
    application.add_handler(CommandHandler("sharewin", sharewin))
logging.info("Sheet updated for command: %s", update.message.text)
    application.add_handler(CommandHandler("grade", grade))
logging.info("Sheet updated for command: %s", update.message.text)
    application.add_handler(CommandHandler("status", status))
logging.info("Sheet updated for command: %s", update.message.text)
    application.add_handler(MessageHandler(filters.TEXT | filters.VIDEO | filters.PHOTO | filters.Document.ALL, handle_submission))
logging.info("Sheet updated for command: %s", update.message.text or update.message.caption)
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
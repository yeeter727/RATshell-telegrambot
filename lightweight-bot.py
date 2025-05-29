#!/bin/python
# Makeshift remote shell telegram bot

import subprocess
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

######### STARTUP #########
# read config file
with open("tg.conf") as f:
    exec(f.read(), globals())

if admin_id == 123456789:
    print("\nIt looks like the tg.conf file has default values. \nPlease make sure to add your ID and token to tg.conf. \n")
    exit()
    
# create access_log if not found
if not os.path.exists(access_log):
    with open(access_log, 'w') as f:
        f.write(
            "#######################\n"
            "UNAUTHORIZED ACTION LOG\n"
            "#######################"
        )

# log unauthorized access
def log_unauth(user, action):
    with open(access_log, "a") as f:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"\n[{now}] [{action}] User @{user}")

# check if running in windows
def in_windows():
    return (
        os.name == "nt"
    )
win = in_windows()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
###########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != admin_id:
        username = update.effective_user.username
        log_unauth(username, "/start")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="WARNING: Unknown user detected. \nAccess revoked. \n\nThis attempt has been logged.")
        return
    await update.message.reply_text(start_message)

async def handle_shell_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != admin_id:
        username = update.effective_user.username
        log_unauth(username, "Unsolicited message")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    else:        
        command = update.message.text.strip()
        try:
            if win:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
                output = result.stdout.decode('utf-8')
            else:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output = result.stdout.decode('utf-8')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=output)
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shell_commands))    # read messages as commands
    app.run_polling()

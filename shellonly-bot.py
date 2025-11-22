#!/bin/python
# Makeshift remote shell telegram bot
# this file only includes the shell and unauthorized access logging features

import subprocess
import logging
import os
import getpass
import socket
from datetime import datetime
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

######### STARTUP #########
# read config file
with open("tg.conf") as f:
    exec(f.read(), globals())

if owner_id == 123456789:
    print("\nIt looks like the tg.conf file has default values. \nPlease make sure to add your ID and token to tg.conf. \n")
    exit()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# comment the following line if you want to log all http requests
logging.getLogger("httpx").setLevel(logging.WARNING)

# create access_log if not found
if not os.path.exists(access_log):
    with open(access_log, 'w') as f:
        f.write(
            "#######################\n"
            "UNAUTHORIZED ACTION LOG\n"
            "#######################"
        )
    logging.info("Created access_log file.")

# check if the user is the owner
def is_owner(update, action):
    user_id = update.effective_user.id
    if user_id != owner_id:
        username = "@" + str(update.effective_user.username) or f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [{action}] User {username} ID: {user_id}")
        logging.warning(f"Unauthorized user logged: {username}")
        return False
    else:
        return True

# check if running in windows
def in_windows():
    return (os.name == "nt")
win = in_windows()

###########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/start"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="WARNING: Unknown user detected. \nAccess revoked. \n\nThis attempt has been logged.")
        return
    await update.message.reply_text(start_message, parse_mode='HTML')

async def handle_shell_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "Unsolicited message"):
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
            if not output.strip():
                output = "✓"   # send a checkmark if there is no output from the command
            await context.bot.send_message(chat_id=update.effective_chat.id, text=output)
            logging.info(f"Shell command executed: {command}")
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")

# function to replace placeholders in the start message
async def parse_start_message(app):
    try:
        chat = await app.bot.get_chat(owner_id)
        owner_un = "@" + str(chat.username) or f"{chat.first_name or ''} {chat.last_name or ''}".strip()
        if not owner_un:
            logging.warning("Owner chat returned no username/name.")
    except Exception as e:
        logging.warning("Could not fetch owner username at startup: %s", e)
    
    pwd = "<code>" + os.getcwd() + "</code>"
    os_user = "<code>" + str(getpass.getuser()) + "</code>"
    hostname = "<code>" + str(socket.gethostname()) + "</code>"

    original = start_message

    # changes at runtime, doesn't actually edit tg.conf
    globals()['start_message'] = start_message.replace("OWNER_USERNAME", owner_un)
    globals()['start_message'] = start_message.replace("OWNER_ID", str(owner_id))
    globals()['start_message'] = start_message.replace("WORKING_DIR", pwd)
    globals()['start_message'] = start_message.replace("OS_USER", os_user)
    globals()['start_message'] = start_message.replace("OS_HOSTNAME", hostname)
    globals()['start_message'] = start_message.replace("You can also forward photos/videos to me to upload them.", "")
    
    # only log if something actually changed
    if start_message != original:
        logging.info("Replaced placholders in the start message.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).post_init(parse_start_message).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shell_commands))    # read messages as commands
    app.run_polling()


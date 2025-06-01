#!/bin/python
# Makeshift remote shell telegram bot
# it can also store files sent to it and can send files to the user thru /get

import subprocess
import socket
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.constants import ChatAction

######### STARTUP #########
# read config file
if os.path.exists("tg.conf"):
    with open("tg.conf") as f:
        exec(f.read(), globals())
    # exit if default value
    if owner_id == 123456789:
        print("\nIt looks like the tg.conf file has default values. \nPlease make sure to add your ID and token to tg.conf.\n")
        exit()
else:
    print("Missing required tg.conf file.")
    exit()

# create access_log if not found
if not os.path.exists(access_log):
    with open(access_log, 'w') as f:
        f.write(
            "#######################\n"
            "UNAUTHORIZED ACTION LOG\n"
            "#######################"
        )

# check if user is the owner
def is_owner(update, action):
    user_id = update.effective_user.id
    if user_id != owner_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [{action}] User @{username}")
        return False
    else:
        return True

# function to check if running in termux
def in_termux():
    prefix = os.environ.get("PREFIX")
    home = os.environ.get("HOME")
    return (
        prefix == "/data/data/com.termux/files/usr"
        or (home and home.startswith("/data/data/com.termux"))
    )
termux = in_termux()

# check if running in windows
def in_windows():
    return (os.name == "nt")
win = in_windows()

# install fastfetch if running in win and not already installed
if win:
    winget_list = subprocess.run(["winget", "list", "Fastfetch-cli.Fastfetch"], capture_output=True, text=True, timeout=10)
    if not "Fastfetch-cli.Fastfetch" in winget_list.stdout:
        print("\nFastfetch is not installed (needed for the 'Run Neofetch' button).")
        ff_install = input("Would you like to install it? (Y/n): ")
        
        if ff_install.lower() != "n":
            print("Installing fastfetch (Windows version of neofetch) through winget...\n")
            subprocess.run(["winget", "install", "--silent", "--accept-package-agreements", "--accept-source-agreements", "Fastfetch-cli.Fastfetch"])
            print()
            fastfetch = True
        else:
            print("Skipping fastfetch install. 'Run Neofetch' button will not work.\n")
            fastfetch = False
    else:
        fastfetch = True

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
###########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/start"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="WARNING: Unknown user detected. \nAccess revoked. \n\nThis attempt has been logged.")
        return

    keyboard = [
        [InlineKeyboardButton("Get IP Info", callback_data='get_ip')],
        [InlineKeyboardButton("Neofetch", callback_data='run_neofetch')],
        [InlineKeyboardButton("Print Access Log", callback_data='print_log')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_message, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_owner(update, f"{query.data} button"):
        await query.edit_message_text(text="Access denied.")
        return

    if query.data == 'run_neofetch':
        try:
            if win:
                if fastfetch: 
                    result = subprocess.run(['fastfetch', '-l', 'none', '-s', 'title:separator:os:host:uptime:shell:cpu:memory:disk:break:separator:localip:publicip'], capture_output=True, text=True, timeout=10)
                    output = result.stdout.strip() or "No output from fastfetch.exe"
                else:
                    output = "fastfetch not installed."
            else:
                result = subprocess.run(['neofetch', '--stdout'], capture_output=True, text=True, timeout=10)
                output = result.stdout.strip() or "No output from neofetch."
        except Exception as e:
            output = f"Error: {str(e)}"

        keyboard = [[InlineKeyboardButton("Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=f"<pre>{output}</pre>", reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'get_ip':
        try:
            if termux:
                # get local IP address through termux-friendly method
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("9.9.9.9", 80))       # no actual connection made
                local_ip = s.getsockname()[0]
                s.close()

                # get public IP address
                pub_ip = subprocess.run(['curl', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nLocal IP Address:\n<code>{local_ip.strip()}</code>" or "No output from curl or socket connection."
            elif win:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("9.9.9.9", 80))       # no actual connection made
                local_ip = s.getsockname()[0]
                s.close()

                # get public IP address
                pub_ip = subprocess.run("$ProgressPreference = 'SilentlyContinue'; (Invoke-WebRequest https://ifconfig.me/ip).Content", shell=True, capture_output=True, text=True, executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nLocal IP Address:\n<code>{local_ip.strip()}</code>" or "No output from curl or socket connection."
            else:
                # get interfaces and addresses
                ip_cmd = "ip -o -4 a | awk '$2 != \"lo\" {print $2, $4}'"
                interfaces = subprocess.run(ip_cmd, shell=True, capture_output=True, text=True)

                # get public IP address
                pub_ip = subprocess.run(['curl', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nDevice Interfaces:\n<code>{interfaces.stdout.strip()}</code>" or "No output from curl or ip addr commands."
        except Exception as e:
            output = f"Error: {str(e)}"
        
        keyboard = [[InlineKeyboardButton("Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=output, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'print_log':
        with open(access_log, 'r') as file:
            content = file.read()

        keyboard = [[InlineKeyboardButton("Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=f"<code>{content}</code>", reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'go_back':
        # recreate the original menu
        keyboard = [
            [InlineKeyboardButton("Get IP Info", callback_data='get_ip')],
            [InlineKeyboardButton("Run Neofetch", callback_data='run_neofetch')],
            [InlineKeyboardButton("Print Access Log", callback_data='print_log')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=start_message, reply_markup=reply_markup)


async def handle_shell_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "Unsolicited message"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    else:
        command = update.message.text.strip()  # Get the command from the message
        try:
            if win:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
                output = result.stdout.decode('utf-8')
            else:
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output = result.stdout.decode('utf-8')
            if not output.strip():
                output = "✓"  # send a checkmark if there is no output from the command
            await context.bot.send_message(chat_id=update.effective_chat.id, text=output)
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")


async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/get"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="/get usage: \n<code>/get path/to/file.txt</code> \n\nor to get everything in a folder:\n<code>/get path/to/dir/</code>", parse_mode='HTML')
        return

    file_path = " ".join(context.args)
    if os.path.isfile(file_path):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, "rb"))
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to get file: {e}")
        return
    elif os.path.isdir(file_path):
        file_list = [
            os.path.join(file_path, f)
            for f in os.listdir(file_path)
            if os.path.isfile(os.path.join(file_path, f))
        ]
        if not file_list:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Directory is empty.")
            return

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sending <code>{len(file_list)}</code> files from directory: \n<code>{file_path}</code>", parse_mode='HTML')
        for fpath in file_list:
            try:
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
                await context.bot.send_document(chat_id=update.effective_chat.id, document=open(fpath, "rb"))
            except Exception as e:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Failed to send file {fpath}: {e}")
        return
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="File or directory not found.")
        return

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "Sent file"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    file_info = None
    filename = None

    # check most file types
    if update.message.document:
        file_info = await context.bot.get_file(update.message.document.file_id)
        filename = update.message.document.file_name
    elif update.message.photo:
        photo = update.message.photo[-1]
        file_info = await context.bot.get_file(photo.file_id)
        filename = f"photo_{photo.file_unique_id}.jpg"
    elif update.message.video:
        file_info = await context.bot.get_file(update.message.video.file_id)
        filename = update.message.video.file_name or f"video_{update.message.video.file_unique_id}.mp4"
    elif update.message.audio:
        file_info = await context.bot.get_file(update.message.audio.file_id)
        filename = update.message.audio.file_name or f"audio_{update.message.audio.file_unique_id}.mp3"
    elif update.message.voice:
        file_info = await context.bot.get_file(update.message.voice.file_id)
        filename = f"voice_{update.message.voice.file_unique_id}.ogg"
    elif update.message.animation:
        file_info = await context.bot.get_file(update.message.animation.file_id)
        filename = update.message.animation.file_name or f"animation_{update.message.animation.file_unique_id}.gif"

    if file_info and filename:
        save_path = os.path.join(upload_folder, filename)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Saving file...")
        await file_info.download_to_drive(save_path)
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"File saved: \n<code>{save_path}</code>", parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The file you sent is not supported for upload.")


if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('get', get_file))

    # read messages as commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shell_commands))
    
    # read all files for upload
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.ANIMATION, handle_upload))

    app.run_polling()

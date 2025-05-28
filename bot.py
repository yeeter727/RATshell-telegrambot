#!/bin/python
# Makeshift remote shell telegram bot for linux systems
# it can also archive videos/photos sent to it (only saves TG file IDs, does not download files)

import subprocess
import socket
import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler


######### STARTUP #########
# read config file
if os.path.exists("tg.conf"):
    with open("tg.conf") as f:
        exec(f.read(), globals())
    # exit if default value
    if admin_id == 123456789:
        print("It looks like the tg.conf file has default values. \nPlease make sure to add your ID and token to tg.conf.")
        exit()
else:
    print("Missing required tg.conf file. \nDid you download it?")
    exit()

# create access_log if not found
if not os.path.exists(access_log):
    with open(access_log, 'w') as f:
        f.write(
            "#######################\n"
            "UNAUTHORIZED ACTION LOG\n"
            "#######################"
        )

user_state = {}                   # dictionary to store the state of each user
user_state[admin_id] = 'shell'    # allow admin to immediately send commands

# load media links from the text file
def load_media_links():
    if os.path.exists(media_file):
        with open(media_file, 'r') as f:
            return [line.strip() for line in f.readlines()]
    else:
        # create media_file if it doesnt exist
        with open(media_file, 'w') as f:
            pass
        return []
media_links = load_media_links()

def save_media_links(media_links):
    with open(media_file, 'w') as f:
        for link in media_links:
            f.write(f"{link}\n")

# function to check if running in termux
def in_termux():
    prefix = os.environ.get("PREFIX")
    home = os.environ.get("HOME")
    return (
        prefix == "/data/data/com.termux/files/usr"
        or (home and home.startswith("/data/data/com.termux"))
    )
termux = in_termux()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
###########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != admin_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [/start] User @{username}")
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

    user_id = update.effective_user.id
    if query.from_user.id != admin_id: 
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [{query.data} button] User @{username}")
        await query.edit_message_text(text="Access denied.")
        return

    if query.data == 'run_neofetch':
        try:
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

        await query.edit_message_text(text=content, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'go_back':
        # recreate the original menu
        keyboard = [
            [InlineKeyboardButton("Get IP Info", callback_data='get_ip')],
            [InlineKeyboardButton("Run Neofetch", callback_data='run_neofetch')],
            [InlineKeyboardButton("Print Access Log", callback_data='print_log')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=start_message, reply_markup=reply_markup)


async def enter_shell_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == admin_id:
        if user_id not in user_state:
            user_state[user_id] = 'shell'
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Entering shell mode. Type your commands.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Shell mode already enabled.")
    else:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [/x (enter shell)] User @{username}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")


async def exit_shell_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == admin_id and user_state.get(user_id) == 'shell':
        del user_state[user_id]  # Remove the user's shell mode state
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Exiting shell mode.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not in shell mode.")


async def handle_shell_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != admin_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [Unsolicited message] User @{username}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    if user_state.get(user_id) == 'shell':
        # user is in shell mode, execute the command
        command = update.message.text.strip()  # Get the command from the message
        try:
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = result.stdout.decode('utf-8')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=output)
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")


async def archive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != admin_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [Sent media] User @{username}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    # check if the message contains a photo or video
    if update.message and not 'remove_next' in context.user_data and (update.message.photo or update.message.video):
        file_id = None
        
        # store the photo file ID
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        # store the video file ID
        elif update.message.video:
            file_id = update.message.video.file_id

        if file_id and file_id not in media_links:
            media_links.append(file_id)

            save_media_links(media_links)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Archived \n[{file_id}]")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed: already archived.")

    # check if /r is active
    elif update.message and 'remove_next' in context.user_data and context.user_data['remove_next'] and (update.message.photo or update.message.video):
        if update.message.photo:
            media_id = update.message.photo[-1].file_id
        elif update.message.video:
            media_id = update.message.video.file_id

        if media_id in media_links:
            media_links.remove(media_id)
            save_media_links(media_links)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Removed \n[{media_id}]")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Not found \n[{media_id}]")
        # stop waiting for media to remove
        del context.user_data['remove_next']


async def remove_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != admin_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [/r (remove media)] User @{username}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Send item to be removed.")
    context.user_data['remove_next'] = True


async def forward_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != admin_id:
        username = update.effective_user.username
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{now}] [/v (foward media)] User @{username}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    if media_links:
        total = len(media_links)
        for file_id in media_links:
            try:
                await context.bot.send_video(chat_id=update.effective_chat.id, video=file_id)
            except Exception as e:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=file_id)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Total: {total}")
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No media found. Send a photo or video first."
        )

if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('x', enter_shell_mode))
    app.add_handler(CommandHandler('q', exit_shell_mode))
    app.add_handler(CommandHandler('v', forward_media))
    app.add_handler(CommandHandler('r', remove_media))

    # read messages as commands
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shell_commands))

    # set up handler to look for photos and videos
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, archive_media))

    app.run_polling()

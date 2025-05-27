#!/bin/python
# Makeshift remote shell telegram bot (RATelegram) for linux systems
# it can also archive videos/photos sent to it (only saves TG file IDs, does not download files)

import subprocess
import socket
import logging
import os
import shutil
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

#########################
# read config file
with open("tg.conf") as f:
    exec(f.read(), globals())

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

user_state = {}                   # Dictionary to store the state of each user
user_state[admin_id] = 'shell'    # set default state of admin to 'shell'

# make backup on program start
shutil.copyfile(media_file, f'src/bak.{media_file}')

# load media links from the text file (one link per line)
def load_media_links():
    if os.path.exists(media_file):
        with open(media_file, 'r') as f:
            return [line.strip() for line in f.readlines()]
    return []

def save_media_links(media_links):
    with open(media_file, 'w') as f:
        for link in media_links:
            f.write(f"{link}\n")

media_links = load_media_links()
#######################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != admin_id:
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [/start] User {user_id}\n")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="WARNING: Unknown user detected. \nAccess revoked. \n\nThis attempt has been logged.")
        return

    keyboard = [
        [InlineKeyboardButton("Get IP Info", callback_data='get_ip')],
        [InlineKeyboardButton("Neofetch", callback_data='run_neofetch')],
        [InlineKeyboardButton("Forward Media", callback_data='forward_media')],
        [InlineKeyboardButton("Print Access Log", callback_data='print_unauth')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(start_message, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    user_id = update.effective_user.id
    if query.from_user.id != admin_id: 
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [{query.data} button] User {user_id}\n")
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
            # get local IP address
            #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            #s.connect(("9.9.9.9", 80))
            #local_ip = s.getsockname()[0]
            #s.close()
            
            # get interfaces and addresses
            ip_cmd = "ip -o -4 a | awk '$2 != \"lo\" {print $2, $4}'"
            interfaces = subprocess.run(ip_cmd, shell=True, capture_output=True, text=True)

            # get public IP address
            pub_ip = subprocess.run(['curl', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
            output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nDevice Interfaces:\n<code>{interfaces.stdout.strip()}</code>" or "No output from curl or socket connection."
        except Exception as e:
            output = f"Error: {str(e)}"
        
        keyboard = [[InlineKeyboardButton("Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=output, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'forward_media':
        total = 0
        if media_links:
            total = len(media_links)

            sent_message_ids = []

            for file_id in media_links:
                try:
                    msg = await context.bot.send_video(chat_id=query.message.chat_id, video=file_id)
                    sent_message_ids.append(msg.message_id)
                except Exception:
                    try:
                        msg = await context.bot.send_photo(chat_id=query.message.chat_id, photo=file_id)
                        sent_message_ids.append(msg.message_id)
                    except Exception as e:
                        await context.bot.send_message(chat_id=query.message.chat_id, text=f"Error sending media: {e}")

            # Save message IDs to context for cleanup later
            context.user_data["sent_media_ids"] = sent_message_ids

        else:
            await query.edit_message_text(text="No media found. Send a photo or video first.")

        # Show Back button
        keyboard = [[InlineKeyboardButton("Hide and return", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"Total: {total}", reply_markup=reply_markup)

    elif query.data == 'print_unauth':
        with open(access_log, 'r') as file:
            content = file.read()

        keyboard = [[InlineKeyboardButton("Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=content, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'go_back':
        # Delete previously sent media, if any
        sent_ids = context.user_data.get("sent_media_ids", [])
        for msg_id in sent_ids:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
            except Exception:
                pass  # Ignore messages that can't be deleted

        context.user_data["sent_media_ids"] = []  # Clear list

        # Recreate the original menu
        keyboard = [
            [InlineKeyboardButton("Get IP Info", callback_data='get_ip')],
            [InlineKeyboardButton("Run Neofetch", callback_data='run_neofetch')],
            [InlineKeyboardButton("Forward Media", callback_data='forward_media')],
            [InlineKeyboardButton("Print Access Log", callback_data='print_unauth')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=start_message, reply_markup=reply_markup)


async def enter_shell_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == admin_id:
        if user_id not in user_state:
            user_state[user_id] = 'shell'  # Set the user's state to 'shell'
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Entering shell mode. Type your commands.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Shell mode already enabled.")
    else:
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [/x (enter shell)] User {user_id}\n")
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
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [Unsolicited message] User {user_id}\n")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    if user_state.get(user_id) == 'shell':
        # User is in shell mode, execute the command
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
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [Sent media] User {user_id}\n")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return

    # Check if the message contains a photo or video
    if update.message and not 'remove_next' in context.user_data and (update.message.photo or update.message.video):
        file_id = None
        
        # Store the photo file ID
        if update.message.photo:
            file_id = update.message.photo[-1].file_id  # Get the highest resolution photo file_id
        # Store the video file ID
        elif update.message.video:
            file_id = update.message.video.file_id

        if file_id and file_id not in media_links:
            media_links.append(file_id)

            # Persist the media links to the JSON file
            save_media_links(media_links)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Archived [{file_id}]")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Failed: already archived.")

    # check if /r is active
    elif update.message and 'remove_next' in context.user_data and context.user_data['remove_next'] and (update.message.photo or update.message.video):
        if update.message.photo:
            media_id = update.message.photo[-1].file_id  # Take the highest resolution photo
        elif update.message.video:
            media_id = update.message.video.file_id

        if media_id in media_links:
            media_links.remove(media_id)
            save_media_links(media_links)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Removed [{media_id}]"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Not found [{media_id}]"
            )
        # Stop waiting for media
        del context.user_data['remove_next']


async def remove_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != admin_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [/r (remove media)] User {user_id}\n")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Send item to be removed.")
    context.user_data['remove_next'] = True


async def forward_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != admin_id:
        with open(access_log, "a") as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{now}] [/v (foward media)] User {user_id}\n")
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

    start_handler = CommandHandler('start', start)
    execute_handler = CommandHandler('x', enter_shell_mode)
    quit_handler = CommandHandler('q', exit_shell_mode)
    forward_handler = CommandHandler('v', forward_media)
    remove_handler = CommandHandler('r', remove_media)

    shell_message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shell_commands)
    app.add_handler(shell_message_handler)  # Handle shell commands
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(start_handler)
    app.add_handler(execute_handler)
    app.add_handler(quit_handler)
    app.add_handler(forward_handler)
    app.add_handler(remove_handler)

    media_handler = MessageHandler(filters.PHOTO | filters.VIDEO, archive_media)
    app.add_handler(media_handler)

    app.run_polling()

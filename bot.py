#!/bin/python
# Makeshift remote shell telegram bot
# it can also store files sent to it and can send files to the user thru /get

import subprocess
import socket
import logging
import os
import json
import glob
import unicodedata
import re
import getpass
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# comment the following line if you want to log all http requests
logging.getLogger("httpx").setLevel(logging.WARNING)

# (lazy) config fix
try:
    bot_download_limit
    tags_file
except NameError:
    bot_download_limit = 20970496
    tags_file = "tags.json"
try:
    testserver
except NameError:
    testserver = False

# create access_log if not found
if not os.path.exists(access_log):
    with open(access_log, 'w') as f:
        f.write(
            "#######################\n"
            "UNAUTHORIZED ACTION LOG\n"
            "#######################"
        )
    logging.info("Created access_log file.")

# check if user is the owner
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

def load_index():
    if os.path.exists(file_index):
        with open(file_index, "r") as f:
            return json.load(f)
    return {}

def save_index(index):
    with open(file_index, "w") as f:
        json.dump(index, f, indent=2)

def load_tags():
    if os.path.exists(tags_file):
        with open(tags_file, "r") as f:
            return json.load(f)
    return []

def save_tags(tags):
    with open(tags_file, "w") as f:
        json.dump(tags, f, indent=2)

def add_file_to_index(file_id, filename, file_type, saved_path, file_size_MB):
    idx = load_index()
    idx[filename] = {
        "file_id": file_id,
        "file_type": file_type,
        "tags": [],
        "file_size": f"{file_size_MB}MB",
        "saved_path": saved_path,
        "date_saved": datetime.now().isoformat()
    }
    save_index(idx)
    logging.info(f"Added a {file_type} file to the index.")

def get_by_filename(filename):
    idx = load_index()
    return idx.get(filename)

def get_by_file_id(file_id):
    idx = load_index()
    for fname, entry in idx.items():
        if entry.get("file_id") == file_id:
            return fname, entry
    return None, None

def extract_file_info(message):
    
    filename = None
    file_type = None
    file_id = None
    file_size = None

    if message.photo:
        photo = message.photo[-1]
        filename = f"photo_{photo.file_unique_id}.jpg"
        file_type = "photo"
        file_id = photo.file_id
        file_size = photo.file_size
        file_unique_id = photo.file_unique_id
    elif message.video:
        video = message.video
        filename = video.file_name or f"video_{video.file_unique_id}.mp4"
        file_type = "video"
        file_id = video.file_id
        file_size = video.file_size
        file_unique_id = video.file_unique_id
    elif message.audio:
        audio = message.audio
        filename = audio.file_name or f"audio_{audio.file_unique_id}.mp3"
        file_type = "audio"
        file_id = audio.file_id
        file_size = audio.file_size
        file_unique_id = audio.file_unique_id
    elif message.voice:
        voice = message.voice
        filename = f"voice_{voice.file_unique_id}.ogg"
        file_type = "voice"
        file_id = voice.file_id
        file_size = voice.file_size
        file_unique_id = voice.file_unique_id
    elif message.animation:
        anim = message.animation
        filename = anim.file_name or f"animation_{anim.file_unique_id}.mp4"
        file_type = "animation"
        file_id = anim.file_id
        file_size = anim.file_size
        file_unique_id = anim.file_unique_id
    elif message.sticker:
        sticker = message.sticker
        if getattr(sticker, "is_video", False):
            filename = f"sticker_{sticker.file_unique_id}.webm"
        elif sticker.is_animated:
            filename = f"sticker_{sticker.file_unique_id}.tgs"
        else:
            filename = f"sticker_{sticker.file_unique_id}.webp"
        file_type = "sticker"
        file_id = sticker.file_id
        file_size = sticker.file_size
        file_unique_id = sticker.file_unique_id
    elif message.document:
        doc = message.document
        filename = doc.file_name
        file_type = "document"
        file_id = doc.file_id
        file_size = doc.file_size
        file_unique_id = doc.file_unique_id

    return filename, file_type, file_id, file_size, file_unique_id

def normalize_filename(filename: str, max_length: int = 255) -> str:
    filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')     # Normalize Unicode characters (e.g., smart quotes, accents)    
    filename = ''.join(c for c in filename if c.isprintable())                                       # Remove control characters and problematic Unicode remnants
    filename = re.sub(r'[\s\-]+', '_', filename)                                                     # Replace spaces and repeated dashes/underscores with a single underscore
    filename = re.sub(rf'[^\w{re.escape("._-")}]', '', filename)                                     # Remove characters that are generally unsafe in filenames
    filename = filename.strip("._")                                                                  # Remove leading/trailing underscores or dots

    # Enforce maximum filename length
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext

    # Fallback if filename is empty after cleanup
    return filename or "file"

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
    logging.info("Windows detected. Checking for fastfetch command...")
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

###########################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/start"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="WARNING: Unknown user detected. \nAccess revoked. \n\nThis attempt has been logged.")
        return
    logging.info("Command /start used.")

    keyboard = [
        [InlineKeyboardButton("📡 Get IP Info", callback_data='get_ip')],
        [InlineKeyboardButton("🖥 Neofetch", callback_data='run_neofetch')],
        [InlineKeyboardButton("📄 Print Access Log", callback_data='print_log')],
        [InlineKeyboardButton("📂 Manage Uploaded Files", callback_data='manage_files')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(start_message, reply_markup=reply_markup, parse_mode='HTML')

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

        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='go_back')]]
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
                pub_ip = subprocess.run(['curl', '-s', ip_url], capture_output=True, text=True, timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nLocal IP Address:\n<code>{local_ip.strip()}</code>" or "No output from curl or socket connection."
            elif win:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("9.9.9.9", 80))       # no actual connection made
                local_ip = s.getsockname()[0]
                s.close()

                # get public IP address
                pub_ip = subprocess.run(f"$ProgressPreference = 'SilentlyContinue'; (Invoke-WebRequest '{ip_url}').Content", shell=True, capture_output=True, text=True, executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nLocal IP Address:\n<code>{local_ip.strip()}</code>" or "No output from curl or socket connection."
            else:
                # get interfaces and addresses
                ip_cmd = "ip -o -4 a | awk '$2 != \"lo\" {print $2, $4}'"
                interfaces = subprocess.run(ip_cmd, shell=True, capture_output=True, text=True)

                # get public IP address
                pub_ip = subprocess.run(['curl', '-s', ip_url], capture_output=True, text=True, timeout=10)
                output = f"Public IP Address:\n<code>{pub_ip.stdout.strip()}</code>\n\n\nDevice Interfaces:\n<code>{interfaces.stdout.strip()}</code>" or "No output from curl or ip addr commands."
        except Exception as e:
            output = f"Error: {str(e)}"
        
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=output, reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'print_log':
        with open(access_log, 'r') as file:
            content = file.read()

        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=f"{content}", reply_markup=reply_markup, parse_mode='HTML')

    elif query.data == 'go_back':
        # recreate the original menu
        keyboard = [
            [InlineKeyboardButton("📡 Get IP Info", callback_data='get_ip')],
            [InlineKeyboardButton("🖥 Neofetch", callback_data='run_neofetch')],
            [InlineKeyboardButton("📄 Print Access Log", callback_data='print_log')],
            [InlineKeyboardButton("📂 Manage Uploaded Files", callback_data='manage_files')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=start_message, reply_markup=reply_markup, parse_mode='HTML')

async def manage_files_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, send: bool = False):
    """
    Shows information about the upload index.
    Can be invoked as /manage or via the button menu.
    """
    if not is_owner(update, "/manage"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    logging.info("Command /manage used.")
    query = update.callback_query
    if query:
        await query.answer()
        send_func = query.edit_message_text
    else:
        send_func = update.message.reply_text

    idx = load_index()

    total_files = len(idx)
    total_downloaded = 0
    type_counts = {}
    total_storage_MB = 0.0
    for fname, entry in idx.items():
        t = entry.get("file_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        # only count files that are not .tglink (placeholders)
        if not fname.endswith(".tglink"):
            # entry["file_size"] is a string like "3.2MB"
            total_downloaded += 1
            size_str = entry.get("file_size", "0MB")
            try:
                total_storage_MB += float(size_str.replace("MB", ""))
            except Exception:
                pass
    lines = [
        f"Total files in index: <b>{total_files}</b>",
        f"Indexed files on disk: <b>{total_downloaded}</b>",
        "File types indexed:"
    ]
    for t, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  <code>{t}</code>: <b>{count}</b>")
    lines.append(f"\nStorage used: <b>{total_storage_MB:.2f} MB</b>")
    
    keyboard = [
        [InlineKeyboardButton("🗄 View uploaded files (/get)", callback_data='get_file')],
        [InlineKeyboardButton("🗑 Select files to remove (/remove)", callback_data='remove_file')],
        [InlineKeyboardButton("◀️ Back", callback_data='go_back'), InlineKeyboardButton("🏷️ Manage Media Tags", callback_data='manage_tags')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if send:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines), reply_markup=reply_markup, parse_mode='HTML')
    else:
        await send_func(text="\n".join(lines), reply_markup=reply_markup, parse_mode='HTML')

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
            logging.info(f"Shell command executed: {command}")
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error: {str(e)}")

async def send_file(context, chat_id, file_entry, file_path, filename):
    sent = False
    if file_entry:
        file_id = file_entry["file_id"]
        file_type = file_entry["file_type"]
        try:
            if file_type == "document":
                await context.bot.send_document(chat_id=chat_id, document=file_id)
            elif file_type == "photo":
                await context.bot.send_photo(chat_id=chat_id, photo=file_id, has_spoiler=testserver)
            elif file_type == "video":
                await context.bot.send_video(chat_id=chat_id, video=file_id, has_spoiler=testserver)
            elif file_type == "audio":
                await context.bot.send_audio(chat_id=chat_id, audio=file_id)
            elif file_type == "voice":
                await context.bot.send_voice(chat_id=chat_id, voice=file_id)
            elif file_type == "animation":
                await context.bot.send_animation(chat_id=chat_id, animation=file_id, has_spoiler=testserver)
            elif file_type == "sticker":
                await context.bot.send_sticker(chat_id=chat_id, sticker=file_id)
            sent = True
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Sending by file ID failed for {filename}, sending from disk. Error: {e}")
    if not sent:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            with open(file_path, "rb") as f:
                if file_entry:
                    if file_type == "photo":
                        await context.bot.send_photo(chat_id=chat_id, photo=f, has_spoiler=testserver)
                    elif file_type == "video":
                        await context.bot.send_video(chat_id=chat_id, video=f, has_spoiler=testserver)
                    elif file_type == "audio":
                        await context.bot.send_audio(chat_id=chat_id, audio=f)
                    elif file_type == "voice":
                        await context.bot.send_voice(chat_id=chat_id, voice=f)
                    elif file_type == "animation":
                        await context.bot.send_animation(chat_id=chat_id, animation=f, has_spoiler=testserver)
                    elif file_type == "sticker":
                        await context.bot.send_sticker(chat_id=chat_id, sticker=f)
                    else:
                        await context.bot.send_document(chat_id=chat_id, document=f)
                else:
                    await context.bot.send_document(chat_id=chat_id, document=f)
        except Exception as e:
            await context.bot.send_message(chat_id=chat_id, text=f"Failed to send file {filename}: {e}")
    return sent

async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/get"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    query = update.callback_query
    if query:
        await query.answer()
    if not context.args:
        logging.info(f"Command /get used.")
    else:
        logging.info(f"Command /get used: {context.args}")

    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="/get usage: \n<code>/get path/to/file.txt</code> \nGet everything in a folder:\n<code>/get path/to/dir/</code> \nBy type: <code>/get -t video</code> \n\nUsing without arguments shows everything in the upload folder.", parse_mode='HTML')
        if not testserver:
            file_path = os.path.normpath(upload_folder)
        else:
            return
    elif context.args[0] and context.args[0] == "-t":
        if len(context.args) < 2:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Specify a file type: \n<code>/get -t video</code> \n\nAll file types: \n<code>photo, video, audio, voice, document, animation, sticker</code>", parse_mode='HTML')
            return
        query_type = context.args[1]
        idx = load_index()
        sent_num = 0
        for fname, entry in idx.items():
            if entry.get("file_type") == query_type:
                file_entry = get_by_filename(fname)
                fpath =  file_entry["saved_path"]
                sent = await send_file(context, chat_id, file_entry, fpath, fname)
                if file_entry and sent:
                    sent_num += 1
        if sent_num > 0:
            await context.bot.send_message(chat_id=chat_id, text=f"Sent <code>{sent_num}</code> files by type: <code>{query_type}</code>", parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"No files by type <code>{query_type}</code> were found in the index.", parse_mode='HTML')
            return
    else:
        file_path = os.path.normpath(" ".join(context.args))

    # wildcard support
    if any(char in file_path for char in ['*', '?', '[']):
        matched_files = [f for f in glob.glob(file_path) if os.path.isfile(f)]
        if not matched_files:
            await context.bot.send_message(chat_id=chat_id, text="No files match that pattern.")
            return

        indexed = 0
        await context.bot.send_message(chat_id=chat_id, text=f"Sending <code>{len(matched_files)}</code> files matching pattern: \n<code>{file_path}</code>", parse_mode='HTML')
        for fpath in matched_files:
            filename = os.path.basename(fpath)
            file_entry = get_by_filename(filename)
            sent = await send_file(context, chat_id, file_entry, fpath, filename)
            if file_entry and sent:
                indexed += 1
        await context.bot.send_message(chat_id=chat_id, text=f"<code>{indexed}/{len(matched_files)}</code> files were in the upload index.", parse_mode='HTML')
        return

    # directory support
    if os.path.isdir(file_path):
        file_list = [
            os.path.join(file_path, f)
            for f in os.listdir(file_path)
            if os.path.isfile(os.path.join(file_path, f))
        ]
        if not file_list:
            await context.bot.send_message(chat_id=chat_id, text=f"Directory <code>{file_path}</code> is empty.", parse_mode='HTML')
            return

        indexed = 0
        await context.bot.send_message(chat_id=chat_id, text=f"Sending <code>{len(file_list)}</code> files from directory: \n<code>{file_path}</code>", parse_mode='HTML')
        for fpath in file_list:
            filename = os.path.basename(fpath)
            file_entry = get_by_filename(filename)
            sent = await send_file(context, chat_id, file_entry, fpath, filename)
            if file_entry and sent:
                indexed += 1
        await context.bot.send_message(chat_id=chat_id, text=f"<code>{indexed}/{len(file_list)}</code> files were in the upload index.", parse_mode='HTML')
        return

    # single file support
    elif os.path.isfile(file_path):
        filename = os.path.basename(file_path)
        file_entry = get_by_filename(filename)
        if file_entry:
            msg = await context.bot.send_message(chat_id=chat_id, text="File found in index, sending...")
            sent = await send_file(context, chat_id, file_entry, file_path, filename)
            await context.bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        else:
            await send_file(context, chat_id, None, file_path, filename)
        return

    else:
        await context.bot.send_message(chat_id=chat_id, text="File or directory not found.")
        return

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "Sent file"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    
    filename, file_type, file_id, file_size, file_unique_id = extract_file_info(update.message)
    file_info = None

    idx = load_index()
    if context.user_data.get('remove_next'):
        # remove by file ID first
        to_remove = None
        for fname, entry in idx.items():
            if entry.get("file_id") == file_id:
                to_remove = fname
                break
        if to_remove:
            entry = idx.pop(to_remove)
            save_index(idx)
            try:
                if os.path.exists(entry["saved_path"]):
                    os.remove(entry["saved_path"])
                msg = f"File <code>{to_remove}</code> removed from index and disk (by file ID)."
            except Exception as e:
                msg = f"Removed from index, but failed to delete file: \n{e}"
        else:
            msg = "File not found in index (by file ID)."
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop deleting", callback_data='stop_deleting')]]))
        return

    elif filename and file_id and file_type and file_size is not None:
        if filename in idx or any(entry["file_id"] == file_id for entry in idx.values()):
            if any(entry["file_id"] == file_id for entry in idx.values()):
                await context.bot.send_message(chat_id=update.effective_chat.id, text=f"File <code>{filename}</code> was already in the index.", parse_mode='HTML')
                return
            else:
                filename = normalize_filename(filename)
                filename = f"{file_unique_id}_{filename}"
        file_size_MB = round(file_size / 1000000, 2)
        download_limit_MB = round(bot_download_limit / 1000000, 2)
        filename = normalize_filename(filename)

        if file_size > bot_download_limit:
            # too large for Telegram bot download, create .tglink placeholder
            save_path = os.path.join(upload_folder, f"{filename}.tglink")
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            placeholder = {
                "filename": filename,
                "file_id": file_id,
                "file_type": file_type,
                "file_size": f"{file_size_MB}MB",
                "download_limit": f"{download_limit_MB}MB",
                "date_saved": datetime.now().isoformat(),
                "note": "File size exceeds Telegram bot download limit. This placeholder is necessary for the file to be sent properly. Data in this file is for your reference, as it is nearly a copy of the index entry."
            }

            with open(save_path, "w") as f:
                json.dump(placeholder, f, indent=2)
            add_file_to_index(file_id, f"{filename}.tglink", file_type, save_path, file_size_MB)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"File is too large for Telegram bot download. Indexed and placeholder created:\n<code>{save_path}</code>", parse_mode='HTML')
            return

        # report error if file is still too large
        try: 
            file_info = await context.bot.get_file(file_id)
            save_path = os.path.join(upload_folder, filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="Saving file...")
            await file_info.download_to_drive(save_path)
            add_file_to_index(file_id, filename, file_type, save_path, file_size_MB)
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"{file_type.capitalize()} saved: \n<code>{save_path}</code>", parse_mode='HTML')
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Error downloading file: \n<code>{str(e)}</code> \n\nFile type: {file_type} \nDownload limit: {download_limit_MB}MB \nFile size: {file_size_MB}MB \nFile info: {file_info}", parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The file you sent is not supported for upload.")


### file tagging functionality
async def manage_tags_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, send=False):
    """
    Manages file tagging of indexed files.
    """
    if not is_owner(update, "Tag management menu"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    # Handles displaying the main tag management menu
    query = update.callback_query
    if query:
        await query.answer()
        send_func = query.edit_message_text
    else:
        send_func = update.message.reply_text

    tags = load_tags()
    idx = load_index()
    if tags:
        tag_counts = {tag: 0 for tag in tags}
        for entry in idx.values():
            for tag in entry.get("tags", []):
                if tag in tag_counts:
                    tag_counts[tag] += 1
        tag_list = "\n".join(f"<code>{tag}</code>: <b>{tag_counts[tag]}</b>" for tag in tags)
    else:
        tag_list = "No tags yet."
    keyboard = [
        [InlineKeyboardButton("🔍 View Tagged", callback_data='view_tag'), InlineKeyboardButton("📎 Tag Media", callback_data='tag_media')],
        [InlineKeyboardButton("➕ Create Tag", callback_data='add_tag'), InlineKeyboardButton("🏷️ Untag Media", callback_data='untag_media')],
        [InlineKeyboardButton("◀️ Back", callback_data='manage_files'), InlineKeyboardButton("🗑️ Delete Tag", callback_data='delete_tag')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if send:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Available tags:\n{tag_list}", reply_markup=reply_markup, parse_mode='HTML')
    else:
        await send_func(text=f"Available tags:\n{tag_list}", reply_markup=reply_markup, parse_mode='HTML')

async def add_tag_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_new_tag'] = True
    await query.edit_message_text("Send me the tag name you want to add:")

async def add_tag_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_new_tag'):
        tag = update.message.text.strip()
        tags = load_tags()
        if tag in tags:
            await update.message.reply_text("Tag already exists.")
        else:
            tags.append(tag)
            save_tags(tags)
            await update.message.reply_text(f"Tag <code>{tag}</code> added.", parse_mode='HTML')
        context.user_data['awaiting_new_tag'] = False
        # Show tag menu again
        await manage_tags_menu(update, context)

async def delete_tag_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tags = load_tags()
    if not tags:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No tags to delete.")
        return
    keyboard = [[InlineKeyboardButton(tag, callback_data=f'del_tag_{tag}')] for tag in tags]
    keyboard.append([InlineKeyboardButton("Back", callback_data='manage_tags')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Pick a tag to delete:", reply_markup=reply_markup)

async def delete_tag_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tag = query.data.replace('del_tag_', '')
    tags = load_tags()
    if tag in tags:
        tags.remove(tag)
        save_tags(tags)
        await query.edit_message_text(f"Tag <code>{tag}</code> deleted.", parse_mode='HTML')
    else:
        await query.edit_message_text("Tag not found.")
    # Show menu again
    await manage_tags_menu(update, context)

async def tag_media_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tags = load_tags()
    if not tags:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You don't have any available tags, create one first.")
        return
    context.user_data['tag_next_media'] = True
    context.user_data['pending_tag_media_batch'] = []
    keyboard = [[InlineKeyboardButton("Cancel", callback_data='tag_media_cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Forward the files you want to tag.", reply_markup=reply_markup)

async def tag_media_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('tag_next_media'):
        return

    msg = update.message
    filename, file_type, file_id, file_size, file_unique_id = extract_file_info(msg)
    fname, entry = get_by_file_id(file_id)

    if not entry:
        context.user_data['tag_next_media'] = False
        context.user_data['pending_tag_media_batch'] = []
        await msg.reply_text("This media is not in the index. Tagging canceled.")
        return

    # Add to batch, but avoid duplicates
    batch = context.user_data.setdefault('pending_tag_media_batch', [])
    if not any(item['file_id'] == file_id for item in batch):
        batch.append({"filename": fname, "file_id": file_id})

    # Prompt for tag after each file, or allow more files to be forwarded
    tags = load_tags()
    keyboard = [[InlineKeyboardButton(tag, callback_data=f'tag_media_apply_{tag}')] for tag in tags]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data='tag_media_cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text("Pick a tag to apply to these forwarded files, or keep forwarding files to add to the batch.", reply_markup=reply_markup)

async def tag_media_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tag = query.data.replace('tag_media_apply_', '')
    batch = context.user_data.get('pending_tag_media_batch', [])
    if not batch:
        await query.edit_message_text("No files to tag.")
        context.user_data['tag_next_media'] = False
        return

    idx = load_index()
    tagged = []
    for item in batch:
        file_id = item['file_id']
        # Always find by file_id
        for fname, entry in idx.items():
            if entry.get("file_id") == file_id:
                if "tags" not in entry:
                    entry["tags"] = []
                if tag not in entry["tags"]:
                    entry["tags"].append(tag)
                tagged.append(fname)
                break
    save_index(idx)
    context.user_data['pending_tag_media_batch'] = []
    context.user_data['tag_next_media'] = False
    if tagged:
        await query.edit_message_text(f"Tagged <code>{len(tagged)}</code> files as <code>{tag}</code>:\n" + "\n".join(f"<code>{fname}</code>" for fname in tagged), parse_mode='HTML')
        await manage_tags_menu(update, context, send=True)
    else:
        await query.edit_message_text("No files were tagged.")

async def tag_media_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['pending_tag_media_batch'] = []
    context.user_data['tag_next_media'] = False
    await query.edit_message_text("Tagging mode canceled.")
    await manage_tags_menu(update, context)

async def untag_media_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['untag_next_media'] = True
    keyboard = [[InlineKeyboardButton("Cancel", callback_data='untag_media_cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Forward the file you want to untag.", reply_markup=reply_markup)

async def untag_media_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('untag_next_media'):
        return
    msg = update.message
    filename, file_type, file_id, file_size, file_unique_id = extract_file_info(msg)
    filename, entry = get_by_file_id(file_id)
    if not entry:
        context.user_data['untag_next_media'] = False
        await msg.reply_text("This media is not in the index. Untagging canceled.")
        return
    tags = entry.get("tags", [])
    if not tags:
        context.user_data['untag_next_media'] = False
        await msg.reply_text("This file has no tags to remove. Untagging canceled.")
        await manage_tags_menu(update, context, send=True)
        return
    # Save info for callback
    context.user_data['pending_untag_media'] = {"filename": filename, "file_id": file_id}
    keyboard = [[InlineKeyboardButton(tag, callback_data=f'untag_media_apply_{tag}')] for tag in tags]
    keyboard.append([InlineKeyboardButton("Cancel", callback_data='untag_media_cancel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text("Pick a tag to remove from this file:", reply_markup=reply_markup)
    context.user_data['untag_next_media'] = False

async def untag_media_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tag = query.data.replace('untag_media_apply_', '', 1)
    pending = context.user_data.get('pending_untag_media')
    if not pending:
        await query.edit_message_text("No media to untag.")
        return
    file_id = pending['file_id']
    idx = load_index()
    found = False

    # Find the entry by file_id
    for fname, entry in idx.items():
        if entry.get("file_id") == file_id:
            if "tags" in entry and tag in entry["tags"]:
                entry["tags"].remove(tag)
                save_index(idx)
                await query.edit_message_text(f"Tag <code>{tag}</code> removed from <code>{fname}</code>.", parse_mode='HTML')
            else:
                await query.edit_message_text("Tag not found on this file.")
            found = True
            break

    if not found:
        await query.edit_message_text("File not found in index for untagging.")

    context.user_data['pending_untag_media'] = None
    await manage_tags_menu(update, context, send=True)

async def untag_media_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['pending_untag_media'] = None
    context.user_data['untag_next_media'] = False
    await query.edit_message_text("Untagging canceled.")
    await manage_tags_menu(update, context)

async def view_tag_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tags = load_tags()  # This should return a list of tag strings
    if not tags:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No tags to view.")
        return
    keyboard = [[InlineKeyboardButton(tag, callback_data=f'view_tag_{tag}')] for tag in tags]
    keyboard.append([InlineKeyboardButton("Back", callback_data='manage_tags')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Select a tag to view files:", reply_markup=reply_markup)

async def view_tag_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tag = query.data.replace('view_tag_', '', 1)
    idx = load_index()
    matched_files = [
        (fname, entry)
        for fname, entry in idx.items()
        if tag in entry.get("tags", [])
    ]
    if not matched_files:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"No files found with tag <code>{tag}</code>.", parse_mode='HTML')
        await manage_tags_menu(update, context)
        return
    chat_id = query.message.chat.id
    for fname, entry in matched_files:
        file_path = entry.get("saved_path")
        await send_file(context, chat_id, entry, file_path, fname)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sent <code>{len(matched_files)}</code> files with tag <code>{tag}</code>.", parse_mode='HTML')
    await manage_tags_menu(update, context, send=True)


async def remove_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "/remove"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    query = update.callback_query
    if query:
        await query.answer()
    if context.args and " ".join(context.args) == "-c":
        await context.bot.send_message(chat_id=update.effective_chat.id, text="File removal canceled.")
        context.user_data['remove_next'] = False
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Forward items to be deleted from index and disk. Tap 'Stop deleting' to end removal mode.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop deleting", callback_data='stop_deleting')]])
    )
    context.user_data['remove_next'] = True

async def stop_deleting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['remove_next'] = False
    await query.answer()
    await query.edit_message_text("Stopped deletion mode.")

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if waiting for tag input
    if context.user_data.get('awaiting_new_tag'):
        await add_tag_receive(update, context)
        return
    # Otherwise treat as a shell command
    await handle_shell_commands(update, context)

async def media_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('tag_next_media'):
        await tag_media_receive(update, context)
        return
    if context.user_data.get('untag_next_media'):
        await untag_media_receive(update, context)
        return
    # Default: handle as a normal upload
    await handle_upload(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update, "Invalid bot command"):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Access denied.")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid bot command. \nTry /start or /get")


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

    # only log if something actually changed
    if start_message != original:
        logging.info("Replaced placholders in the start message.")


if __name__ == '__main__':
    app = ApplicationBuilder().token(bot_token).post_init(parse_start_message).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('manage', manage_files_menu))
    app.add_handler(CommandHandler('get', get_file))
    app.add_handler(CommandHandler('remove', remove_file))

    # handlers for the manage files menu
    app.add_handler(CallbackQueryHandler(manage_files_menu, pattern="^manage_files$"))
    app.add_handler(CallbackQueryHandler(get_file, pattern="^get_file$"))
    app.add_handler(CallbackQueryHandler(remove_file, pattern="^remove_file$"))
    app.add_handler(CallbackQueryHandler(stop_deleting_callback, pattern="stop_deleting"))

    # handlers for the manage tagging menu
    app.add_handler(CallbackQueryHandler(manage_tags_menu, pattern="manage_tags"))
    app.add_handler(CallbackQueryHandler(add_tag_prompt, pattern="add_tag"))
    app.add_handler(CallbackQueryHandler(delete_tag_prompt, pattern="^delete_tag"))
    app.add_handler(CallbackQueryHandler(delete_tag_confirm, pattern="^del_tag_"))
    app.add_handler(CallbackQueryHandler(tag_media_apply, pattern="^tag_media_apply_"))
    app.add_handler(CallbackQueryHandler(tag_media_cancel, pattern="^tag_media_cancel"))
    app.add_handler(CallbackQueryHandler(tag_media_prompt, pattern="^tag_media"))
    app.add_handler(CallbackQueryHandler(view_tag_files, pattern="^view_tag_"))
    app.add_handler(CallbackQueryHandler(view_tag_prompt, pattern="^view_tag$"))
    app.add_handler(CallbackQueryHandler(untag_media_apply, pattern="^untag_media_apply_"))
    app.add_handler(CallbackQueryHandler(untag_media_cancel, pattern="^untag_media_cancel"))
    app.add_handler(CallbackQueryHandler(untag_media_prompt, pattern="untag_media"))

    # handle callbacks not already handled
    app.add_handler(CallbackQueryHandler(button_handler))

    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # route text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # route most media
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE | filters.ANIMATION | filters.Sticker.ALL, media_router))


    app.run_polling()


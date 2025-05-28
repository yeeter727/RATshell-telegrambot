# RAT-telegrambot-for-linux
A very simple remote access tool using the `python-telegram-bot` module to execute shell commands.

<img src="src/example.png" width="400"/>

## Setup
To run the bot directly (`python bot.py`), all you should need is a working Linux system (it should also work in Termux) and the `python-telegram-bot` module:
```
pip install python-telegram-bot

sudo apt install neofetch curl    # if you don't have these
```
**Remember to add your Telegram user ID and bot token to `tg.conf`!**
 
  \
***Optional:*** \
Reccomended command list to send to [BotFather](https://t.me/botfather):
```
start - open start menu
v - view archived media
r - remove next media
x - enter shell 
q - exit shell
```

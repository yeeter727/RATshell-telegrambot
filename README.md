# RAT-telegrambot-for-linux
A very simple remote access tool using the `python-telegram-bot` Python module to execute shell commands.

<img src="https://github.com/yeeter727/RAT-telegrambot-for-linux/blob/16b78441b023a84187bade63a72f784dc795b1e9/src/example.png" width="400"/>

### Setup
To run the bot directly (`python bot.py`), all you should need is a working Linux system (it should also work in Termux) and the `python-telegram-bot` module:
```
pip install python-telegram-bot
```
If not already installed, neofetch and curl: `sudo apt install neofetch curl`
Remember to add your Telegram user ID and bot token to `tg.conf` !

#### Optional: 
Reccomended command list to send to BotFather:
```
start - open start menu
v - view archived media
r - remove next media
x - enter shell 
q - exit shell
```

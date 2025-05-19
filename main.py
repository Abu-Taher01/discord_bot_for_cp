from bot import bot, TOKEN
from keep_alive import keep_alive

if __name__ == "__main__":
    keep_alive()  # Start the web server to keep the bot alive
    bot.run(TOKEN)  # Run the bot 
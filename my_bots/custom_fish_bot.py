from telegram.ext import CommandHandler
from telegram_bot_plug import Bot


class TheFishBot(Bot):
    def __init__(self, dp):
        super().__init__(dp)  # This must always be called first!

        # Add a single handler handling when people type /fish to the bot
        self.add_handler(CommandHandler("fish", self.handle_fish_command))

    def handle_fish_command(self, update, context):
        # Send the user a message
        update.message.reply_text("You asked for fish! Here you go: 🐟🐟🐟")

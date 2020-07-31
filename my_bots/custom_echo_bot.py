from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram_bot_plug import Bot


class AnotherCustomBot(Bot):
    def __init__(self, dp):
        super().__init__(dp)  # This must always be called first!

        self.wants_echo = False  # Keeps track of if the user has typed the /start command to us

        handlers = [
            CommandHandler("echo", self.handle_echo_command),
            MessageHandler(Filters.text & ~Filters.command, self.handle_messages),
        ]
        self.add_handlers(handlers)

    def handle_echo_command(self, update, context):
        # User has sent us /echo, meaning that he wants echoed his text from now on
        self.wants_echo = True
        update.message.reply_text("From now on I am going to be anoying")

    def handle_messages(self, update, context):
        if self.wants_echo:
            update.message.reply_text("I like to repeat you: " + update.message.text)

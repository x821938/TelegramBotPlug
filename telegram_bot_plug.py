import glob
import re
import importlib
import logging
import configparser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from telegram.ext import Updater

CONFIG_FILE = "config.ini"


class Bot:
    """ All custom bots should inherit from this class. The first thing they should do is call
    The this constructor from their constructor: super().__init__(dispatcher)
    """

    def __init__(self, dp):
        self.dp = dp
        self.handlers = []

    def add_handler(self, handler):
        """ Adds a single telegram handler to telegram.

        Args:
            handler (telegram.ext.Handler): It could be eg CommandHandler or MessageHandler
        """
        if self.is_sane():
            logging.info(f"Adding handler: {handler}")
            self.handlers.append(handler)
            self.dp.add_handler(handler)

    def add_handlers(self, handlers):
        """ Adds multiple handlers to telegram

        Args:
            handlers (list): list of telegram.ext.Handler
        """
        for handler in handlers:
            self.add_handler(handler)

    def remove_handlers(self):
        """ Removes all previously added handlers for a custom bot. This is called when a bot is reloaded.
        """
        try:
            for handler in self.handlers:
                logging.info(f"Removing handler: {handler}")
                self.dp.remove_handler(handler)
        except:
            logging.error("Could not remove handlers")

    def is_sane(self):
        """ Before adding handlers, we make sure that our constructer has been called from the custom bot

        Returns:
            bool: True if our constructer has been called and we have a handler-list for the custom bot.
                  Otherwise returns Talse.
        """
        try:
            self.handlers
            return True
        except:
            logging.error("You didn't call 'super().__init__(dp)' in your constructor!")
            return False


class Botmaster:
    """ Controls all the custom bots (in the custom bot-directories)
    It's responsible for loading and reloading the bots from disk.
    """

    def __init__(self, bot_dir, dispatcher):
        self.dispatcher = dispatcher
        self.bot_dir = bot_dir

        # Here we keep track of all running bots. {filename: (importet_module, bot_instance), ...}
        self.bots = {}
        self.load_all_bots()

    def get_custom_bot_class(self, loaded_module):
        """ Searches a module for a class that is a subclass of our class "Bot".

        Args:
            loaded_module (module): A custom bot module that should contain a 'class custombot(Bot)'

        Returns:
            class: The class of the custom bot. This is the class thats later instanciated to make the bot
            running
        """
        for obj_name in loaded_module.__dict__:
            obj = loaded_module.__dict__[obj_name]
            try:
                if issubclass(obj, loaded_module.Bot) and obj_name != "Bot":
                    return obj
            except (TypeError, AttributeError):
                pass
        return None

    def get_custom_bot_instance(self, imported_module):
        """ Finds the class of the bot and creates an instance (Basically making it running)

        Args:
            imported_module (module): A loded module that contains the custom bot-class

        Returns:
            Bot: An instance of Bot->Custombot.
        """
        bot_class = self.get_custom_bot_class(imported_module)
        if bot_class:
            bot_instance = bot_class(self.dispatcher)
            logging.info(f"We created a bot instance of '{bot_instance}'")
            return bot_instance
        else:
            logging.warning(f"No bot class found. Please create an inherited class of 'Bot'!")
            return None

    def run_bot(self, bot_file_name):
        """ Runs a bot from a file. If the bot is not running, it's loaded for the first time. Otherwise
        it will be reloaded. An instance of the custom bot will be created (thereby making it running)

        Args:
            bot_file_name (str): Filename of the pythonfile that contains the custom bot class
        """
        bot = self.bots.get(bot_file_name)  # Fetch it from our "bot-database"

        if not bot:
            imported_module = self.load_bot(bot_file_name)
        else:
            imported_module = self.reload_bot(bot_file_name)

        if imported_module:
            bot_instance = self.get_custom_bot_instance(imported_module)
            self.bots[bot_file_name] = (imported_module, bot_instance)  # Store info about running bot

    def load_bot(self, bot_file_name):
        """ Imports the custom bot class from a custom file for the first time.

        Args:
            bot_file_name (str): Filename of the pythonfile that contains the custom bot class

        Returns:
            module: The loaded module/package. Or None if it could not be imported
        """
        logging.info(f"bot file '{bot_file_name}' is new. We are trying to load it.")
        bot_module_name = bot_file_name.split("\\")[-1].replace(".py", "")
        bot_full_module_name = self.bot_dir.replace("/", ".").replace("\\", ".") + "." + bot_module_name
        try:
            return importlib.import_module(bot_full_module_name)
        except:
            logging.exception(f"Could not load bot '{bot_file_name}'")
            return None

    def reload_bot(self, bot_file_name):
        """ If we have a bot in memory, it can be reloaded with this method

        Args:
            bot_file_name (str): Filename of the pythonfile that contains the custom bot class

        Returns:
            module: The reloaded module/package.
        """
        imported_module, custom_bot = self.bots[bot_file_name]
        try:
            custom_bot.remove_handlers()
        except:
            logging.exception(f"Could not remove handlers from bot'{bot_file_name}'")

        try:
            importlib.reload(imported_module)
            logging.info(f"Reloaded bot from file '{bot_file_name}'")
        except:
            logging.exception(f"Could not reload bot '{bot_file_name}'")

        return imported_module

    def load_all_bots(self):
        """ When the masterbot is started, it loads all custom bots and starts them
        """
        for file in glob.glob(f"{self.bot_dir}/*.py"):
            self.run_bot(file)


class Filewatcher:
    """ Checks directories on disk for changes and acts upon them.
    """

    def __init__(self, watch_dir, callback_on_modify):
        """ Set up watching handlers

        Args:
            watch_dir (str): The directory to watch for file-changes
            callback_on_modify (function): Method to call when a file changes
        """
        self.callback_on_modify = callback_on_modify

        event_handler = FileSystemEventHandler()
        event_handler.on_modified = self.on_modified_file

        self.observer = Observer()
        self.observer.schedule(event_handler, watch_dir)
        self.observer.start()

    def on_modified_file(self, event):
        """ Callback function from watchdog module. It makes sure that a python file has been modified
        and calls the callback function in this Filewatcher-class. (the one provided in constructor)

        Args:
            event (watchdog.events.FileModifiedEvent): All info about watchdogs event (filename etc)
        """
        filename = event.src_path
        if re.search(".py$", filename):
            logging.info(f"File '{filename}' has changed")
            self.callback_on_modify(filename)

    def __del__(self):
        self.observer.stop()
        self.observer.join()


class Config:
    """ Handles configuration from ini-file
    """

    def __init__(self, config_file):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

    def masterbots(self):
        """ Iterator that gives back token/folder settings for the custom bots.

        Yields:
            (token, folder): A token and a folder for each custom bot directory
        """
        for section in self.config.sections():
            if "bot" in section.lower():
                try:
                    token = self.config.get(section, "token")
                    folder = self.config.get(section, "folder")
                    logging.info(f"CFG: Added bot folder '{folder}' with token xxxxxx")
                    yield token, folder
                except configparser.NoOptionError:
                    logging.error(f"CFG: No token and folder setting for '{section}' in '{self.config_file}'")


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

    updaters = []

    cfg = Config(CONFIG_FILE)
    for token, folder in cfg.masterbots():
        updater = Updater(token, use_context=True)
        updaters.append(updater)
        dispatcher = updater.dispatcher
        updater.start_polling()

        # Set up a botmaster for each folder in the configuration
        bot_master = Botmaster(folder, dispatcher)
        filewatcher = Filewatcher(folder, bot_master.run_bot)

    updaters[0].idle()  # Wail forever or until ctrl-break

    for updater in updaters:
        updater.stop()

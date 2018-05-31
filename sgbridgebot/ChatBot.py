from telegram.ext import Updater, CommandHandler
from GameManager import GameManager
from CommandUtils import CommandUtils
from ChatHandler import ChatHandler

class ChatBot(object):

    '''
    Object that contains all elements of the chatbot. Interfaces between the
    python-telegram-bot API and the GameManager object with the help of several
    utilities.

    ATTRIBUTES
    manager(GameManager)
    updater(telegram.Updater)
    cmd_utils(CommandUtils)

    ARGS
    start(int): idle 0/1
    init_command_handlers()

    '''


    def __init__(self, token):
        self.updater = Updater(token)
        self.manager = GameManager()
        self.chat_handler = ChatHandler(self.updater.bot)
        self.cmd_utils = CommandUtils(self.manager, self.chat_handler)


    def start(self):
        self.init_command_handlers()
        self.updater.start_polling()
        self.updater.idle()


    def init_command_handlers(self):
        self.updater.dispatcher.add_handler(CommandHandler('hello', self.cmd_utils.hello))
        self.updater.dispatcher.add_handler(CommandHandler('join', self.cmd_utils.join))
        self.updater.dispatcher.add_handler(CommandHandler('leave', self.cmd_utils.leave))

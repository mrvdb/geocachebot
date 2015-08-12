# The responder object is the long running process that
# gets the POST requests from Telegram.
#
# The object responds only to POST requests on a predefined route. The
# responder is tied to a bot and takes a configparser object, which we
# assume has already been filled with the proper config earlier.

import logging
import random, string

from flask import Flask
from flask import request

from telegram.update import Update

class BotResponder(Flask):
    __routelen = 15

    def __init__(self, bot, config):
        # Instantiate flask
        super().__init__(__name__)

        # The route to which we respond is what we make of it
        self.route = '/' + bot.token

        # Get our hostname and register our webhook for the bot
        self.hostname = config.get('responder','host', fallback='localhost')
        bot.setWebhook( self.hostname + self.route)

        # Link it to the method that should handle the route
        self.add_url_rule(self.route, 'receiveJSON', self.receiveJSON, methods=['POST'])

    # what handles the updates?
    # FIXME: why have one? make a chain with addHandler / delHandler
    def setHandler(self, function):
        self.handler = function

    def receiveJSON(self):
        # Turn the JSON into a python thing
        update = Update.de_json(request.get_json(force=True))

        # Pass the update to the registered handler
        if self.handler:
            result = self.handler(update)

        # FIXME: What should we return here?
        # json or just ok, what does telegram have as convention?
        return 'ok'

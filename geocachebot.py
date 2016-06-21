#!/usr/bin/env python

'''A little geocache bot helper for Telegram'''


# System imports
import configparser
import logging
from string import Template

# Other packages
import pycaching
import telegram
from telegram.ext import (
    Updater,
    CommandHandler,
    RegexHandler)

# Pattern adapted from:
# http://eeecacher.blogspot.dk/2012/11/geocaching-gc-code-regex.htm
GC_PAT = '(GC[A-HJKMNPQRTV-Z0-9]{5}|GC[A-F0-9]{1,4}|GC[GHJKMNPQRTV-Z][A-HJKMNPQRTV-Z0-9]{3})'

# Pattern for TB codes seems to be TB plus 4 or 5 chars
TB_PAT = '(TB[A-Z0-9]{4,5})'


# Convert value rating to star rating
# # Example: 3.5 -> 🌑🌑🌑🌓
def StarRating(rate):
    FULL = '🌑'
    HALF = '🌓'
    FILL = '🌕'

    e = int(float(rate)) * FULL
    if (float(rate)-int(float(rate))) == 0.5:
        e += HALF
    return e.ljust(5, FILL)


# Read a template
def ReadTemplate(name, data=None):
    text = 'Error reading %s-template' % name
    try:
        with open(config.get("templates", name), "r") as f:
            text = f.read()
    except Exception as e:
        log.error(e)

    return Template(text).safe_substitute(data)


# Retrieve and format cache information
def GetCacheInfo(gc):
    # Lazy load the cache
    c = geo.get_cache(gc.upper())

    # Not using logged in feature for now
    if False and geo.get_logged_user():
        # We can retrieve more info, but the method degrades when the
        # user is not a premium member
        data = dict(
            type=c.type, code=c.wp, name=c.name,
            size=c.size, favorites=c.favorites,
            diff=StarRating(c.difficulty), terrain=StarRating(c.terrain),
            lat=c.location.latitude, long=c.location.longitude)
        template = "cache-full"
    else:
        # Load what we can as anonymous user
        c.load_quick()
        data = dict(
            type=c.type, code=c.wp, name=c.name,
            size=c.size, favorites=c.favorites,
            diff=StarRating(c.difficulty), terrain=StarRating(c.terrain))
        template = "cache-quick"

    # Render it
    msg = ReadTemplate(template, data)
    logging.debug(c)
    return msg


def GetTrackableInfo(tb):
    log.info("Getting info for : %s" % tb)

    try:
        t = geo.get_trackable(tb.upper())

        data = dict(
            type=t.type, code=t.tid, name=t.name,
            owner=t.owner, location=t.location)
        text = ReadTemplate("trackable", data)
    except pycaching.errors.NotLoggedInException:
        text = tb.upper() + ': for trackables, the bot needs to be logged in to geocaching.com'
    except Exception as e:
        text = tb.upper() + ': could not be found. Does it really exist?'

    return text


# Util function
def typing(bot, chat_id):
    bot.sendChatAction(chat_id=chat_id, action=telegram.ChatAction.TYPING)


def SimpleTemplate(bot, name, chat_id):
    text = ReadTemplate(name)
    typing(bot, chat_id)
    bot.sendMessage(
        chat_id=chat_id,
        text=text,
        parse_mode=telegram.ParseMode.MARKDOWN,
        disable_web_page_preview=True)


# Handle the start command
def StartCommand(bot, update):
    SimpleTemplate(bot, "start", update.message.chat_id)


# Handle the help command
def HelpCommand(bot, update):
    SimpleTemplate(bot, "help", update.message.chat_id)


# Handle detected GC code
def HandleGCs(bot, update, groups):
    gc = groups[0]
    log.info("GC code '%s' detected", gc)

    # Send either err msg or GC info
    typing(bot, update.message.chat_id)
    bot.sendMessage(
        chat_id=update.message.chat_id,
        text=GetCacheInfo(gc),
        parse_mode=telegram.ParseMode.MARKDOWN,
        disable_web_page_preview=True)


# Handle detected TC code
def HandleTBs(bot, update, groups):
    tb = groups[0]
    chat_id = update.message.chat_id
    log.info("TB code '%s' detected", tb)

    # Send either err msg or TB info
    typing(bot, chat_id)
    bot.sendMessage(
        chat_id=chat_id,
        text=GetTrackableInfo(tb),
        parse_mode=telegram.ParseMode.MARKDOWN,
        disable_web_page_preview=True)


def error(bot, update, error):
    logging.error('Update "%s" caused error "%s"' % (update, error))

if __name__ == '__main__':
    # Start logging as soon as possible
    loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel)
    log = logging.getLogger(__name__)
    log.info("Starting geocache bot implementation...")

    # Read in the configfile
    config = configparser.SafeConfigParser()
    config.read('geocachebot.cfg') or exit("FATAL: config file reading failed")

    # Connect to geocaching.com
    geo = pycaching.Geocaching()
    try:
        geo.login(
            config.get("geocaching", "user"),
            config.get("geocaching", "pass"))
        log.warning("Authenticated as %s" % config.get("geocaching", "user"))
    except Exception as e:
        log.warning(e)
        log.info("Continuing unauthenticated")

    # The updater is the main process
    updater = Updater(token=config.get('telegram', 'token'))
    dp = updater.dispatcher

    # Add our commands and message parser thingies
    # Commands
    dp.add_handler(CommandHandler('start', StartCommand))
    dp.add_handler(CommandHandler('help',  HelpCommand))

    # Message handlers
    dp.add_handler(RegexHandler(GC_PAT, HandleGCs, pass_groups=True), 0)
    dp.add_handler(RegexHandler(TB_PAT, HandleTBs, pass_groups=True), 1)

    # Error handler
    dp.add_error_handler(error)

    # Run it
    update_queue = updater.start_webhook(
        url_path=config.get('telegram', 'token'),
        port=config.getint('responder', 'port'),
        listen=config.get('responder', 'address'))

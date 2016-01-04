#!/usr/bin/env python

'''A little geocache bot helper for Telegram'''


# System imports
import re
import sys
import configparser
import logging
from string import Template

# Other packages
import pycaching
import telegram

# Our libs
from responder import BotResponder


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

    t = geo.get_trackable(tb.upper())

    data = dict(
        type=t.type, code=t.tid, name=t.name,
        owner=t.owner, location=t.location)
    return ReadTemplate("trackable", data)


# Util function
def typing(chat_id):
    bot.sendChatAction(chat_id=chat_id, action=telegram.ChatAction.TYPING)


def SimpleTemplate(name, chat_id):
    text = ReadTemplate(name)
    typing(chat_id)
    bot.sendMessage(
        chat_id=chat_id,
        text=text,
        parse_mode=telegram.ParseMode.MARKDOWN,
        disable_web_page_preview=True)


# Handle the start command
def StartCommand(update):
    SimpleTemplate("start", update.message.chat_id)


# Handle the help command
def HelpCommand(update):
    SimpleTemplate("help", update.message.chat_id)


# Match a regular expression in an update and return a formatted text
def MatchRegEx(update, pattern, formatCallback):
    matches = re.findall(
        pattern,
        update.message.text,
        re.IGNORECASE + re.UNICODE)

    for match in matches:
        typing(update.message.chat_id)
        try:
            # Send a formatted info message
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=formatCallback(match),
                parse_mode=telegram.ParseMode.MARKDOWN,
                disable_web_page_preview=True)
        except pycaching.errors.NotLoggedInException:
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=match.upper() + ': for trackables, the bot needs to be logged in to geocaching.com')
            pass
        except Exception as e:
            log.error(e)
            log.error(sys.exc_info()[0])
            bot.sendMessage(
                chat_id=update.message.chat_id,
                text=match.upper() + ': Ouch, load failed, are you sure it exists?')


def MatchGCs(update):
    # Pattern adapted from:
    # http://eeecacher.blogspot.dk/2012/11/geocaching-gc-code-regex.htm
    GC_PAT='(GC[A-HJKMNPQRTV-Z0-9]{5}|GC[A-F0-9]{1,4}|GC[GHJKMNPQRTV-Z][A-HJKMNPQRTV-Z0-9]{3})'

    MatchRegEx(update, GC_PAT, GetCacheInfo)


def MatchTBs(update):
    # Pattern for TB codes seems to be TB plus 4 or 5 chars
    TB_PAT = '(TB[A-Z0-9]{4,5})'

    MatchRegEx(update, TB_PAT, GetTrackableInfo)


# Process one update
def ProcessUpdate(update):
    assert(isinstance(update, telegram.Update))
    update_id = update['update_id']

    logging.info('Processing %d' % update_id)
    if (update.message.text):
        log.debug("Message received: %s", update.message.text)

        # Start command
        if update.message.text.startswith('/start'):
            log.debug("Command: start")
            StartCommand(update)
            return

        # Help command
        if update.message.text.startswith('/help'):
            log.debug("Command: help")
            HelpCommand(update)
            return

        # Test for presence of (multiple) GCxxxx patterns
        MatchGCs(update)

        # Test for presence of (multiple) TBxxxx patterns
        MatchTBs(update)


if __name__ == '__main__':
    # Start logging as soon as possible
    loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel)
    log = logging.getLogger(__name__)
    log.info("Starting geocache bot implementation...")

    # Read in the configfile
    config = configparser.SafeConfigParser()
    config.read('geocachebot.cfg') or exit("FATAL: config file reading failed")

    # Create our bot
    bot = telegram.Bot(config.get('telegram', 'token'))

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

    # The responder is our main process
    resp = BotResponder(bot, config)
    resp.setHandler(ProcessUpdate)

    # Run it
    resp.run(
        host=config.get('responder', 'address'),
        port=config.getint('responder', 'port'))

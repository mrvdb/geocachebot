#!/usr/bin/env python

'''A little geocache bot helper for Telegram'''

# System imports
import time, re, sys
import configparser
import logging
import pprint

# Other packages
import pycaching
import telegram

# Start logging as soon as possible
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
log = logging.getLogger(__name__)
log.info("Starting geocache bot implementation...")

# Debug
def dump(obj):
    pprint.pprint(vars(obj))

# Read in the configfile
config = configparser.SafeConfigParser()
config.read('geocachebot.cfg') or exit("FATAL: config file reading failed")

# Authorize to telegram
bot = telegram.Bot(config.get('telegram','token'))

# Connect to geocaching.com
log.info("Trying to authenticate,..")
geo = pycaching.Geocaching()
AUTHENTICATED=False
try:
    geo.login(config.get("geocaching","user"),config.get("geocaching","pass"))
    AUTHENTICATED=True
    log.warning("Authenticated as %s" % config.get("geocaching","user"))
except Exception as e:
    log.error(e)
    log.info("Continuing unauthenticated")

# This will be our global variable to keep the latest update_id when requesting
# for updates. It starts with the latest update_id if available.
try:
    LAST_UPDATE_ID = bot.getUpdates()[-1].update_id
except IndexError:
    LAST_UPDATE_ID = None

# Convert value rating to star rating
# # Example: 3.5 -> 🌑🌑🌑🌓🌕
def StarRating(rate):
    FULL='🌑'; HALF='🌓';FILL='🌕'

    e = int(float(rate)) * FULL
    if (float(rate)-int(float(rate))) == 0.5:
        e+=HALF
    return e.ljust(5,FILL)

# Read a template
def ReadTemplate(name):
    text = 'Error reading %s-template' % name
    try:
        with open(config.get("templates", name), "r") as f:
            text = f.read()
    except Exception as e:
        log.error(e)

    return text

# Retrieve and format cache information
def GetCacheInfo(gc):
    if AUTHENTICATED:
        # We can retrieve more info
        c=geo.load_cache(gc.upper())
        msg = ReadTemplate("cache-full") % (
            c.cache_type, c.wp, c.name,
            c.size, c.favorites,
            StarRating(c.difficulty), StarRating(c.terrain),
            c.location.latitude, c.location.longitude, c.wp)
    else:
        # Load what we can as anonymous user
        c = geo.load_cache_quick(gc.upper())
        msg = ReadTemplate("cache-quick") %(
            c.cache_type, c.wp, c.name,
            c.size, c.favorites,
            StarRating(c.difficulty), StarRating(c.terrain), c.wp)
    dump(c)

    return msg.encode('utf-8')

# Util function
def typing(chat_id):
    bot.sendChatAction(chat_id=chat_id, action=telegram.ChatAction.TYPING)

# Handle the help command
def HelpCommand(chat_id):
    text = ReadTemplate("help")
    typing(chat_id)
    bot.sendMessage(chat_id, text=text.encode('utf-8'), disable_web_page_preview=True)

# The bot handler
def handler():
    global LAST_UPDATE_ID

    # Request updates from last updated_id
    for update in bot.getUpdates(offset=LAST_UPDATE_ID):
        if LAST_UPDATE_ID < update.update_id:
            # chat_id is required to reply any message
            chat_id = update.message.chat_id

            if (update.message.text):
                log.debug("Message received: %s",update.message.text)

                # Help command
                if update.message.text.startswith('/help'):
                    log.debug("Command: help")
                    HelpCommand(chat_id)
                    LAST_UPDATE_ID = update.update_id
                    continue

                # Test for presence of (multiple) GCxxxx patterns
                # Pattern adapted from: http://eeecacher.blogspot.dk/2012/11/geocaching-gc-code-regex.htm
                GC_PAT = '(GC[A-HJKMNPQRTV-Z0-9]{5}|GC[A-F0-9]{1,4}|GC[GHJKMNPQRTV-Z][A-HJKMNPQRTV-Z0-9]{3})'

                matches = re.findall(GC_PAT, update.message.text, re.IGNORECASE+re.UNICODE)
                for gc in matches:
                    typing(chat_id)
                    try:
                        # Send a formatted cache info message
                        bot.sendMessage(chat_id=chat_id, text=GetCacheInfo(gc),disable_web_page_preview=True)
                    except Exception as e:
                        # Log it
                        log.error(e)
                        log.debug(sys.exc_info()[0])
                        # FIXME upstream: LoadError fails because of KeyError
                        bot.sendMessage(chat_id=chat_id, text=gc.upper() + ': load failed, non-existing cache?')

            # Update the last message seen, even if we don't handle it
            dump(update.message)
            LAST_UPDATE_ID = update.update_id

if __name__ == '__main__':
    while True:
        # Call the handler here
        handler()
        time.sleep(3)

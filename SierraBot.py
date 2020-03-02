#  Copyright (c) 2020 University of Cambridge Computer Laboratory Group Projects 2020 Team Sierra
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.

import argparse
import datetime
import json
import logging
import os
import random
import statistics
import sys
import time
import urllib.parse

import dateutil.parser
import pytimeparse.timeparse
import requests
import tweepy

argParser: argparse.ArgumentParser = argparse.ArgumentParser(
    description="Tweets about current conditions in study spaces",
    add_help=True
)

# Argument destination names
# Storing in a bunch of str constants to facilitate renaming
ATTR_WARNING_THRESHOLD: str = "warning_threshold"
ATTR_SAFETY_THRESHOLD: str = "safety_threshold"
ATTR_KEY_FILE: str = "key_file"
ATTR_TEMPLATE_FILE: str = "template_file"
ATTR_LOG_FILE: str = "log_file"
ATTR_LOG_LEVEL: str = "log_level"
ATTR_SUMMARY_URL: str = "summary_url"
ATTR_DAEMON: str = "daemon_period"
ATTR_AVERAGE_PERIOD: str = "averaging_period"
ATTR_WARNING_PERIOD: str = "warning_period"

argParser.add_argument(  # JSON endpoint
    dest=ATTR_SUMMARY_URL, type=str,
    help="URL of JSON summary", metavar="<summary url>"
)
argParser.add_argument(  # Warning threshold
    "-warn", "--warning-threshold", default=1_400, type=int, dest=ATTR_WARNING_THRESHOLD,
    help="CO\u2082 concentration (ppm) at which to post a warning", metavar="<max. concentration>"
)
argParser.add_argument(  # Safety notice threshold
    "-safe", "--safety-threshold", default=1_000, type=int, dest=ATTR_SAFETY_THRESHOLD,
    help="CO\u2082 concentration (ppm) at which to post a safety notice", metavar="<safe concentration>"
)
argParser.add_argument(  # Time threshold
    "--averaging-period", type=str, dest=ATTR_AVERAGE_PERIOD,
    help="Time period for which to consider conditions, if not provided conditions over all time are considered",
    metavar="<time threshold> "
)
argParser.add_argument(  # Warning repeat period
    "--warning-period", type=str, dest=ATTR_WARNING_PERIOD,
    help="How frequently to repeat warnings about rooms with detrimental conditions, "
         "defaults to <time threshold> if given, otherwise 90 minutes"
    , metavar="<warning period>"
)
argParser.add_argument(  # Twitter API key file
    "-keys", "--key-file", default="keys.json", type=str, dest=ATTR_KEY_FILE,
    # String as only want open while reading file
    help="Path to file containing Twitter API keys, defaults to keys.json", metavar="<key file>"
)
argParser.add_argument(  # Template file
    "-templates", "--template-file", default="templates.json", type=str, dest=ATTR_TEMPLATE_FILE,
    # String as only want open while reading file
    help="Path to file containing templates for tweets, defaults to templates.json", metavar="<template file>"
)
argParser.add_argument(  # Log file
    "-log", "--log-file", type=str, dest=ATTR_LOG_FILE, nargs='?', const=sys.argv[0] + ".log",
    # String as used as argument for FileHandler constructor
    help="Log to a file (" + sys.argv[0] + ".log by default), otherwise log messages go to stdout/stderr",
    metavar="log file"
)
argParser.add_argument(  # Logging level
    "--logging-level", default="WARNING", dest=ATTR_LOG_LEVEL,
    choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"],
    help="Minimum level of log messages, one of: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET",
    metavar="<logging level>"
)
# TODO Required for currentTime, making daemon-mode optional will require restructuring pretty much everything
argParser.add_argument(  # Check period
    "--daemon", dest=ATTR_DAEMON, required=True,
    help="Run as daemon, tweeting every <daemon period>", metavar="<daemon period>"
)

INVALID_FILE_SUFFIX: str = "_invalid"
TWEET_TIMESTAMP_FORMAT: str = "%a %d %b %H:%M"

# API key attributes
KEYS_API: str = "api"
KEYS_API_KEY: str = "key"
KEYS_API_SECRET: str = "secret"
KEYS_ACCESS: str = "access"
KEYS_ACCESS_TOKEN: str = "token"
KEYS_ACCESS_SECRET: str = "secret"
# Tweet templates attributes
TEMPLATE_WARNING: str = "warning"
TEMPLATE_WARNING_NEW: str = "new"
TEMPLATE_WARNING_CONTINUED: str = "continued"
TEMPLATE_SAFETY: str = "safety"
# Location attributes
LOC_ID: str = "locationID"
LOC_NAME: str = "name"
LOC_DATA: str = "data"
# Post attributes
POST_TIMESTAMP: str = "timestamp"
POST_TEMP: str = "temperature"
POST_PRESSURE: str = "pressure"
POST_HUMIDITY: str = "humidity"
POST_CO2: str = "co2"
POST_DEVICES: str = "devices"
POST_COUNT: str = "_count"
POST_IDX: str = "_idx"


def parse_timedelta(string: str) -> datetime.timedelta:
    secs = pytimeparse.timeparse.timeparse(string)
    if not secs:
        raise SyntaxError("Invalid time format: " + string)
    return datetime.timedelta(seconds=secs)


# Parse arguments
args: argparse.Namespace = argParser.parse_args()
CO2_WARNING_THRESHOLD: int = getattr(args, ATTR_WARNING_THRESHOLD)
CO2_SAFETY_THRESHOLD: int = getattr(args, ATTR_SAFETY_THRESHOLD)
# This shouldn't raise a KeyError as log level is set from list of valid choices
# noinspection PyProtectedMember
LOG_LEVEL: int = logging._nameToLevel[getattr(args, ATTR_LOG_LEVEL)]
LOG_FILE: str or None = getattr(args, ATTR_LOG_FILE)
KEY_FILE: str = getattr(args, ATTR_KEY_FILE)
TEMPLATE_FILE: str = getattr(args, ATTR_TEMPLATE_FILE)
SUMMARY_URL = getattr(args, ATTR_SUMMARY_URL)
DAEMON_PERIOD: datetime.timedelta or None = \
    parse_timedelta(getattr(args, ATTR_DAEMON)) if getattr(args, ATTR_DAEMON) else None
AVERAGING_PERIOD: datetime.timedelta or None = \
    parse_timedelta(getattr(args, ATTR_AVERAGE_PERIOD)) if getattr(args, ATTR_AVERAGE_PERIOD) else None
WARNING_PERIOD: datetime.timedelta = \
    parse_timedelta(getattr(args, ATTR_WARNING_PERIOD)) if getattr(args, ATTR_AVERAGE_PERIOD) \
        else AVERAGING_PERIOD if AVERAGING_PERIOD else datetime.timedelta(minutes=90)

# Logging
log: logging.Logger = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)
fmt: logging.Formatter = logging.Formatter(
    fmt='[%(asctime)-19s] %(levelname)8s: %(message)s'
)
if LOG_FILE:
    logFileHandler: logging.Handler = logging.FileHandler(LOG_FILE)
    logFileHandler.setFormatter(fmt)
    log.addHandler(logFileHandler)
else:
    # Info/debug output
    stdoutHandler: logging.Handler = logging.StreamHandler(sys.stdout)
    stdoutHandler.addFilter(lambda r: r.levelno <= logging.INFO)
    stdoutHandler.setFormatter(fmt)
    log.addHandler(stdoutHandler)
    # Warning/error/critical output
    stderrHandler: logging.Handler = logging.StreamHandler(sys.stderr)
    stderrHandler.addFilter(lambda r: r.levelno > logging.INFO)
    stdoutHandler.setFormatter(fmt)
    log.addHandler(stderrHandler)

# Some simple URL validation
parse_result = urllib.parse.urlparse(SUMMARY_URL)
try:
    assert any([parse_result.netloc, parse_result.path])
except AttributeError as e:
    log.critical("Invalid URL: ", SUMMARY_URL)
    exit(7)
del parse_result

templates: dict or None = None


def make_key_file():
    with open(KEY_FILE, 'x') as newKeyFile:
        json.dump(
            {
                KEYS_API: {
                    KEYS_API_KEY: '[API key]',
                    KEYS_API_SECRET: '[API secret key]'
                },
                KEYS_ACCESS: {
                    KEYS_ACCESS_TOKEN: '[Access token]',
                    KEYS_ACCESS_SECRET: '[Access token secret]'
                }
            },
            newKeyFile,
            indent=4
        )


def make_template_file():
    global templates
    templates = {
        TEMPLATE_WARNING: {
            TEMPLATE_WARNING_NEW: [
                "CO\u2082 concentration in {placeName:s} is above acceptable levels.",
            ],
            TEMPLATE_WARNING_CONTINUED: [
                "CO\u2082 concentration in {placeName:s} remains above acceptable levels.",
            ],
        },
        TEMPLATE_SAFETY: [
            "CO\u2082 concentration in {placeName:s} has returned to acceptable levels.",
        ],
    }
    with open(TEMPLATE_FILE, 'x') as newTemplateFile:
        json.dump(
            templates,
            newTemplateFile,
            indent=4
        )


def now():
    return datetime.datetime.now(tz=datetime.timezone.utc)


api: tweepy.API or None = None
# Access Twitter API
try:
    # Pull credentials from file
    with open(KEY_FILE, 'r') as templateFile:
        keys: dict = json.load(templateFile)
    log.debug("Read keys from: %s", KEY_FILE)
    # Authenticate to Twitter
    auth: tweepy.auth.OAuthHandler = tweepy.OAuthHandler(
        keys[KEYS_API][KEYS_API_KEY],
        keys[KEYS_API][KEYS_API_SECRET]
    )
    auth.set_access_token(
        keys[KEYS_ACCESS][KEYS_ACCESS_TOKEN],
        keys[KEYS_ACCESS][KEYS_ACCESS_SECRET]
    )
    # Create API object
    api = tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True
    )
    # Verify access
    user: tweepy.User = api.verify_credentials()
    if not user:
        log.critical("Twitter API error: no user found")
        exit(4)
    else:
        try:
            # noinspection PyUnresolvedReferences
            log.debug("Successfully authenticated as: @%s", user.screen_name)
        except AttributeError as e:
            log.warning("Successfully authenticated as an unidentifiable user")
except FileNotFoundError as e:
    make_key_file()
    log.critical("No key file found: %s\nWritten template file", KEY_FILE)
    exit(1)
except KeyError as e:
    log.critical("Malformed key file: %s\nMissing key: %s", KEY_FILE, e)
    os.rename(KEY_FILE, KEY_FILE + INVALID_FILE_SUFFIX)
    make_key_file()
    log.critical("Moved %s to %s and written template to", KEY_FILE, KEY_FILE + INVALID_FILE_SUFFIX, KEY_FILE)
    exit(2)
except tweepy.error.TweepError as e:
    log.critical("Twitter API error: authentication failed")
    exit(3)

# Load tweet templates
try:
    with open(TEMPLATE_FILE, 'r') as templateFile:
        templates = json.load(templateFile)
    log.debug("Read templates from: %s", TEMPLATE_FILE)
except FileNotFoundError as e:
    make_template_file()
    log.error("No template file found: %s\nWritten template", TEMPLATE_FILE)
except KeyError as e:
    log.error("Malformed template file: %s\nMissing key: %s", TEMPLATE_FILE, e)
    os.rename(TEMPLATE_FILE, TEMPLATE_FILE + INVALID_FILE_SUFFIX)
    make_template_file()
    log.error("Moved %s to %s and written template", TEMPLATE_FILE, TEMPLATE_FILE + INVALID_FILE_SUFFIX, TEMPLATE_FILE)
log.debug("Setup complete\n")

assert api and templates
overThreshold: dict = {}
lastTweeted: dict = {}
try:
    while True:
        with requests.get(SUMMARY_URL) as response:
            summaryList: list = response.json()
            # Iterate over different locations
            for summary in summaryList:
                locID: str = summary[LOC_ID]
                locName: str = summary[LOC_NAME]
                posts: list = summary[LOC_DATA]
                # Sort list by timestamps, no longer necessary but leaving as it's conceptually pleasant
                posts.sort(key=lambda p: dateutil.parser.parse(p[POST_TIMESTAMP]))
                # Average CO2 level within time threshold
                currentTime: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)
                co2values: list = []
                for post in filter(
                        lambda p: currentTime - dateutil.parser.parse(p[POST_TIMESTAMP]) < AVERAGING_PERIOD
                        if AVERAGING_PERIOD else True,  # Use all if no time threshold provided
                        posts
                ):
                    co2values.append(post[POST_CO2])
                # Threshold
                if len(co2values) < 1:
                    # No recent updates
                    log.debug("%s: No recent updates", locID)
                    continue
                tweetString: str or None = None
                if statistics.mean(co2values) > CO2_WARNING_THRESHOLD:
                    # Check if already warned
                    if (
                            locID in overThreshold.keys() and not overThreshold[locID]
                            or locID not in overThreshold.keys()  # First time seen
                    ):
                        # Warning threshold breached
                        log.debug("%s: Breached warning threshold.", locID)
                        tweetString = random.choice(
                            templates[TEMPLATE_WARNING][TEMPLATE_WARNING_NEW])  # Choose random template
                    else:
                        # Remains above threshold
                        if (now() - lastTweeted[locID]) >= WARNING_PERIOD:
                            # Long enough to tweet again
                            log.debug("%s: Still above warning threshold, tweeting again.", locID)
                            tweetString = random.choice(templates[TEMPLATE_WARNING][TEMPLATE_WARNING_CONTINUED])
                        else:
                            # Too soon to tweet again
                            log.debug("%s: Still above warning threshold, too soon to tweet again", locID)
                    overThreshold[locID] = True
                elif statistics.mean(co2values) < CO2_SAFETY_THRESHOLD:
                    if locID in overThreshold.keys() and overThreshold[locID]:
                        # Dropped below safety threshold
                        log.debug("%s: Dropped below safety threshold.", locID)
                        tweetString = random.choice(templates[TEMPLATE_SAFETY])
                    overThreshold[locID] = False
                # Tweet
                if tweetString:
                    tweetString = now().strftime(TWEET_TIMESTAMP_FORMAT) + " " + (
                                tweetString + " #sierra_{placeID}").format(
                        placeName=locName,
                        placeID=locID.replace('-', '_')  # No hyphens in hashtags
                    )
                    try:
                        log.info("%s: Tweeting: '%s'", locID, tweetString)
                        api.update_status(tweetString)
                        lastTweeted[locID] = now()
                    except tweepy.error.TweepError as e:
                        if e.reason == 'Status is a duplicate.':
                            # TODO Don't know if error code 187 is specifically for duplicates
                            log.error("Tweet failed as would be a duplicate: %s", tweetString)
                        else:
                            raise e
                else:
                    log.debug("%s: No tweet needed", locID)
        time.sleep(DAEMON_PERIOD.total_seconds())  # TODO Catch keyboard interrupt to cleanly exit
except KeyError as e:
    log.critical("Fetched JSON object missing key: %s", e)
    exit(9)

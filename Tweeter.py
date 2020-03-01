#  MIT License
#
#  Copyright (c) 2020 GP2020-Sierra
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

#  MIT License
#
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#
import datetime
#  MIT License
#
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#
import json
import logging
import os
import random
import sys
from statistics import mean
from time import sleep

import requests
import tweepy
from dateutil import parser

CHECK_PERIOD: datetime.timedelta = datetime.timedelta(minutes=15)
AVERAGING_PERIOD: datetime.timedelta = datetime.timedelta(minutes=15)
WARNING_PERIOD: datetime.timedelta = datetime.timedelta(minutes=90)
CO2_WARNING_THRESHOLD = 1_400 # ppm
CO2_SAFETY_THRESHOLD = 1_000 # ppm
KEY_FILE: str = "keys.json"
TEMPLATE_FILE: str = "templates.json"
summaryURL: str = "https://gp2020-sierra.azurewebsites.net/api/summary"

INVALID_FILE_SUFFIX: str = "_invalid"

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

# Logging
log: logging.Logger = logging.getLogger(__name__)
log.setLevel(logging.INFO)
fmt: logging.Formatter = logging.Formatter(
    fmt='[%(asctime)-19s] %(levelname)8s: %(message)s'
)
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
        with requests.get(summaryURL) as response:
            summaryList: list = response.json()
            # Iterate over different locations
            for summary in summaryList:
                locID: str = summary[LOC_ID]
                locName: str = summary[LOC_NAME]
                posts: list = summary[LOC_DATA]
                # Sort list by timestamps
                posts.sort(key=lambda p: parser.parse(p[POST_TIMESTAMP]))
                # Average CO2 level over past [time period]
                now: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)
                co2values: list = []
                for post in filter(lambda p: now - parser.parse(p[POST_TIMESTAMP]) < AVERAGING_PERIOD, posts):
                    co2values.append(post[POST_CO2])
                # Threshold
                if len(co2values) < 1:
                    # No recent updates
                    log.debug("%s: No recent updates", locID)
                    continue
                tweetString: str or None = None
                if mean(co2values) > CO2_WARNING_THRESHOLD:
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
                        if (datetime.datetime.now() - lastTweeted[locID]) >= WARNING_PERIOD:
                            # Long enough to tweet again
                            log.debug("%s: Still above warning threshold, tweeting again.", locID)
                            tweetString = random.choice(templates[TEMPLATE_WARNING][TEMPLATE_WARNING_CONTINUED])
                        else:
                            # Too soon to tweet again
                            log.debug("%s: Still above warning threshold, too soon to tweet again", locID)
                    overThreshold[locID] = True
                elif mean(co2values) < CO2_SAFETY_THRESHOLD:
                    if locID in overThreshold.keys() and overThreshold[locID]:
                        # Dropped below safety threshold
                        log.debug("%s: Dropped below safety threshold.", locID)
                        tweetString = random.choice(templates[TEMPLATE_SAFETY])
                    overThreshold[locID] = False
                # Tweet
                if tweetString:
                    tweetString = (tweetString + " #sierra_{placeID}").format(
                        placeName=locName,
                        placeID=locID.replace('-', '_')  # No hyphens in hashtags
                    )
                    log.info("%s: Tweeting: '%s'", locID, tweetString)
                    api.update_status(tweetString)
                    lastTweeted[locID] = datetime.datetime.now()
                else:
                    log.debug("%s: No tweet needed", locID)
        sleep(CHECK_PERIOD.total_seconds()) # TODO Catch keyboard interrupt to cleanly exit
except KeyError as e:
    log.critical("Fetched JSON object missing key: %s", e)
    exit(9)

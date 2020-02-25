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
import json
import logging
import sys
from datetime import datetime, timedelta
from statistics import mean
from time import sleep

import requests
import tweepy
from dateutil import parser
# Parameters
from tweepy import API

TWEET_PERIOD:     timedelta = timedelta(minutes=30)
AVERAGING_PERIOD: timedelta = timedelta(minutes=30)
CO2_THRESHOLD = 1_000
KEY_FILE: str = "keys.json"
summaryURL: str = "https://gp2020-sierra.azurewebsites.net/api/summary"

# API key attributes
KEYS_API = "api"
KEYS_API_KEY = "key"
KEYS_API_SECRET = "secret"
KEYS_ACCESS = "access"
KEYS_ACCESS_TOKEN = "token"
KEYS_ACCESS_SECRET = "secret"
# Location attributes
LOC_ID = "locationID"
LOC_NAME = "name"
LOC_DATA = "data"
# Post attributes
POST_TIMESTAMP = "timestamp"
POST_TEMP = "temperature"
POST_PRESSURE = "pressure"
POST_HUMIDITY = "humidity"
POST_CO2 = "co2"
POST_DEVICES = "devices"
POST_COUNT = "_count"
POST_IDX = "_idx"

# Logging
log: logging.Logger = logging.getLogger(__name__)
# log.setLevel(logging.WARNING)   # Is the default but setting explicitly
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))
# TODO Handlers to stdout for info/debug stderr for warning+


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


api: API
try:    # Access Twitter API
    # Pull credentials from file
    with open(KEY_FILE, 'r') as keyFile:
        keys: dict = json.load(keyFile)
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
        log.error("Twitter API error: no user found")
        exit(4)
    else:
        try:
            # noinspection PyUnresolvedReferences
            log.debug("Successfully authenticated as: @%s", user.screen_name)
        except AttributeError as e:
            log.warning("Successfully authenticated as an unidentifiable user")
except FileNotFoundError as e:
    make_key_file()
    log.error("No key file found: %s", KEY_FILE)
    exit(1)
except KeyError as e:
    make_key_file()
    log.error("Malformed key file: %s\nMissing key: %s\nOverwritten with template file.", KEY_FILE, e)
    exit(2)
except tweepy.error.TweepError as e:
    log.error("Twitter API error: authentication failed")
    exit(3)

try:
    while True:
        with requests.get(summaryURL) as response:
            summaryList: list = response.json()
            # Iterate over different locations
            for summary in summaryList:
                locId: str = summary[LOC_ID]
                locName: str = summary[LOC_NAME]
                posts: list = summary[LOC_DATA]
                # Sort list by timestamps
                posts.sort(key=lambda p: parser.parse(p[POST_TIMESTAMP]))
                # Average CO2 level over past [time period]
                latest: datetime = parser.parse(posts[0][POST_TIMESTAMP])
                co2values: list = []
                for post in filter(lambda p: latest - parser.parse(p[POST_TIMESTAMP]) < AVERAGING_PERIOD, posts):
                    co2values.append(post[POST_CO2])
                # Threshold
                if mean(co2values) > CO2_THRESHOLD:
                    # TODO Threshold on other values/combining metric?
                    # TODO Raw values in tweet?
                    tweetString: str =\
                        "Current CO\u2082 levels in {place:s} will affect your performance.".format(
                            place=locName
                        )
                    # Tweet
                    api.update_status(tweetString)  # PyCharm gives 'Unbound local variable' for api?
                    # print(tweetString)
                # TODO Track places currently over threshold and tweet when they drop below rather than repeatedly
                #  while above
        sleep(TWEET_PERIOD.total_seconds())
        # TODO Cycling through locations over sleep period so not a barrage of tweets
except KeyError as e:
    log.critical("Fetched JSON object missing key: %s", e.args)
    exit(9)

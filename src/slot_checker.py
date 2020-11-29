#! /usr/bin/env python3

import re
import os
import sys
import time
import threading
from datetime import date, datetime, timedelta

import yaml
import httpx
# https://python-telegram-bot.readthedocs.io/en/stable/
import telegram
import logging as log
import argparse as arg
# https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup
# https://marshmallow.readthedocs.io/en/stable/
from marshmallow.exceptions import ValidationError
from marshmallow import Schema, fields, validate, validates, post_load, ValidationError

from exceptions import slot_checker_exception, IntraFailedSignin, SlotCheckerException, SlotCheckError
from env import SIGNIN_URL, PROJECTS_URL, PROFILE_URL, DEBUG_PROJECT

log.basicConfig(format='%(asctime)s %(levelname)7s %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S',
        level=log.INFO)


class Intra(object):

    def __init__(self, login, password):
        self.signin_url = SIGNIN_URL
        self.client = httpx.Client(timeout=3.05)
        self.login = login
        self.password = password
        self.connected = False

    def signin(self):
        try:
            r = self.client.get(self.signin_url)
            r.raise_for_status()
            soup = BeautifulSoup(r.content, "html.parser")
            token = soup.find("input", {"name": "authenticity_token"})["value"]
            cookies = r.cookies
            data = {
                "utf8": "✓",
                "authenticity_token": token,
                "user[login]": self.login,
                "user[password]": self.password,
                "commit": "Sign+in",
            }
            r = self.client.post(self.signin_url, data=data, cookies=cookies, timeout=3.05)
        except httpx.RequestError as err:
            slot_checker_exception(err, "Network error while logging in the Intra")
        soup = BeautifulSoup(r.content, "html.parser")
        error = soup.find("div", {"class": "alert-danger"})
        if error:
            slot_checker_exception(IntraFailedSignin, error.text)
        log.info("Successfully logged in the Intra as %s", self.login)
        self.connected = True
        return self.connected

    def check_signin(func):
        def wrapper(*args, **kwargs):
            if not args[0].connected:
                if not args[0].signin():
                    return False
            return func(*args, **kwargs)
        return wrapper


    @check_signin
    def get_project_slots(self, project, start, end):
        try:
            get_slot_url = lambda x: PROFILE_URL if x == DEBUG_PROJECT else f"{PROJECTS_URL}/{project}"
            r = self.client.get(
                f"{get_slot_url(project)}/slots.json?start={start}&end={end}", timeout=3.05
            )
            slots = r.json()
        except httpx.RequestError as err:
            slot_checker_exception(err, "Unable to retrieve available projects slots")

        return slots

    def close(self):
        self.client.close()


class Config(object):

    def __init__(self, login, password, projects, send=None, refresh=30, range=7, disponibility="00:00-23:59", avoid_spam=False):
        self.login = login
        self.password = password
        self.refresh = refresh
        self.projects = projects
        self.sender = send
        self.start = date.today()
        self.end = date.today() + timedelta(days=range)
        self.avoid_spam = avoid_spam
        try:
            hours = disponibility.split('-')
            self.start_dispo = datetime.strptime(hours[0], '%H:%M').time()
            self.end_dispo = datetime.strptime(hours[1], '%H:%M').time()
        except:
            log.error("disponibility hours is not valid : %s" % disponibility)
            self.start_dispo = None
            self.end_dispo = None

class ConfigSchema(Schema):

    senders = ['telegram']
    telegram_options = ['chat_id', 'token']

    login = fields.Str(required=True)
    password = fields.Str(required=True)
    projects = fields.List(
        fields.Str(
            required=True
        ),
        required=True
    )
    send = fields.Dict(
        keys=fields.Str(
            required=True,
            validate=validate.OneOf(senders)
        ),
        values=fields.Dict(
            keys=fields.Str(
                required=True,
                validate=validate.OneOf(telegram_options)
            ),
            values=fields.Str(
                required=True
            ),
            required=True
        ),
        required=False
    )
    refresh = fields.Int(required=False, default=30)
    range = fields.Int(required=False, default=7)
    disponibility = fields.Str(required=False, default="00:00-23:59")
    avoid_spam = fields.Boolean(required=False)

    @post_load
    def create_processing(self, data, **kwargs):
        return Config(**data)

    @validates('disponibility')
    def validate_disponibility(self, disponibility):
        rx = re.compile(r'^([0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2})$')
        match = rx.search(disponibility)
        if not match:
            raise ValidationError("disponibility not valid")


class Sender(object):

    def __init__(self, sender):
        self.sender = sender
        for key, value in self.sender.items():
            self.send_option = key
            self.sender_config = value
        self.bot = telegram.Bot(token=self.sender_config['token'])

    def send_telegram(self, message):
        self.bot.send_message(text=message, parse_mode='HTML', chat_id=self.sender_config['chat_id'])

    def send(self, message):
        if self.send_option == 'telegram':
            self.send_telegram(message)


class Checker(object):

    def __init__(self, config: Config):
        self.config = config
        self.intra = Intra(self.config.login, self.config.password)
        self.sender = None
        if self.config.sender:
            self.sender = Sender(self.config.sender)
        self.health_delay = 60
        self.health = threading.Thread(target=self.health_loop)
        # Needed so that calls to sys.exit() don't hang with never-ending thread
        # https://stackoverflow.com/questions/38804988/what-does-sys-exit-really-do-with-multiple-threads
        self.health.daemon = True
        self.errors = 0
        self.errors_limit = 2

    def health_loop(self):
        while True:
            log.info("[Health check] slot checker still alive")
            time.sleep(self.health_delay)

    def run(self):
        self.health.start()
        sent = []
        while True:
            for project in self.config.projects:
                slots = self.intra.get_project_slots(project, start=self.config.start, end=self.config.end)
                if slots == False:
                    self.error()
                elif 'error' in slots:
                    slots = None
                    self.error(slots['error'])
                else:
                    self.clean_errors()
                    for slot in slots:
                        log.info(slot)
                        date = datetime.strptime(slot['start'], '%Y-%m-%dT%H:%M:00.000+01:00')
                        log.info("found slot for project %s, %s at %s" % (project, date.strftime('%d/%m/%Y'), date.strftime('%H:%M')))
                        if (date.time() > self.config.start_dispo and date.time() < self.config.end_dispo):
                            if self.sender:
                                if not self.config.avoid_spam or slot['id'] not in sent:
                                    log.info("send to %s" % self.sender.send_option)
                                    message = "Slot found for <b>%s</b> project :\n <b>%s</b> at <b>%s</b>" % (project, date.strftime('%A %d/%m'), date.strftime('%H:%M'))
                                    self.sender.send(message)
                                    sent.append(slot['id'])
                                else:
                                    log.info("Slot details already sent once -> avoiding spam")
                        else:
                            log.info("the slot is not in the disponibility range, not sending")
            time.sleep(self.config.refresh)
    
    def clean_errors(self):
        self.errors = 0

    def error(self, msg=None):
        if msg is not None:
            log.error(msg)
        if self.errors >= self.errors_limit:
            self.intra.close()
            slot_checker_exception(SlotCheckError, "Too many errors while checking for available slots")
        self.errors += 1


if __name__ == "__main__":
    parser = arg.ArgumentParser(description="42 slot checker")
    parser.add_argument(
        '-c',
        '--config',
        type=str,
        default='config.yml',
        help='config file'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='include debugging logs')
    args = parser.parse_args()

    if os.environ.get("SLOT_CHECKER_DEBUG") or args.verbose:
        log.getLogger().setLevel(log.DEBUG)

    try:
        try:

            with open(args.config) as f:
                data = yaml.load(f, Loader=yaml.FullLoader)
            schema = ConfigSchema()
            config = schema.load(data)
        except (FileNotFoundError, ValidationError) as e:
            slot_checker_exception(
                e, "There seems to be a problem with your configuration file"
            )

        log.info("Starting the checker")
        checker = Checker(config)
        checker.run()

    except SlotCheckerException as e:
        log.error("Aborting following an error while running the Slot Checker")
        sys.exit(1)

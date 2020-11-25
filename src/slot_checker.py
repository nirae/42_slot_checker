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
from datetime import date, datetime, timedelta

log.basicConfig(format='%(levelname)s %(asctime)s %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S',
        level=log.INFO)


class Intra(object):

    def __init__(self, login, password):
        self.signin_url = 'https://signin.intra.42.fr/users/sign_in'
        self.slot_url = "https://projects.intra.42.fr/projects/{project}/slots.json?start={start}&end={end}"
        self.client = httpx.Client()
        self.login = login
        self.password = password
        self.connected = False

    def signin(self):
        r = self.client.get(self.signin_url)
        soup = BeautifulSoup(r.content, 'html.parser')
        token = soup.find('input', {"name": "authenticity_token"})['value']
        cookies = r.cookies
        data = {
            'utf8':	"✓",
            'authenticity_token': token,
            'user[login]': self.login,
            'user[password]': self.password,
            'commit': 'Sign+in'
        }
        r = self.client.post(self.signin_url, data=data, cookies=cookies)
        soup = BeautifulSoup(r.content, 'html.parser')
        error = soup.find('div', {"class": "alert-danger"})
        if error:
            log.error(error.text)
            return False
        if r.status_code != 200:
            log.error("can't connect to the intra")
            return False
        self.connected = True
        return True

    def check_signin(func):
        def wrapper(*args, **kwargs):
            if not args[0].connected:
                if not args[0].signin():
                    return False
            return func(*args, **kwargs)
        return wrapper

    @check_signin
    def get_project_slots(self, project, start, end):
        if project == 'debug_my_slots':
            r = self.client.get('https://profile.intra.42.fr/slots.json?start={start}&end={end}'.format(start=start, end=end))
        else:
            r = self.client.get(self.slot_url.format(project=project, start=start, end=end))
        slots = r.json()
        return slots

    def close(self):
        self.client.close()


class Config(object):

    def __init__(self, login, password, projects, send=None, refresh=30, range=7, disponibility="00:00-23:59"):
        self.login = login
        self.password = password
        self.refresh = refresh
        self.projects = projects
        self.sender = send
        self.start = date.today()
        self.end = date.today() + timedelta(days=range)
        try:
            hours = disponibility.split('-')
            self.start_dispo = datetime.strptime(hours[0], '%H:%M').time()
            self.end_dispo = datetime.strptime(hours[1], '%H:%M').time()
        except:
            log.error("disponibility hours is not valid : %s" % disponibility)
            self.start_dispo = None
            self.end_dispo = None
        print(self.start_dispo, self.end_dispo)

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
        for key, value in sender.items():
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
        self.intra = Intra(config.login, config.password)
        self.sender = None
        if self.config.sender:
            self.sender = Sender(self.config.sender)
        self.health_delay = 60
        self.health = threading.Thread(target=self.health_loop)
        
    def health_loop(self):
        while True:
            log.info("[Health check] slot checker still alive")
            time.sleep(self.health_delay)

    def run(self):
        self.health.start()
        while True:
            for project in self.config.projects:
                slots = self.intra.get_project_slots(project, start=self.config.start, end=self.config.end)
                if slots == False:
                    self.quit()
                if 'error' in slots:
                    log.error(slots['error'])
                    self.quit()
                for slot in slots:
                    log.info(slot)
                    date = datetime.strptime(slot['start'], '%Y-%m-%dT%H:%M:00.000+01:00')
                    log.info("found slot for project %s, %s at %s" % (project, date.strftime('%d/%m/%Y'), date.strftime('%H:%M')))
                    if (date.time() > config.start_dispo and date.time() < config.end_dispo):
                        if self.sender:
                            log.info("send to %s" % self.sender.send_option)
                            message = "Slot found for <b>%s</b> project :\n <b>%s</b> at <b>%s</b>" % (project, date.strftime('%A %d/%m'), date.strftime('%H:%M'))
                            self.sender.send(message)
                    else:
                        log.info("the slot is not in the disponibility range, not sending")
            time.sleep(self.config.refresh)
    
    def quit(self):
        log.info("Exit")
        self.intra.close()
        sys.exit(1)


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
        with open(args.config) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
        schema = ConfigSchema()
        config = schema.load(data)
        log.debug(f"CONFIGURATION : {config}")
    except (FileNotFoundError, ValidationError) as e:
        log.error("There seems to be a problem with your configuration file\n{e}")
        log.info("Exit")
        sys.exit(1)
    
    log.info("Starting the checker")
    checker = Checker(config)
    checker.run()

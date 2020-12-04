#! /usr/bin/env python3

"""Slot checker for 42 projects"""

import re
import os
import sys
import time
import threading
import logging as log
import argparse as arg
from datetime import date, datetime, timedelta

import yaml
import httpx

# https://python-telegram-bot.readthedocs.io/en/stable/
import telegram

# https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup

# https://marshmallow.readthedocs.io/en/stable/
from marshmallow import Schema, fields, validate, validates, post_load, ValidationError

from exceptions import slot_checker_exception, IntraFailedSignin, SlotCheckerException
from env import SIGNIN_URL, PROJECTS_URL, PROFILE_URL, DEBUG_PROJECT, PATH_CONFIG

log.basicConfig(
    format="%(asctime)s %(levelname)7s %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    level=log.INFO,
)


class Intra:
    """Handle connection to the Intra"""

    def __init__(self, login, password):
        """Sign into the intra

        If authentication changes while this connection is open, a new Intra should be initialized
        """

        self.signin_url = SIGNIN_URL
        self.login = login
        self.password = password
        self.connected = False
        self._client = None
        self._signin()

    @property
    def client(self):
        """Set up an httpx client to connect to the Intra

        Initializes the client only if none is active.
        """
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    def _signin(self):
        """Sign into the intra

        Raises an error in case of any httpx related network error or wrong authentication
        """

        try:
            resp = self.client.get(self.signin_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            token = soup.find("input", {"name": "authenticity_token"})["value"]
            cookies = resp.cookies
            data = {
                "utf8": "✓",
                "authenticity_token": token,
                "user[login]": self.login,
                "user[password]": self.password,
                "commit": "Sign+in",
            }
            resp = self._client.post(
                self.signin_url, data=data, cookies=cookies, timeout=3.05
            )
        except httpx.RequestError as err:
            slot_checker_exception(err, "Network error while logging in the Intra")
        soup = BeautifulSoup(resp.content, "html.parser")
        error = soup.find("div", {"class": "alert-danger"})
        if error:
            slot_checker_exception(IntraFailedSignin, error.text)
        log.info("Successfully logged in the Intra as %s", self.login)

    def get_project_slots(self, project, start, end, retries=0):
        """Query a project page for available evaluation slots

        Return status code 404 (unknown project) and 403 (unavailable corrections),
        trigger a warning log.

        Raises an error in case of any httpx related network error.

        Args:
            - start: start of the disponibility period
            - end: end of the disponibility period
            - retries: number of retries in case of network error
        """

        max_retries = 10
        try:
            get_slot_url = (
                lambda x: PROFILE_URL
                if x == DEBUG_PROJECT
                else f"{PROJECTS_URL}/{project}"
            )
            resp = self.client.get(
                f"{get_slot_url(project)}/slots.json?start={start}&end={end}",
                timeout=3.05,
            )
            slots = resp.json()
            if resp.status_code == 404:
                log.warning("Project %s does not exist", project)
            elif resp.status_code == 403:
                log.warning(
                    "You don't have access to any correction slots for project %s",
                    project,
                )
            return slots
        except (httpx.RequestError, httpx.ReadTimeout, httpx.ConnectError) as err:
            if retries < max_retries:
                log.debug(
                    "Failed attempt #%d to get projects slots (max %d)",
                    retries,
                    max_retries,
                )
                time.sleep(2)
                return self.get_project_slots(project, start, end, retries + 1)
            slot_checker_exception(err, "Unable to retrieve available projects slots")


class Config:
    """Load and check configuration"""

    # pylint: disable=too-many-instance-attributes
    # Nine is reasonable in this case.

    class Schema(Schema):
        """Template to check that configuration is valid"""

        senders = ["telegram"]
        telegram_options = ["chat_id", "token"]

        login = fields.Str(required=True)
        password = fields.Str(required=True)
        projects = fields.List(fields.Str(required=True), required=True)
        send = fields.Dict(
            keys=fields.Str(required=True, validate=validate.OneOf(senders)),
            values=fields.Dict(
                keys=fields.Str(
                    required=True, validate=validate.OneOf(telegram_options)
                ),
                values=fields.Str(required=True),
                required=True,
            ),
            required=False,
        )
        refresh = fields.Int(required=False, default=30)
        check_range = fields.Int(required=False, default=7)
        disponibility = fields.Str(required=False, default="00:00-23:59")
        avoid_spam = fields.Boolean(required=False)

        @post_load
        def create_processing(self, data, **_):
            """Hand over validated configuration"""
            # pylint: disable=no-self-use
            # self is required for the Marshmallow decorator

            return Config(**data)

        @validates("disponibility")
        def validate_disponibility(self, disponibility):
            """Check that disponibility format is valid"""
            regex = re.compile(r"^([0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2})$")
            match = regex.search(disponibility)
            if not match:
                raise ValidationError("disponibility not valid")

    def __init__(
        self,
        login,
        password,
        projects,
        send=None,
        refresh=30,
        check_range=7,
        disponibility="00:00-23:59",
        avoid_spam=False,
    ):
        """Store configuration"""
        # pylint: disable=too-many-arguments
        # Nine is reasonable in this case.

        self.login = login
        self.password = password
        self.refresh = refresh
        self.projects = projects
        self.sender = send
        self.start = date.today()
        self.end = date.today() + timedelta(days=check_range)
        self.avoid_spam = avoid_spam
        self.mtime = time.time()
        try:
            hours = disponibility.split("-")
            self.start_dispo = datetime.strptime(hours[0], "%H:%M").time()
            self.end_dispo = datetime.strptime(hours[1], "%H:%M").time()
        except ValidationError:
            log.error("disponibility hours is not valid : %s", disponibility)
            self.start_dispo = None
            self.end_dispo = None

    @property
    def updated(self):
        """Check if config was updated since last loaded"""

        if self.mtime < os.path.getmtime(PATH_CONFIG):
            log.info("Config file has changed since starting the Slot Checkout")
            return True
        return False

    @staticmethod
    def load():
        """Load configuration from file

        Returns a Config object
        """
        log.info("Loading configuration from file %s", PATH_CONFIG)
        try:
            with open(PATH_CONFIG) as config:
                data = yaml.load(config, Loader=yaml.FullLoader)
            schema = Config.Schema()
            return schema.load(data)
        except (FileNotFoundError, ValidationError, yaml.parser.ParserError) as err:
            slot_checker_exception(
                err, "There seems to be a problem with your configuration file"
            )


class Sender:
    """Handle interaction with a message channels"""

    def __init__(self, sender):
        """Get ready to send messages"""

        self.sender = sender
        for key, value in self.sender.items():
            self.send_option = key
            self.sender_config = value
        self.bot = telegram.Bot(token=self.sender_config["token"])

    def send_telegram(self, message):
        """Send a message to a telegram bot"""

        self.bot.send_message(
            text=message, parse_mode="HTML", chat_id=self.sender_config["chat_id"]
        )

    def send(self, message):
        """Send message to the chosen channels"""

        if self.send_option == "telegram":
            self.send_telegram(message)


class Checker:
    """Check the user's project pages for available slots"""

    def __init__(self, config: Config):
        """Get ready to check for slots"""

        log.debug("Initializing the checker")
        self.config = config
        self._intra = None
        self._sender = None
        self.health_delay = 60
        self.health = threading.Thread(target=self.health_loop)
        # Needed so that calls to sys.exit() don't hang with never-ending thread
        # https://stackoverflow.com/questions/38804988/what-does-sys-exit-really-do-with-multiple-threads
        self.health.daemon = True
        self.health.start()

    @property
    def sender(self):
        """Set up a Sender object if none is active"""

        if self.config.sender and self._sender is None:
            self._sender = Sender(self.config.sender)
        return self._sender

    @property
    def intra(self):
        """Valid connection the intra

        If there is no active connection or credentials have changed since logging in,
        a new connection is open. Otherwise, the connection remains unchanged.
        """

        if (
            self._intra is None
            or self._intra.login != self.config.login
            or self._intra.password != self.config.password
        ):
            self._intra = Intra(self.config.login, self.config.password)
        return self._intra

    def health_loop(self):
        """Log regularly that the checker is alive"""

        while True:
            log.info("[Health check] slot checker still alive")
            time.sleep(self.health_delay)

    def run(self):
        """Run the slot checker

        For all configured projects, continuously get available slots within disponibility timeframe
        Send positive results to desired message channels at least once (if no-spam is True)
        """

        log.info("Check for available slots")
        sent = []
        with self.intra.client:
            while True:
                if self.config.updated:
                    self.config = Config.load()
                    return self.run()
                for project in self.config.projects:
                    slots = self.intra.get_project_slots(
                        project, start=self.config.start, end=self.config.end
                    )
                    for slot in slots:
                        slot_date = datetime.strptime(
                            slot["start"], "%Y-%m-%dT%H:%M:00.000+01:00"
                        )
                        log.info(
                            "found slot for project %s, %s at %s\n%s",
                            project,
                            slot_date.strftime("%d/%m/%Y"),
                            slot_date.strftime("%H:%M"),
                            slot,
                        )
                        if (
                            slot_date.time() > self.config.start_dispo
                            and slot_date.time() < self.config.end_dispo
                        ):
                            if not self.config.avoid_spam or slot["id"] not in sent:
                                log.info("send to %s", self.sender.send_option)
                                message = f"Slot found for <b>{project}</b> project :\n \
                                        <b>{slot_date.strftime('%A %d/%m')}</b> at \
                                        <b>{slot_date.strftime('%H:%M')}</b>"
                                self.sender.send(message)
                                sent.append(slot["id"])
                            else:
                                log.info(
                                    "Slot details already sent once -> avoiding spam"
                                )
                        else:
                            log.info(
                                "the slot is not in the disponibility range, not sending"
                            )
                time.sleep(self.config.refresh)


if __name__ == "__main__":

    parser = arg.ArgumentParser(description="42 slot checker")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="include debugging logs"
    )
    args = parser.parse_args()

    if os.environ.get("SLOT_CHECKER_DEBUG") or args.verbose:
        log.getLogger().setLevel(log.DEBUG)
    try:
        checker = Checker(Config.load())
        checker.run()
    except SlotCheckerException as err:
        log.error("Aborting following an error while running the Slot Checker")
        sys.exit(err.error_code)

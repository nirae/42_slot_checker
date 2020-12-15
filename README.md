# 42 Slot Checker

![Build](https://github.com/nirae/42_slot_checker/workflows/Build/badge.svg)
![Lint](https://github.com/nirae/42_slot_checker/workflows/Lint/badge.svg)
![Black](https://github.com/nirae/42_slot_checker/workflows/Black/badge.svg)

A tool to check and notify about available correction slots for 42 projects.  
It does not book slots for you.  
It was designed to be helpful given the difficulty of finding slots.  
Please use it responsibly and don't make it part of the problem !

## Usage

```
./src/slot_checker.py -h
usage: slot_checker.py [-h] [-c CONFIG] [-v]

42 slot checker

optional arguments:
  -h, --help                    show this help message and exit
  -c CONFIG, --config CONFIG    config file
  -v, --verbose                 include debugging logs
```

If you have missing dependencies, install them with pip:

```
pip install -r requirements.txt
```

or consider using a virtual environment (for instance with [pipenv](https://pypi.org/project/pipenv/) and similarly set it up from the requirements:

```
pipenv install -r requirements.txt

# Open a shell in the virtual env
pipenv shell
```

## Usage with Docker

Full set-up is provided with Docker, docker-compose and Makefile.
If you don't have Docker and docker-compose, check out the official [Docker](https://docs.docker.com/get-docker/) and [Docker-Compose](https://docs.docker.com/compose/install/) doc and follow the guidelines for your distribution.

Then you can run one of the makefile rules:

```
# Build and up container
make up

# Build and up container in detached mode
make upd
```

If you don't have Docker and docker-compose, check out the official [Docker](https://docs.docker.com/get-docker/) and [Docker-Compose](https://docs.docker.com/compose/install/) doc and follow the guidelines for your distribution.

## Configuration

The program work with a YAML configuration file, `config.yml` by default

### Minimal configuration

```yml
login: "my_42_login"
password: "my_42_password"
send:
  telegram:
    token: "000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    chat_id: "0000000000"
projects:
  - "42cursus-ft_my_project"
```

### All options

```yml
login: "my_42_login"
password: "my_42_password"
refresh: 30
range: 7
disponibility: "09:00-20:00"
send:
  telegram:
    token: "000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    chat_id: "0000000000"
projects:
  - "42cursus-ft_my_project"
avoid_spam: true
```

- `refresh` is the time to wait for refresh the slot page in seconds (default: 30)
- `range` is the number of days during which you are looking for slots (default: 7)
- `disponibility` is the range of the hours you want to be alerted (default: 00:00-23:59)
- `avoid_spam`: if true, only one message will be sent for a given slot (default: False)

## Sending

To send with `telegram`, you need a bot. [How to create a telegram bot?](https://fr.jeffprod.com/blog/2017/creer-un-bot-telegram/)

:warning: Don't forget to talk to your bot one first time :warning:

You need the `token` of your bot, and **your** `chat_id`
To find your `chat_id`, initiate a conversation with the telegram bot @chatid_echo_bot

## Debug

Set the environment variable `SLOT_CHECKER_DEBUG` to get more detailed logs.

You can also use your slot page instead of a project slot page by choosing `debug_my_slots` in the `projects` option in the yaml configuration file.
You just have to add some slots et you will see your slots to debug

To get more detailed logs:

- with docker: set the environment variable `SLOT_CHECKER_DEBUG` in the docker-compose.yml
- without docker: run the slot_checker with its --verbose option.

## Dev

Be aware that the build stage will check that your code is blacked and linted.
Pre-commit hooks have been configured to ease these checks during development.
If you want to use this development set-up:
```
pip install -r requirements-dev.txt
```

Staged files will be checked anytime a change is committed.
In case of a format error, the commit will fail but the files will be formatted.

To run pre-commit checks manually:

```
# On staged files
pre-commit run

# On all files
pre-commit run --all-files
```

This is discouraged, but to skip these checks while committing:

```
git commit -m "foo" --no-verify
```

If you don't wish to use pre-commit and want to black your files manually, using this containerized version will avoid OS-related differences with the build black stage.

```
# Inside the root of your project directory
docker run --rm -v (pwd):/data cytopia/black .
```

## TODO

- [] add discord on senders
- [x] log every x minutes the bot is alive
- [] custom header with referer, user-agent...
```

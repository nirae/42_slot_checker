# 42 Slot Checker

## Usage

```
./src/slot_checker.py -h
usage: slot_checker.py [-h] [-c CONFIG]

42 slot checker

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        config file

```
If you have missing dependencies, install them with pip:
```
pip install -r requirements.txt
```
or consider using a virtual environment.

## Docker

Full set-up is provided with Docker, docker-compose and Makefile.
If you don't have Docker and docker-compose, check out the official [Docker](https://docs.docker.com/get-docker/) and [Docker-Compose](https://docs.docker.com/compose/install/) doc and follow the guidelines for your distribution.

Then you can run one of the makefile rules:
```
# Build and up container
make up

# Build and up container in detached mode
make upd
```

## Configuration

The program work with a YAML configuration file, `config.yml` per default

### Minimal configuration

```yml
login: "my_42_login"
password: "my_42_password"
send:
  telegram:
    token: '000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    chat_id: '0000000000'
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
    token: '000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    chat_id: '0000000000'
projects:
  - "42cursus-ft_my_project"
```

- `refresh` is the time to wait for refresh the slot page in second (default: 30)
- `range` is the number of days during which you are looking for slots (default: 7)
- `disponibility` is the range of the hours you want to be alerted (default: 00:00-23:59)

## Sending

To send with `telegram`, you need a bot. [How to create a telegram bot?](https://fr.jeffprod.com/blog/2017/creer-un-bot-telegram/)

Don't forget to talk to your bot one first time /!\

You need the `token` of your bot, and **your** `chat_id`

## Debug

Set the environment variable `SLOT_CHECKER_DEBUG` to get more detailed logs. 

You can also use your slot page instead of a project slot page by choosing `debug_my_slots` in the `projects` option in the yaml configuration file. You just have to add some slots et you will see your slots to debug

## TODO

- [] add discord on senders
- [x] log every x minutes the bot is alive
- [] custom header with referer, user-agent... 

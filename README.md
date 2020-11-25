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

## Docker

```
make build && make up
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
send:
  telegram:
    token: '000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    chat_id: '0000000000'
projects:
  - "42cursus-ft_my_project"
```

- `refresh` is the time to wait for refresh the slot page in second (default: 30)
- `range` is the number of days during which you are looking for slots (default: 7)

## Sending

To send with `telegram`, you need a bot. [How to create a telegram bot?](https://fr.jeffprod.com/blog/2017/creer-un-bot-telegram/)

Don't forget to talk to your bot one first time /!\

You need the `token` of your bot, and **your** `chat_id`

## Debug

Set the environment variable `SLOT_CHECKER_DEBUG` to get more detailed logs. 

You can also use your slot page instead of a project slot page by choosing `debug_my_slots` in the `projects` option in the yaml configuration file. You just have to add some slots et you will see your slots to debug

## TODO

- [] add discord on senders
- [] log every x minutes the bot is alive

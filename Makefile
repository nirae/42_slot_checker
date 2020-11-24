all: build run

build:
	docker build -t slot_checker .

up:
	docker-compose up -d

restart:
	docker-compose restart

down:
	docker-compose down

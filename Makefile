all: build run

build: web renderer

web:
	docker-compose build web
renderer:
	docker-compose build renderer


run:
	docker-compose up
install: build
	docker-compose up -d

stop:
	docker-compose down


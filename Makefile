.PHONY: help install importdb clean-cache rebuild start stop logs ps bash

NAME = exegol
TARGETS := $(MAKEFILE_LIST)
SHARE = $(PWD)/shared-volume

help: ## [Help] This help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(TARGETS) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

## DOCKER
build: ## [Docker] build
	sudo docker build -t exegol .

update: ## [Docker] update
	sudo docker build --no-cache --pull -t exegol .

up: ## [Docker] create and start the container (detached)
	sudo docker run -d -ti --network host -e DISPLAY=$$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --volume $$XAUTH:/root/.Xauthority --volume $(SHARE):/share --name exegol_container exegol

shell: ## [Docker] shell
	sudo docker exec -ti exegol_container zsh

start: ## [Docker] start
	sudo docker start exegol_container

stop: ## [Docker] stop
	sudo docker stop exegol_container

down: ## [Docker] stop and destroy container
	sudo docker stop exegol_container && sudo docker rm exegol_container


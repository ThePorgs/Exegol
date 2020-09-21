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

start: ## [Docker] Start
	sudo docker run -ti --network host --volume $(SHARE):/share --name exegol_container exegol zsh

startd: ## [Docker] Start detached
	sudo docker run -ti -d --network host --volume $(SHARE):/share --name exegol_container exegol zsh

bash: ## [Docker] bash
	sudo docker exec -ti exegol_container zsh

stop: ## [Docker] stop
	sudo docker stop exegol_container

destroy: ## [Docker] destroy container
	sudo docker stop exegol_container && sudo docker rm exegol_container


.PHONY: help install importdb clean-cache rebuild start stop logs ps bash

TARGETS := $(MAKEFILE_LIST)

# Image name
NAME = nwodtuhs/exegol
# Name given to the container, useful for docker run/start/stop/rm
CONTAINER_NAME = exegol
# Name given to the docker hostname
HOSTNAME = exegol
# GitHub branch to pull sources from
BRANCH = dev
# Image tag for install/update
TAG = dev
# Absolute path to the Makefile
EXEGOL_PATH = $(shell pwd)
# Path to the shared-volume
SHARE = $(EXEGOL_PATH)/shared-volume

help: ## [Help] This help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(TARGETS) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

install: ## [Docker] pull exegol from DockerHub
	docker pull $(NAME):$(TAG)

update: ## [Docker] update exegol from DockerHub
	docker pull $(NAME):$(TAG)

install-from-sources: ## [Docker] build exegol from the sources cloned from GitHub
	docker build --tag $(NAME) $(EXEGOL_PATH)

update-from-sources: ## [Docker] update exegol from the sources cloned from GitHub
	git -C $(EXEGOL_PATH) pull origin $(BRANCH)
	docker build --no-cache --pull --tag $(NAME) $(EXEGOL_PATH)

start: ## [Docker] start exegol
	docker run --interactive --tty --detach --network host --volume $(SHARE):/share --name $(CONTAINER_NAME) --hostname $(HOSTNAME) $(NAME)

start-gui: ## [in-dev][Docker] start exegol with display sharing
	docker run --interactive --tty --detach --network host --env DISPLAY=$$DISPLAY --volume /tmp/.X11-unix:/tmp/.X11-unix --volume $$XAUTH:/root/.Xauthority --volume $(SHARE):/share --name $(CONTAINER_NAME) --hostname $(HOSTNAME) $(NAME)

shell: ## [Docker] get a shell (exegol needs to be started first)
	docker exec -ti $(CONTAINER_NAME) zsh

resume: ## [Docker] resume after a pause from the saved state
	docker start $(CONTAINER_NAME)

pause: ## [Docker] pause exegol in a saved state
	docker stop $(CONTAINER_NAME)

kill: ## [Docker] reset exegol
	docker stop $(CONTAINER_NAME)
	docker rm $(CONTAINER_NAME)

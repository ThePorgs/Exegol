# Contributors documentation
Check the full contributors (up-to-date) documentation here: https://exegol.readthedocs.io/en/dev/community/contributors.html

# Wrapper & images (legacy)
- the `master` branch is the stable version. Only Pull Requests are allowed on this branch.
- the `dev` branch is used for active development. This is the bleeding-edge version, but is sometimes not as stable as the `master` (depending on the development cycle).
- the `Exegol` repository includes the exegol.py wrapper code base, and features a `exegol-docker-build` submodule tracking [Exegol-images](https://github.com/ThePorgs/Exegol-images).
- changes to the images/dockerfiles/tools/installs must be done on the [Exegol-images](https://github.com/ThePorgs/Exegol-images) repo.
- by default, the wrapper pulls the latest DockerHub pre-built image for the install and updates
- DockerHub automatic builds are configured as follows
  - `nightly` image is built using the base Dockerfile whenever a commit is made on [Exegol-images](https://github.com/ThePorgs/Exegol-images) `dev` branch.
  - `full` image is built using the base Dockerfile whenever a new tag is pushed on [Exegol-images](https://github.com/ThePorgs/Exegol-images).
  - `ad`, `osint`, `web` and `light` images are built using specific Dockerfiles whenever a new tag is pushed on [Exegol-images](https://github.com/ThePorgs/Exegol-images).
- if you want to locally build your image with your changes, run `exegol install local`. If you have local changes to the dockerfiles, they won't be overwritten.
- any addition/question/edit/pull request to the wrapper? Feel free to raise issues on this repo, or contribute on the dev branch!
- any addition/question/edit/pull request to the docker images? GOTO [Exegol-images](https://github.com/ThePorgs/Exegol-images).

Any other idea that falls outside this scope?
Any question that is left unanswered?
Feel free to reach out, I'll be happy to help and improve things, Exegol is a community-driven toolkit :rocket:

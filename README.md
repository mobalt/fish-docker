fish-docker
===========
Docker utilities and completions for fish shell.

Installation
------------

### [Fisher](https://github.com/jorgebucaran/fisher)

    fisher install mobalt/fish-docker

### Manual

    mkdir -p ~/.config/fish/completions
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/completions/docker.fish -O ~/.config/fish/completions/docker.fish
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/completions/docker-compose.fish -O ~/.config/fish/completions/docker-compose.fish

fish will show up the new completions straight away, no reload necessary.
    
Example
-------
    % docker run -[TAB]
    --attach          (Attach to stdin, stdout or stderr.)
    ...

    % docker run -t -i [TAB]
        busybox:latest             (Image)
        ubuntu:12.04               (Image)

    % docker run -t -i busybox:latest
    / #

Completion supported
--------------------
- parameters
- commands
- containers
- images
- repositories


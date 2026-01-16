fish-docker
===========
Docker utilities and completions for fish shell.

Installation
------------

### [Fisher](https://github.com/jorgebucaran/fisher)

    fisher install mobalt/fish-docker

### Manual

    mkdir -p ~/.config/fish/completions ~/.config/fish/functions
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/completions/docker.fish -O ~/.config/fish/completions/docker.fish
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/completions/docker-compose.fish -O ~/.config/fish/completions/docker-compose.fish
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/completions/docker-util.fish -O ~/.config/fish/completions/docker-util.fish
    wget https://raw.githubusercontent.com/mobalt/fish-docker/master/functions/docker-util.fish -O ~/.config/fish/functions/docker-util.fish

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

docker-util
-----------
The `docker-util` command provides additional Docker utilities.

### nsenter
Enter a container's namespace using nsenter. Useful for debugging containers with networking tools not installed in the container.

    docker-util nsenter [nsenter-args] -- <container>

Examples:

    # Enter all namespaces of a container
    docker-util nsenter --all -- my-container

    # Enter only the network namespace
    docker-util nsenter --net -- my-container

    # Enter multiple specific namespaces
    docker-util nsenter --mount --uts --ipc --net --pid -- my-container

Tab completion is supported for running containers after `--`.

### get-veth
Get the host-side veth interface name for one or more containers. Useful for debugging container networking with tools like `tcpdump`.

    docker-util get-veth <container> [container...]

Output format (tab-separated):

    container_name	docker_network	veth_name

Example:

    $ docker-util get-veth my-nginx
    my-nginx	bridge	veth006358f

Tab completion is supported for running containers.

### get-ip
Get the IP addresses for one or more containers.

    docker-util get-ip <container> [container...]

Output format (tab-separated):

    container_name	network:ip[,network:ip...]

Example:

    $ docker-util get-ip my-nginx
    my-nginx	bridge:172.17.0.2

Tab completion is supported for running containers.

Completion supported
--------------------
- parameters
- commands
- containers
- images
- repositories


# docker-util.fish - completions for docker-util command

# Helper: list running docker containers (self-contained, doesn't depend on docker.fish)
function __fish_docker_util_print_containers
    docker ps --no-trunc --filter status=running --format '{{.ID}}\n{{.Names}}' 2>/dev/null | tr ',' '\n'
end

# Helper: check if no subcommand given yet
function __fish_docker_util_no_subcommand
    not __fish_seen_subcommand_from nsenter get-veth
end

# Helper: check if get-veth subcommand is active
function __fish_docker_util_using_get_veth
    __fish_seen_subcommand_from get-veth
end

# Helper: check if -- has been seen (for nsenter container completion)
function __fish_docker_util_nsenter_needs_container
    set -l cmd (commandline -opc)
    # Must have seen 'nsenter' and '--'
    if not contains nsenter $cmd
        return 1
    end
    if not contains -- -- $cmd
        return 1
    end
    return 0
end

# Subcommand completion
complete -c docker-util -f -n __fish_docker_util_no_subcommand -a nsenter -d 'Enter container namespace with nsenter'
complete -c docker-util -f -n __fish_docker_util_no_subcommand -a get-veth -d 'Get veth interface names for containers'

# Container completion for nsenter (after --)
complete -c docker-util -f -n __fish_docker_util_nsenter_needs_container -a '(__fish_docker_util_print_containers)' -d "Container"

# Container completion for get-veth
complete -c docker-util -f -n __fish_docker_util_using_get_veth -a '(__fish_docker_util_print_containers)' -d "Container"

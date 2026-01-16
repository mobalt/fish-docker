function docker-util --description 'Docker utilities for fish shell'
    if test (count $argv) -lt 1
        echo "Usage: docker-util <subcommand> [args]"
        echo "Subcommands: nsenter"
        return 1
    end

    switch $argv[1]
        case nsenter
            __docker_util_nsenter $argv[2..-1]
        case '*'
            echo "Unknown subcommand: $argv[1]"
            return 1
    end
end

function __docker_util_nsenter --description 'Enter container namespace with nsenter'
    # Find the -- separator
    set -l dash_idx 0
    for i in (seq (count $argv))
        if test "$argv[$i]" = "--"
            set dash_idx $i
            break
        end
    end

    if test $dash_idx -eq 0
        echo "Usage: docker-util nsenter [nsenter-args] -- <container>"
        return 1
    end

    # Split args: before -- are nsenter args, after -- is container
    set -l nsenter_args
    if test $dash_idx -gt 1
        set nsenter_args $argv[1..(math $dash_idx - 1)]
    end

    set -l container_idx (math $dash_idx + 1)
    if test $container_idx -gt (count $argv)
        echo "Error: No container specified after --"
        return 1
    end
    set -l container $argv[$container_idx]

    # Get container PID
    set -l pid (docker inspect --format '{{.State.Pid}}' $container 2>/dev/null)
    if test -z "$pid" -o "$pid" = "0"
        echo "Error: Could not get PID for container '$container'"
        return 1
    end

    # Execute nsenter
    sudo nsenter --target $pid $nsenter_args
end

function docker-util --description 'Docker utilities for fish shell'
    if test (count $argv) -lt 1
        echo "Usage: docker-util <subcommand> [args]"
        echo "Subcommands: nsenter, get-veth"
        return 1
    end

    switch $argv[1]
        case nsenter
            __docker_util_nsenter $argv[2..-1]
        case get-veth
            __docker_util_get_veth $argv[2..-1]
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

function __docker_util_get_veth --description 'Get veth interface names for containers'
    if test (count $argv) -lt 1
        echo "Usage: docker-util get-veth <container> [container...]"
        return 1
    end

    for container in $argv
        # Get container name (in case ID was passed)
        set -l name (docker inspect --format '{{.Name}}' $container 2>/dev/null | string replace -r '^/' '')
        if test -z "$name"
            echo "Error: Container '$container' not found" >&2
            continue
        end

        # Get docker networks (comma-separated)
        set -l networks (docker inspect --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}},{{end}}' $container 2>/dev/null | string replace -r ',$' '')

        # Get container PID
        set -l pid (docker inspect --format '{{.State.Pid}}' $container 2>/dev/null)
        if test -z "$pid" -o "$pid" = "0"
            echo "Error: Could not get PID for container '$container'" >&2
            continue
        end

        # Get all interfaces (except lo) and find their host-side veth pairs
        # Need both --net and --mount to access /sys/class/net inside container
        set -l veths
        for iface in (sudo nsenter --target $pid --net --mount ls /sys/class/net/ 2>/dev/null)
            if test "$iface" = "lo"
                continue
            end
            # Get peer interface index from iflink
            set -l iflink (sudo nsenter --target $pid --net --mount cat /sys/class/net/$iface/iflink 2>/dev/null)
            if test -n "$iflink"
                # Find the veth on host with this index, strip @ifN suffix if present
                set -l veth (ip link show 2>/dev/null | string replace -rf "^$iflink: ([^@:]+).*" '$1')
                if test -n "$veth"
                    set -a veths $veth
                end
            end
        end

        # Output: container_name<TAB>networks<TAB>veths
        printf '%s\t%s\t%s\n' $name $networks (string join ',' $veths)
    end
end

#!/usr/bin/env python
import subprocess
import re
import os
import sys
from argparse import ArgumentParser


class Subcommand(object):
    def __init__(self, command, description, args, switches):
        self.command = command
        self.description = description
        self.args = args
        self.switches = switches


class Switch(object):
    def __init__(self, shorts, longs, description, metavar):
        self.shorts = shorts
        self.longs = longs
        self.description = description
        self.metavar = metavar

    def is_file_target(self):
        if not self.metavar:
            return False
        return self.metavar == 'FILE' or 'PATH' in self.metavar

    @property
    def fish_completion(self):
        complete_arg_spec = ['-s %s' % x for x in self.shorts]
        complete_arg_spec += ['-l %s' % x for x in self.longs]
        if not self.is_file_target():
            complete_arg_spec.append('-f')
        desc = repr(self.description)
        return '''{0} -d {1}'''.format(' '.join(complete_arg_spec), desc)


class DockerCmdLine(object):
    binary = 'docker'

    def __init__(self, docker_path):
        self.docker_path = docker_path

    def get_output(self, *args):
        cmd = [os.path.join(self.docker_path, self.binary)] + list(args)
        # docker returns non-zero exit code for some help commands so can't use subprocess.check_output here
        ps = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, _ = ps.communicate()
        out = out.decode('utf-8')
        return iter(out.splitlines())

    def parse_switch(self, line):
        line = line.strip()
        if '  ' not in line:
            # ignore continuation lines
            return None
        opt, description = re.split('  +', line, maxsplit=1)
        switches = opt.split(', ')
        metavar = None
        # handle arguments with metavar
        # Options:
        # -f, --file FILE
        for i, switch in enumerate(switches):
            if ' ' in switch:
                switches[i], metavar = switch.split(' ')
        shorts = [x[1:] for x in switches if not x.startswith('--')]
        longs = [x[2:] for x in switches if x.startswith('--')]
        return Switch(shorts, longs, description, metavar)

    def common_options(self):
        lines = self.get_output('--help')
        # skip header - look for Options: or Global Options:
        for line in lines:
            if line in ('Options:', 'Global Options:'):
                break
        else:
            return  # no options section found

        for line in lines:
            # stop at next section or empty line after options
            if line and not line.startswith(' ') and not line.startswith('-'):
                break
            switch = self.parse_switch(line)
            if switch:
                yield switch

    def subcommands(self):
        lines = self.get_output('help')
        in_commands_section = False

        for line in lines:
            # Check for any commands section header
            if line.endswith('Commands:'):
                in_commands_section = True
                continue
            # Check for non-command sections (like Global Options:)
            if line and not line.startswith(' ') and line.endswith(':'):
                in_commands_section = False
                continue
            if not in_commands_section:
                continue
            if not line.strip():
                continue
            parts = line.strip().split(None, 1)
            if len(parts) < 2:
                continue
            command, description = parts
            # Skip management commands marked with * (plugins)
            if command.endswith('*'):
                continue
            yield self.subcommand(command, description)

    def subcommand(self, command, description):
        lines = self.get_output('help', command)
        usage = None
        for line in lines:
            if line.startswith('Usage:'):
                usage = line
                break
        else:
            raise RuntimeError(
                "Can't find Usage in command: %r" % command
            )
        args = usage.split()[3:]
        if args and args[0].upper() == '[OPTIONS]':
            args = args[1:]
        if command in ('push', 'pull'):
            # improve completion for docker push/pull
            args = ['REPOSITORY|IMAGE']
        elif command == 'images':
            args = ['REPOSITORY']
        switches = []
        for line in lines:
            if not line.strip().startswith('-'):
                continue
            switch = self.parse_switch(line)
            if switch:
                switches.append(switch)
        return Subcommand(command, description, args, switches)


class DockerComposeCmdLine(DockerCmdLine):
    binary = 'docker-compose'


class BaseFishGenerator(object):
    header_text = ''

    def __init__(self, docker):
        self.docker = docker

    # Generate fish completions definitions for docker
    def generate(self):
        self.header()
        self.common_options()
        self.subcommands()

    def header(self):
        cmds = sorted(sub.command for sub in self.docker.subcommands())
        print(self.header_text.lstrip() % ' '.join(cmds))

    def common_options(self):
        print('# common options')
        for switch in self.docker.common_options():
            print('''complete -c {binary} -n '__fish_docker_no_subcommand' {completion}'''.format(
                binary=self.docker.binary,
                completion=switch.fish_completion))
        print()

    def subcommands(self):
        print('# subcommands')
        for sub in self.docker.subcommands():
            print('# %s' % sub.command)
            desc = repr(sub.description)
            print('''complete -c {binary} -f -n '__fish_docker_no_subcommand' -a {command} -d {desc}'''.format(
                binary=self.docker.binary,
                command=sub.command,
                desc=desc))
            for switch in sub.switches:
                print('''complete -c {binary} -A -n '__fish_seen_subcommand_from {command}' {completion}'''.format(
                    binary=self.docker.binary,
                    command=sub.command,
                    completion=switch.fish_completion))

            # standalone arguments
            unique = set()
            for args in sub.args:
                m = re.match(r'\[(.+)\.\.\.\]', args)
                if m:
                    # optional arguments
                    args = m.group(1)
                unique.update(args.split('|'))
            for arg in sorted(unique):
                self.process_subcommand_arg(sub, arg)
            print()
        print()

    def process_subcommand_arg(self, sub, arg):
        pass


class DockerFishGenerator(BaseFishGenerator):
    header_text = """
# docker.fish - docker completions for fish shell
#
# This file is generated by gen_docker_fish_completions.py from:
# https://github.com/mobalt/fish-docker
#
# To install the completions:
# mkdir -p ~/.config/fish/completions
# cp docker.fish ~/.config/fish/completions
#
# Completion supported:
# - parameters
# - commands
# - containers
# - images
# - repositories

function __fish_docker_no_subcommand --description 'Test if docker has yet to be given the subcommand'
    for i in (commandline -opc)
        if contains -- $i compose %s
            return 1
        end
    end
    return 0
end

function __fish_print_docker_containers --description 'Print a list of docker containers' -a select
    switch $select
        case running
            docker ps --no-trunc --filter status=running --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
        case stopped
            docker ps --no-trunc --filter status=exited --filter status=created --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
        case all
            docker ps --no-trunc --all --format '{{.ID}}\\n{{.Names}}' | tr ',' '\\n'
    end
end

function __fish_print_docker_images --description 'Print a list of docker images'
    docker images --format '{{if eq .Repository "<none>"}}{{.ID}}\\tUnnamed Image{{else}}{{.Repository}}:{{.Tag}}{{end}}'
end

function __fish_print_docker_repositories --description 'Print a list of docker repositories'
    docker images --format '{{.Repository}}' | command grep -v '<none>' | command sort | command uniq
end
"""

    def process_subcommand_arg(self, sub, arg):
        if arg == 'CONTAINER' or arg == '[CONTAINER...]':
            if sub.command in ('start', 'rm'):
                select = 'stopped'
            elif sub.command in ('commit', 'diff', 'export', 'inspect'):
                select = 'all'
            else:
                select = 'running'
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_containers {1})' -d "Container"'''.format(sub.command, select))
        elif arg == 'IMAGE':
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_images)' -d "Image"'''.format(sub.command))
        elif arg == 'REPOSITORY':
            print('''complete -c docker -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_repositories)' -d "Repository"'''.format(sub.command))

    def generate(self):
        super().generate()
        self.compose_completions()

    def compose_completions(self):
        """Generate completions for 'docker compose' subcommand."""
        print('''# compose
# Helper functions for docker compose completions
function __fish_docker_compose_no_subcommand --description 'Test if compose has yet to be given a subcommand'
    set -l cmd (commandline -opc)
    if not contains compose $cmd
        return 1
    end
    for i in $cmd
        if contains -- $i attach build commit config cp create down events exec export images kill logs ls pause port ps publish pull push restart rm run scale start stats stop top unpause up version volumes wait watch
            return 1
        end
    end
    return 0
end

function __fish_docker_compose_has_subcommand --description 'Test if compose subcommand is given' -a subcmd
    set -l cmd (commandline -opc)
    if not contains compose $cmd
        return 1
    end
    if contains -- $subcmd $cmd
        return 0
    end
    return 1
end

function __fish_print_docker_compose_services --description 'Print a list of docker compose services'
    docker compose config --services 2>/dev/null | command sort
end

# compose subcommand
complete -c docker -f -n '__fish_docker_no_subcommand' -a compose -d 'Define and run multi-container applications'

# compose options (before subcommand)
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l all-resources -f -d 'Include all resources'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l ansi -f -d 'Control ANSI output (never|always|auto)'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l compatibility -f -d 'Run in backward compatibility mode'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l dry-run -f -d 'Execute in dry run mode'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l env-file -f -d 'Alternate environment file'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -s f -l file -f -d 'Compose configuration files'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l parallel -f -d 'Control max parallelism'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l profile -f -d 'Specify a profile to enable'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l progress -f -d 'Progress output type (auto|tty|plain|json|quiet)'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -l project-directory -f -d 'Alternate working directory'
complete -c docker -A -n '__fish_docker_compose_no_subcommand' -s p -l project-name -f -d 'Project name'

# compose subcommands
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a attach -d 'Attach to a running container'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a build -d 'Build or rebuild services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a commit -d 'Create image from container changes'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a config -d 'Parse and render compose file'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a cp -d 'Copy files between container and host'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a create -d 'Create containers for a service'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a down -d 'Stop and remove containers, networks'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a events -d 'Receive real time events'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a exec -d 'Execute command in running container'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a export -d 'Export container filesystem as tar'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a images -d 'List images used by containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a kill -d 'Force stop service containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a logs -d 'View output from containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a ls -d 'List running compose projects'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a pause -d 'Pause services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a port -d 'Print public port for a port binding'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a ps -d 'List containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a pull -d 'Pull service images'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a push -d 'Push service images'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a restart -d 'Restart service containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a rm -d 'Remove stopped service containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a run -d 'Run a one-off command'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a scale -d 'Scale services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a start -d 'Start services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a stats -d 'Display container resource usage'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a stop -d 'Stop services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a top -d 'Display running processes'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a unpause -d 'Unpause services'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a up -d 'Create and start containers'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a version -d 'Show Docker Compose version'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a wait -d 'Block until containers stop'
complete -c docker -f -n '__fish_docker_compose_no_subcommand' -a watch -d 'Watch build context and rebuild'

# compose up options
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l abort-on-container-exit -f -d 'Stop all containers if any stop'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l always-recreate-deps -f -d 'Recreate dependent containers'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l attach -f -d 'Restrict attaching to specific services'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l build -f -d 'Build images before starting'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -s d -l detach -f -d 'Run containers in background'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l exit-code-from -f -d 'Return exit code from service'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l force-recreate -f -d 'Recreate containers even if unchanged'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l no-build -f -d 'Do not build images'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l no-deps -f -d 'Do not start linked services'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l no-recreate -f -d 'Do not recreate existing containers'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l no-start -f -d 'Do not start services after creating'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l pull -f -d 'Pull image policy (always|missing|never)'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l quiet-pull -f -d 'Pull without printing progress'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l remove-orphans -f -d 'Remove containers not in compose file'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l scale -f -d 'Scale service to NUM instances'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -s t -l timeout -f -d 'Shutdown timeout in seconds'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l wait -f -d 'Wait for services to be healthy'
complete -c docker -A -n '__fish_docker_compose_has_subcommand up' -l watch -f -d 'Watch source and rebuild/refresh'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand up' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose down options
complete -c docker -A -n '__fish_docker_compose_has_subcommand down' -l remove-orphans -f -d 'Remove containers not in compose file'
complete -c docker -A -n '__fish_docker_compose_has_subcommand down' -l rmi -f -d 'Remove images (all|local)'
complete -c docker -A -n '__fish_docker_compose_has_subcommand down' -s t -l timeout -f -d 'Shutdown timeout in seconds'
complete -c docker -A -n '__fish_docker_compose_has_subcommand down' -s v -l volumes -f -d 'Remove named volumes'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand down' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose logs options
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -s f -l follow -f -d 'Follow log output'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -l no-color -f -d 'Produce monochrome output'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -l no-log-prefix -f -d 'Do not print prefix in logs'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -l since -f -d 'Show logs since timestamp'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -s n -l tail -f -d 'Number of lines from end of logs'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -s t -l timestamps -f -d 'Show timestamps'
complete -c docker -A -n '__fish_docker_compose_has_subcommand logs' -l until -f -d 'Show logs before timestamp'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand logs' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose exec options
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -s d -l detach -f -d 'Run in background'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -s e -l env -f -d 'Set environment variables'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -l index -f -d 'Index of container if scaled'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -s T -l no-TTY -f -d 'Disable pseudo-TTY allocation'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -l privileged -f -d 'Give extended privileges'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -s u -l user -f -d 'Run as this user'
complete -c docker -A -n '__fish_docker_compose_has_subcommand exec' -s w -l workdir -f -d 'Working directory inside container'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand exec' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose run options
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l build -f -d 'Build image before running'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l cap-add -f -d 'Add Linux capabilities'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l cap-drop -f -d 'Drop Linux capabilities'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s d -l detach -f -d 'Run in background'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l entrypoint -f -d 'Override entrypoint'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s e -l env -f -d 'Set environment variables'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s i -l interactive -f -d 'Keep STDIN open'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s l -l label -f -d 'Add or override label'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l name -f -d 'Assign a name to the container'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s T -l no-TTY -f -d 'Disable pseudo-TTY allocation'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l no-deps -f -d 'Do not start linked services'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s p -l publish -f -d 'Publish container port'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l quiet-pull -f -d 'Pull without printing progress'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l rm -f -d 'Remove container when it exits'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l service-ports -f -d 'Run with service port mappings'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -l use-aliases -f -d 'Use service network aliases'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s u -l user -f -d 'Run as this user'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s v -l volume -f -d 'Bind mount a volume'
complete -c docker -A -n '__fish_docker_compose_has_subcommand run' -s w -l workdir -f -d 'Working directory inside container'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand run' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose ps options
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -s a -l all -f -d 'Show all containers'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l filter -f -d 'Filter output'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l format -f -d 'Format output (table|json)'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l no-trunc -f -d 'Do not truncate output'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l orphans -f -d 'Include orphaned containers'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -s q -l quiet -f -d 'Only display container IDs'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l services -f -d 'Display services'
complete -c docker -A -n '__fish_docker_compose_has_subcommand ps' -l status -f -d 'Filter by status'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand ps' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose build options
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l build-arg -f -d 'Set build-time variables'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l builder -f -d 'Set builder to use'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l memory -f -d 'Set memory limit for build'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l no-cache -f -d 'Do not use cache'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l pull -f -d 'Always pull newer image'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l push -f -d 'Push images after build'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -s q -l quiet -f -d 'Do not print anything'
complete -c docker -A -n '__fish_docker_compose_has_subcommand build' -l ssh -f -d 'Set SSH agent socket or keys'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand build' -a '(__fish_print_docker_compose_services)' -d "Service"

# compose pull/push options
complete -c docker -A -n '__fish_docker_compose_has_subcommand pull' -l ignore-buildable -f -d 'Ignore images that can be built'
complete -c docker -A -n '__fish_docker_compose_has_subcommand pull' -l ignore-pull-failures -f -d 'Pull what it can and ignore failures'
complete -c docker -A -n '__fish_docker_compose_has_subcommand pull' -l include-deps -f -d 'Also pull service dependencies'
complete -c docker -A -n '__fish_docker_compose_has_subcommand pull' -l policy -f -d 'Apply pull policy (missing|always)'
complete -c docker -A -n '__fish_docker_compose_has_subcommand pull' -s q -l quiet -f -d 'Pull without printing progress'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand pull' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -n '__fish_docker_compose_has_subcommand push' -l ignore-push-failures -f -d 'Push what it can and ignore failures'
complete -c docker -A -n '__fish_docker_compose_has_subcommand push' -l include-deps -f -d 'Also push service dependencies'
complete -c docker -A -n '__fish_docker_compose_has_subcommand push' -s q -l quiet -f -d 'Push without printing progress'
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand push' -a '(__fish_print_docker_compose_services)' -d "Service"

# Service completions for other compose subcommands
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand start' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand stop' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand restart' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand pause' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand unpause' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand kill' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand rm' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand create' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand attach' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand top' -a '(__fish_print_docker_compose_services)' -d "Service"
complete -c docker -A -f -n '__fish_docker_compose_has_subcommand events' -a '(__fish_print_docker_compose_services)' -d "Service"
''')


class DockerComposeFishGenerator(BaseFishGenerator):
    header_text = """
# docker-compose.fish - docker completions for fish shell
#
# This file is generated by gen_docker_fish_completions.py from:
# https://github.com/mobalt/fish-docker
#
# To install the completions:
# mkdir -p ~/.config/fish/completions
# cp docker-compose.fish ~/.config/fish/completions
#
# Completion supported:
# - parameters
# - commands
# - services

function __fish_docker_no_subcommand --description 'Test if docker has yet to be given the subcommand'
    for i in (commandline -opc)
        if contains -- $i %s
            return 1
        end
    end
    return 0
end

function __fish_print_docker_compose_services --description 'Print a list of docker-compose services'
    docker-compose config --services ^/dev/null | command sort
end
"""

    def process_subcommand_arg(self, sub, arg):
        if arg in ('SERVICE', '[SERVICE...]'):
            print('''complete -c docker-compose -A -f -n '__fish_seen_subcommand_from {0}' -a '(__fish_print_docker_compose_services)' -d "Service"'''.format(sub.command))



def main():
    parser = ArgumentParser()
    parser.add_argument(
        '--docker-path',
        default='/usr/bin'
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    completions_dir = os.path.join(script_dir, 'completions')
    os.makedirs(completions_dir, exist_ok=True)

    docker_fish = os.path.join(completions_dir, 'docker.fish')
    print(f'Generating {docker_fish}...')
    with open(docker_fish, 'w') as f:
        old_stdout = sys.stdout
        sys.stdout = f
        DockerFishGenerator(DockerCmdLine(args.docker_path)).generate()
        sys.stdout = old_stdout

    compose_fish = os.path.join(completions_dir, 'docker-compose.fish')
    print(f'Generating {compose_fish}...')
    with open(compose_fish, 'w') as f:
        old_stdout = sys.stdout
        sys.stdout = f
        DockerComposeFishGenerator(DockerComposeCmdLine(args.docker_path)).generate()
        sys.stdout = old_stdout

    print('Done.')

if __name__ == '__main__':
    main()

# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'attach' --description "Attach to a running container"
# complete -f -n '__fish_seen_subcommand_from attach' -c docker -l no-stdin --description "Do not attach stdin"
# complete -f -n '__fish_seen_subcommand_from attach' -c docker -l sig-proxy --description "Proxify all received signal to the process (even in non-tty mode)"

# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'build' --description "Build a container from a Dockerfile"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'commit' --description "Create a new image from a container's changes"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'cp' --description "Copy files/folders from the containers filesystem to the host path"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'diff' --description "Inspect changes on a container's filesystem"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'events' --description "Get real time events from the server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'export' --description "Stream the contents of a container as a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'history' --description "Show the history of an image"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'images' --description "List images"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'import' --description "Create a new filesystem image from the contents of a tarball"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'info' --description "Display system-wide information"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'insert' --description "Insert a file in an image"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'inspect' --description "Return low-level information on a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'kill' --description "Kill a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'load' --description "Load an image from a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'login' --description "Register or Login to the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'logs' --description "Fetch the logs of a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'port' --description "Lookup the public-facing port which is NAT-ed to PRIVATE_PORT"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'ps' --description "List containers"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'pull' --description "Pull an image or a repository from the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'push' --description "Push an image or a repository to the docker registry server"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'restart' --description "Restart a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'rm' --description "Remove one or more containers"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'rmi' --description "Remove one or more images"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'run' --description "Run a command in a new container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'save' --description "Save an image to a tar archive"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'search' --description "Search for an image in the docker index"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'start' --description "Start a stopped container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'stop' --description "Stop a running container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'tag' --description "Tag an image into a repository"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'top' --description "Lookup the running processes of a container"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'version' --description "Show the docker version information"
# complete -f -n '__fish_docker_no_subcommand' -c docker -a 'wait' --description "Block until a container stops, then print its exit code"

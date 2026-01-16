# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides fish shell completions for `docker` and `docker-compose` commands. The completions are auto-generated from Docker's help output using a Python script.

**Note:** This project is archived and no longer maintained.

## Generating Completions

The completion files in `completions/` are generated, not hand-written. To regenerate:

```bash
python gen_docker_fish_completions.py

# Use custom docker path if needed
python gen_docker_fish_completions.py --docker-path /path/to/bin
```

Output follows the Fisher plugin structure (`completions/docker.fish`, `completions/docker-compose.fish`).

## Architecture

`gen_docker_fish_completions.py` parses Docker CLI help output and generates fish completion definitions:

- **DockerCmdLine / DockerComposeCmdLine**: Execute docker/docker-compose commands and parse help text to extract subcommands and switches
- **Subcommand / Switch**: Data classes representing parsed command structure
- **DockerFishGenerator / DockerComposeFishGenerator**: Generate fish completion syntax from parsed data, including helper functions for dynamic completion of containers, images, and repositories

## Git Commits

Do NOT add `Co-Authored-By` lines to commit messages.

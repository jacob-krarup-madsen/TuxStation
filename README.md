# TuxStation

[![CI](https://github.com/dismount8645/TuxStation/actions/workflows/ci.yml/badge.svg)](https://github.com/dismount8645/TuxStation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Fedora Atomic](https://img.shields.io/badge/Fedora-Atomic-blue.svg)](https://fedoraproject.org/atomic-desktops/)

Cohesive personal **Fedora Atomic / Silverblue** desktop workstation ecosystem.

## Features

- **Atomic Image:** Bootc / Fedora Atomic base container definitions, BlueBuild recipes, disk config, cosign
- **Tuxility:** Post-install setup & automated maintenance assistant (Python CLI)
- **Dotfiles:** GNOME desktop configs, flatpak manifests, system settings

## Tech Stack

- **OS:** Fedora Atomic, bootc, BlueBuild
- **Languages:** Containerfile, Python, Shell
- **Orchestration:** \Justfile\ (just)

## Project Structure

``text
TuxStation/
├── README.md
├── LICENSE
├── .github/
├── Justfile                  # just build-image / just maintain / just dotfiles
├── image/                    # Containerfile, build_files, recipes, cosign
├── tools/
│   └── tuxility/             # Maintenance assistant
└── dotfiles/
    └── distroconfig/         # GNOME + flatpaks
``

## Quick Start

``bash
git clone https://github.com/dismount8645/TuxStation.git
cd TuxStation

just                        # list workflows
just build-image            # build Fedora Atomic container
just maintain               # run Tuxility assistant
just dotfiles               # apply GNOME & flatpaks
``

## Usage

Use \just\ workflows to build the OS image, maintain the system, or apply dotfiles. See \Justfile\ for all commands.

## Development

- Edit \image/Containerfile\ or \	ools/tuxility/\ then run \just\ tasks
- Test builds with \podman build\ or \just build-image\

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 dismount8645 (dismount8645)


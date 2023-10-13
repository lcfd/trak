<p align="center">
  <a href="https://github.com/lcfd/trak">
    <img src="./assets/banner.png" alt="Trak banner">
  </a>

  <h1 align="center">trak</h1>

  <p align="center">
    <br />
    Trak is a CLI to track the time you spend on projects, with useful reports and analytics.
    <br />
    <br />
    For freelancers, by a freelance.
    <br />
    <br />
    <a href="https://usetrak.com">Website</a>
    ·
    <a href="https://github.com/lcfd/trak/issues">Issues</a>
    ·
    <a href="https://usetrak.com/docs/">Documentation</a>
    •
    <a href="https://github.com/lcfd/trak/discussions">Feedback</a>
  </p>
</p>

## Installation

### Pypi

[On Pypi](https://pypi.org/project/trakcli/) you can find the package under the `trakcli` name.

You can install it with pip:

```bash
pip install trakcli
```

or with pipx:

```bash
pipx install trakcli
```
### Brew

TBA

### Nix

If you have [Nix](https://nixos.org/download.html) installed and flakes enabled, you can try trak using:

```bash
nix run github:lcfd/trak
```

The package will be built from source, so it might take a while.

You can pass arguments like this:

`nix run github:lcfd/trak -- --help`

### Local

Run `poetry build` and then

```bash
# x.x.x = The version you have used to do the build.
pipx install ./dist/trakcli-x.x.x-py3-none-any.whl
```

to install `trak` usign the wheel file.


## Usage

The package has the useful `--help` command that will explain all the commands.

The CLI will guide you anyway through what you should and must do with messages with specific messages.

### Basic commands

```bash
trak start <project-name>

trak stop

trak status

trak report <project-name>
```

Start trakking a project that is billable:

`trak start pasta -b`

Start tracking a project on a specific category/topic:

`trak start pasta -c rigatoni`

All the commands are described in the help command:

`trak --help`

## Starship

There is a dedicated command that ouputs clean strings for tools like Starship:

`trak status -s` or `trak status --starship`

To see the status in your terminal line open `$HOME/.config/starship.toml`
and put this snippet inside of it:

```bash
[custom.trak]
command = """ trak status -s """
when = "trak status"
shell = "sh"
```

<p align="center">
  <a href="https://github.com/lcfd/trak">
    <img src="./assets/banner.png" alt="Trak">
  </a>

  <h1 align="center">trak</h1>

  <p align="center">
    Project time tracking CLI
    <br />
    <br />
    Trak is a CLI to track the time you spend on projects, with useful reports and analytics.
    <br />
    For freelancers, by a freelance.
    <br />
    <br />
    <a href="https://usetrak.com">Website</a>
    ·
    <a href="https://github.com/lcfd/trak/issues">Issues</a>
  </p>
</p>

## Installation

### Local

`poetry build`

```bash
# x.x.x = The version you desire.
pipx install ./dist/trak-x.x.x-py3-none-any.whl
```

### Pypi



## Usage

```bash
trak start <project-name>
trak stop
trak status
trak report
```

Start trakking a project that is billable:

`trak start pasta -b`

Start tracking a project on a specific category/topic:

`trak start pasta -c rigatoni`

## Starship

`trak status -s`

In `$HOME/.config/starship.toml`:

```bash
[custom.trak]
command = """ trak status -s """
when = "trak status"
shell = "sh"
```

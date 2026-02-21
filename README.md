# Dotfiles

Multi-machine dotfiles with composable layers.

## Profiles

Each machine gets a **profile** that defines an ordered list of **layers** to
apply:

| Profile    | OS    | Layers                    |
| ---------- | ----- | ------------------------- |
| `personal` | macOS | `base`, `mac`, `personal` |
| `work`     | macOS | `base`, `mac`, `work`     |
| `remote`   | linux | `base`, `linux`, `remote` |

Layers are stowed in order. Later layers override earlier ones for the same file
path.

## Layers

| Layer      | What it contains                   |
| ---------- | ---------------------------------- |
| `base`     | Configs shared across all machines |
| `mac`      | macOS-shared configs               |
| `personal` | Personal machine configs           |
| `work`     | Work machine configs               |
| `linux`    | Linux-shared configs and packages  |
| `remote`   | Remote server configs              |

## Cloning

```bash
mkdir -p ~/dev/dotfiles && git clone https://github.com/daleal/dotfiles.git ~/dev/dotfiles
```

## Install everything

```bash
bash ~/dev/dotfiles/install
```

This runs packages, scripts, and dotfiles in order. Each step can also be run
independently:

| Step     | Command                                | What it does                          |
| -------- | -------------------------------------- | ------------------------------------- |
| Packages | `bash ~/dev/dotfiles/packages/install` | `brew` (macOS) or `apt` (Linux)       |
| Scripts  | `bash ~/dev/dotfiles/scripts/install`  | `curl \| bash` installers and similar |
| Dotfiles | `bash ~/dev/dotfiles/dotfiles/install` | Stows configs into `~` and `/`        |

All scripts auto-detect the OS, filter matching profiles, and prompt if multiple
match.

## Structure

```
dotfiles/
  layers/
    <layer>/
      user/             # Stowed into ~
      system/           # Stowed into /
profiles/
  <name>.conf           # os=macos|linux, layers=base,mac,...
packages/
  layers/
    <layer>             # Package list (one per line)
scripts/
  layers/
    <layer>/            # Executable scripts (run in order)
lib/
  profile.sh            # Shared profile selection logic
```

## Adding a new layer

1. Create `dotfiles/layers/<name>/` with `user/` and/or `system/` directories
2. Optionally add `packages/layers/<name>` with a package list
3. Optionally add executable scripts in `scripts/layers/<name>/`

## Adding a new profile

1. Create `profiles/<name>.conf` with `os=` and `layers=`
2. Layers are applied in order; later layers override earlier ones

## Manual Installation

Some configs need to be manually installed. Refer to
[the manual README](./manual/README.md) for more information.

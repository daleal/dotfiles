# Dotfiles repo — composable layers with GNU Stow

Keep the `AGENTS.md` file updated with pertinent changes to the repo and lessons learned from the developers.

## Architecture

Profiles (`profiles/<name>.conf`) define an OS and ordered layers. Layers apply
in order — later layers override earlier ones for the same file path.

| Profile    | OS    | Layers                    |
| ---------- | ----- | ------------------------- |
| `personal` | macOS | `base`, `mac`, `personal` |
| `work`     | macOS | `base`, `mac`, `work`     |
| `remote`   | linux | `base`, `linux`, `remote` |

## Where things go

Three-phase install pipeline, each independently runnable:

1. **Packages** — `packages/layers/<layer>`: one package name per line (brew on
   macOS, apt on Linux)
2. **Scripts** — `scripts/layers/<layer>/<name>`: executable bash scripts (run in
   order)
3. **Configs** — `dotfiles/layers/<layer>/user/` stowed into `~`,
   `dotfiles/layers/<layer>/system/` stowed into `/` (with sudo)

Config files mirror their target path. Example: ghostty config lives at
`dotfiles/layers/mac/user/.config/ghostty/config` and gets symlinked to
`~/.config/ghostty/config`.

## Stow behavior

- `--no-folding`: creates individual file symlinks, not directory symlinks
- `--override='.*'`: later layers can override earlier ones
- README.md files inside layer dirs are ignored by stow

## Layer responsibilities

| Layer      | Scope                                                    |
| ---------- | -------------------------------------------------------- |
| `base`     | Cross-platform configs (opencode, zed, etc.)             |
| `mac`      | macOS-only (ghostty, keyboard layout)                    |
| `personal` | Personal identity (.gitconfig with personal email)       |
| `work`     | Work identity, work-specific tooling (Linear MCP, finpr) |
| `linux`    | Linux-only packages                                      |
| `remote`   | Remote server (systemd services, nano as editor)         |

Don't mix concerns: base shouldn't have mac-specific configs, mac shouldn't have
identity-specific things.

## Conventions

- All bash scripts use `set -euo pipefail`
- Some shared logic lives in `lib/profile.sh` — touch carefully, everything sources it
- Theme consistency: One Dark Pro across tools (Zed, Ghostty, terminal)

## Adding things

- **New package**: add a line to `packages/layers/<layer>`
- **New install script**: create executable file in `scripts/layers/<layer>/`
- **New config file**: place at `dotfiles/layers/<layer>/<user|system>/<path>`
  mirroring the intended target path
- **New layer**: create dir under `dotfiles/layers/<name>/` with `user/` and/or
  `system/`, then add it to relevant profile(s)
- **New profile**: create `profiles/<name>.conf` with `os=` and `layers=`

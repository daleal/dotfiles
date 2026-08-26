# Dotfiles repo — composable layers with GNU Stow

Keep the `AGENTS.md` file updated with pertinent changes to the overarching repo structure and lessons learned from the developers.

## Architecture

Profiles (`profiles/<name>.conf`) define an OS and ordered layers. Layers apply
in order — later layers override earlier ones for the same file path.

| Profile      | OS    | Layers                        |
| ------------ | ----- | ----------------------------- |
| `personal`   | macOS | `base`, `mac`, `personal`     |
| `work`       | macOS | `base`, `mac`, `work`         |
| `neoremote`  | linux | `base`, `linux`, `neoremote`  |
| `remotework` | linux | `base`, `linux`, `remotework` |

## Where things go

Three-phase install pipeline, each independently runnable:

1. **Packages** — `packages/layers/<layer>`: one package name per line (brew on
   macOS, apt on Linux)
2. **Scripts** — `scripts/layers/<layer>/<name>`: executable bash scripts
   (sourced in filename order so environment changes persist)
3. **Configs** — `dotfiles/layers/<layer>/user/` stowed into `~`,
   `dotfiles/layers/<layer>/system/` stowed into `/` (with sudo)

Config files mirror their target path. Example: ghostty config lives at
`dotfiles/layers/mac/user/.config/ghostty/config` and gets symlinked to
`~/.config/ghostty/config`.

## Stow behavior

- `--no-folding`: creates individual file symlinks, not directory symlinks
- `--override='.*'`: later layers can override earlier ones
- README.md files inside layer dirs are ignored by stow
- Install removes unmanaged target files reported by both old and current GNU Stow diagnostics before retrying

## Layer responsibilities

| Layer        | Scope                                                       |
| ------------ | ----------------------------------------------------------- |
| `base`       | Cross-platform configs (OpenCode, Zed, etc.)                |
| `mac`        | macOS-only (Ghostty, keyboard layout)                       |
| `personal`   | Personal identity and OpenCode runtime                      |
| `work`       | Work identity and tooling (OpenCode, Linear MCP, pr, tmux)  |
| `linux`      | Linux-only packages                                         |
| `neoremote`  | Remote development (OpenCode, tmux/Smug, Git)               |
| `remotework` | Remote work tooling with work identity and project configs  |

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
- **New shell alias/function**: add a `.sh` file to
  `dotfiles/layers/<layer>/user/.config/shell/aliases.d/`. These are sourced
  automatically by a snippet injected into shell rc files by the
  `scripts/layers/base/00.shell-aliases` install script.

## Good to know

- Uninstall is intentionally config-only: top-level `uninstall` delegates to `dotfiles/uninstall`, which unstows profile layers in reverse order. It does not remove packages, reverse install scripts, or restore overwritten unmanaged files.
- `remotework` runs under Google OS Login, whose NSS users are not present in `/etc/passwd`; its Zsh setup uses `.profile` instead of `usermod`.

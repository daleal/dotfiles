# Dotfiles

These are the dotfiles for my macOS configuration

## Cloning

Clone this repo in `~/dev/dotfiles`

```bash
mkdir -p ~/dev/dotfiles && git clone https://github.com/daleal/dotfiles.git ~/dev/dotfiles
```

## Packages

Start by installing the packages. You can do this by running

```bash
bash ~/dev/dotfiles/packages/install
```

## Dotfiles

Then, setup the dotfiles by running

```bash
bash ~/dev/dotfiles/install
```

This will symlink the `user` folder into `~`, and the `system` folder into `/`.
You will need to grant admin privileges to run this command.

## Included

- [OpenCode](https://opencode.ai)
- International english keyboard with AltGr dead keys

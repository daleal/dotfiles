local_tmux() {
  if command tmux has-session 2>/dev/null; then
    command tmux attach-session
  else
    command smug start home --attach
  fi
}

# `local` is reserved by zsh, so it cannot be declared as a shell function
alias local=local_tmux

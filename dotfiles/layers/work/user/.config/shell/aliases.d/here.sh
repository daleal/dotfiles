here() {
  if command tmux has-session 2>/dev/null; then
    command tmux attach-session
  else
    command smug start home --attach
  fi
}

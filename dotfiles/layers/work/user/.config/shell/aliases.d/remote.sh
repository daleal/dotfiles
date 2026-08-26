remote() {
  command ssh -t remote.dev.fin 'if tmux has-session 2>/dev/null; then exec tmux attach-session; else exec /usr/local/bin/smug start home --attach; fi'
}

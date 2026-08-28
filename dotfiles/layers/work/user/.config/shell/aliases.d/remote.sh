remote() {
  local -a forward_options=()
  if [[ "${1:-}" == "--forward-ports" ]]; then
    local ports="${2:-}"
    if [[ $# -ne 2 || -z "$ports" ]]; then
      printf 'Usage: remote [--forward-ports PORT[,PORT...]]\n' >&2
      return 2
    fi

    local port
    while true; do
      port="${ports%%,*}"
      if [[ -z "$port" || "$port" == 0* || "$port" == *[!0-9]* ]] ||
        [[ "$port" -lt 1 || "$port" -gt 65535 ]]; then
        printf 'Usage: remote [--forward-ports PORT[,PORT...]]\n' >&2
        return 2
      fi
      forward_options+=(-L "$port:127.0.0.1:$port")

      [[ "$ports" == *,* ]] || break
      ports="${ports#*,}"
    done
  elif [[ $# -ne 0 ]]; then
    printf 'Usage: remote [--forward-ports PORT[,PORT...]]\n' >&2
    return 2
  fi

  command ssh -t "${forward_options[@]}" \
    remote.dev.fin \
    'if tmux has-session 2>/dev/null; then exec tmux attach-session; else exec /usr/local/bin/smug start home --attach; fi'
}

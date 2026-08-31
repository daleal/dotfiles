remote() {
  local -a opened_ports=(
    # Dashboard
    8888 # Application
    6006 # Storybook

    # Rails
    3000 # Application

    # Pacioli
    3001 # Sandbox
    3002 # MX
    3003 # CL

    # Luna
    3333 # API
    3334 # Admin API
    8080 # Simulator
    8081 # Admin UI
    4983 # DB Studio

    # daleal-specific
    6969 # Opentasks
  )
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
      opened_ports+=("$port")

      [[ "$ports" == *,* ]] || break
      ports="${ports#*,}"
    done
  elif [[ $# -ne 0 ]]; then
    printf 'Usage: remote [--forward-ports PORT[,PORT...]]\n' >&2
    return 2
  fi

  local port
  for port in "${opened_ports[@]}"; do
    forward_options+=(-L "$port:127.0.0.1:$port")
  done

  command ssh -t "${forward_options[@]}" \
    remote.dev.fin \
    'if tmux has-session 2>/dev/null; then exec tmux attach-session; else exec /usr/local/bin/smug start home --attach; fi'
}

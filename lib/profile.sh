#!/usr/bin/env bash

# Shared profile detection and selection logic.
# Source this file and call `select_profile "$repo_dir" [profile_name]`.
# Sets PROFILE and PROFILE_LAYERS (array).

detect_os() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux)  echo "linux" ;;
    *)      echo "unknown" ;;
  esac
}

select_profile() {
  local repo_dir="$1"
  local explicit_profile="${2:-}"

  OS="$(detect_os)"

  if [[ -n "$explicit_profile" ]]; then
    PROFILE="$explicit_profile"
  else
    local profiles=()
    for file in "$repo_dir"/profiles/*.conf; do
      [[ -f "$file" ]] || continue
      local name
      name="$(basename "$file" .conf)"
      local profile_os
      profile_os="$(grep '^os=' "$file" | cut -d= -f2)"
      if [[ "$profile_os" == "$OS" ]]; then
        profiles+=("$name")
      fi
    done

    if [[ ${#profiles[@]} -eq 0 ]]; then
      echo "No profiles found for OS '$OS'." >&2
      echo "Available profiles:" >&2
      for file in "$repo_dir"/profiles/*.conf; do
        [[ -f "$file" ]] || continue
        echo "  - $(basename "$file" .conf)" >&2
      done
      echo "" >&2
      read -rp "Enter profile name: " PROFILE
    elif [[ ${#profiles[@]} -eq 1 ]]; then
      PROFILE="${profiles[0]}"
      echo "Auto-selected profile: $PROFILE (only match for $OS)"
    else
      echo "Multiple profiles available for $OS:"
      for name in "${profiles[@]}"; do
        echo "  - $name"
      done
      echo ""
      read -rp "Enter profile name: " PROFILE
    fi
  fi

  local conf="$repo_dir/profiles/$PROFILE.conf"
  if [[ ! -f "$conf" ]]; then
    echo "Profile '$PROFILE' not found." >&2
    return 1
  fi

  # Parse layers
  IFS=',' read -ra PROFILE_LAYERS <<< "$(grep '^layers=' "$conf" | cut -d= -f2)"

  echo "Using profile: $PROFILE (layers: ${PROFILE_LAYERS[*]})"
}

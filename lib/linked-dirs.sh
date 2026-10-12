#!/usr/bin/env bash

# Directories containing a `.stow-link-dir` marker are symlinked as a whole
# instead of file by file. Stow ignores them; these helpers manage the links.
# Commands accept an optional prefix (e.g. `sudo`) as the last argument.

LINKED_DIR_MARKER=".stow-link-dir"

# Print marked directories relative to the package dir, outermost only.
find_linked_dirs() {
  local package_dir="$1"
  local previous=""

  while IFS= read -r marker; do
    local rel="${marker#"$package_dir"/}"
    rel="${rel%/"$LINKED_DIR_MARKER"}"
    if [[ -n "$previous" && "$rel" == "$previous"/* ]]; then
      continue
    fi
    printf '%s\n' "$rel"
    previous="$rel"
  done < <(find "$package_dir" -mindepth 2 -type f -name "$LINKED_DIR_MARKER" | sort)
}

# Print `--ignore` args (one per line) for marked directories.
linked_dir_ignore_args() {
  local package_dir="$1"

  while IFS= read -r rel; do
    printf '%s\n' --ignore
    printf '%s\n' "^$(printf '%s' "$rel" | sed 's/[][\.*^$+?(){}|/]/\\&/g')"
  done < <(find_linked_dirs "$package_dir")
}

# Remove per-file symlinks pointing into the repo, then empty directories.
clear_stale_linked_dir() {
  local dest="$1"
  local repo_dir="$2"
  local prefix="${3:-}"
  local link resolved

  while IFS= read -r link; do
    resolved="$(readlink -f "$link" 2>/dev/null || true)"
    if [[ "$resolved" == "$repo_dir"/* ]]; then
      $prefix rm -f "$link"
    fi
  done < <(find "$dest" -type l)

  $prefix find "$dest" -depth -type d -empty -delete
}

link_dirs() {
  local package_dir="$1"
  local target_dir="$2"
  local repo_dir="$3"
  local prefix="${4:-}"

  while IFS= read -r rel; do
    local src="$package_dir/$rel"
    local dest="$target_dir/$rel"

    if [[ -L "$dest" ]]; then
      [[ "$(readlink "$dest")" == "$src" ]] && continue
      $prefix rm -f "$dest"
    elif [[ -d "$dest" ]]; then
      clear_stale_linked_dir "$dest" "$repo_dir" "$prefix"
    elif [[ -e "$dest" ]]; then
      echo "  Removing conflicting file: $rel"
      $prefix rm -f "$dest"
    fi

    if [[ -e "$dest" ]]; then
      echo "  Warning: $dest has unmanaged contents, skipping directory link." >&2
      continue
    fi

    $prefix mkdir -p "$(dirname "$dest")"
    $prefix ln -s "$src" "$dest"
    echo "  LINK DIR: $rel => $src"
  done < <(find_linked_dirs "$package_dir")
}

unlink_dirs() {
  local package_dir="$1"
  local target_dir="$2"
  local prefix="${3:-}"

  while IFS= read -r rel; do
    local src="$package_dir/$rel"
    local dest="$target_dir/$rel"

    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
      $prefix rm -f "$dest"
      echo "  UNLINK DIR: $rel"
    fi
  done < <(find_linked_dirs "$package_dir")
}

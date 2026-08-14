#!/usr/bin/env bash
set -euo pipefail

latest_url="$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/tmux/tmux/releases/latest)"
version="${latest_url##*/}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+[a-z]?$ ]]; then
  echo "Could not resolve the latest tmux release" >&2
  return 1
fi

if [[ "$(tmux -V 2>/dev/null || true)" == "tmux $version" ]]; then
  return
fi

tmp_dir="$(mktemp -d)"
cleanup_tmux_install() {
  rm -rf "$tmp_dir"
}
trap cleanup_tmux_install EXIT HUP INT TERM

archive="tmux-$version.tar.gz"
curl -fsSL "https://github.com/tmux/tmux/releases/download/$version/$archive" \
  -o "$tmp_dir/$archive"
tar -xzf "$tmp_dir/$archive" -C "$tmp_dir"

(
  cd "$tmp_dir/tmux-$version"
  ./configure
  make -j"$(nproc)"
  sudo make install
)

cleanup_tmux_install
trap - EXIT HUP INT TERM
unset -f cleanup_tmux_install

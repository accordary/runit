#!/bin/sh
# Regression tests for scripts/runit-devices.
set -u
here=$(cd "$(dirname "$0")" && pwd)
script="$here/../scripts/runit-devices"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fail=0

check() {
  if [ "$2" = "$3" ]; then
    echo "ok $1"
  else
    echo "FAIL $1: expected [$3] got [$2]"
    fail=1
  fi
}
contains() {
  case "$2" in
    *"$3"*) echo "ok $1" ;;
    *) echo "FAIL $1: [$3] not in output:"; printf '%s\n' "$2"; fail=1 ;;
  esac
}

mkdir -p "$tmp/class/net/eth0"
printf 'net/eth0 dhcp\nnet/* netmon\n' > "$tmp/rules"
base="--root $tmp/class --rules $tmp/rules --state $tmp/state.json --dry-run"

out=$("$script" $base list); rc=$?
check "list exit 0" "$rc" "0"
contains "list shows device" "$out" "net/eth0"

out=$("$script" $base detect --commit); rc=$?
check "detect exit 0" "$rc" "0"
contains "addition reported" "$out" "+ net/eth0"
contains "dhcp started" "$out" "up dhcp: sv up /var/service/dhcp"
contains "netmon started" "$out" "up netmon: sv up /var/service/netmon"
contains "snapshot written" "$(cat "$tmp/state.json")" "net/eth0"

out=$("$script" $base detect)
contains "no change" "$out" "no device changes"

rmdir "$tmp/class/net/eth0"
out=$("$script" $base detect --commit)
contains "removal reported" "$out" "- net/eth0"
contains "dhcp stopped" "$out" "down dhcp: sv down /var/service/dhcp"

out=$("$script" $base services net/eth0 2>&1)
contains "services lists dhcp" "$out" "dhcp"
out=$("$script" $base services block/sda 2>&1); rc=$?
check "unknown device exits 1" "$rc" "1"
contains "unknown device message" "$out" "no services for block/sda"

[ "$fail" -eq 0 ] && echo "all tests passed" || echo "tests failed"
exit "$fail"

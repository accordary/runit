#!/bin/sh
# Tests for scripts/runit-logs. Run: sh tests/test-runit-logs.sh
set -e
BIN=$(cd "$(dirname "$0")/../scripts" && pwd)/runit-logs
R=$(mktemp -d); trap 'rm -rf "$R"' EXIT
fail=0
ok() { echo "ok   - $1"; }
no() { echo "FAIL - $1"; fail=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 (want [$3] got [$2])"; fi; }

mkdir -p "$R/nginx" "$R/sshd"
printf 'start ok\nerror: disk full\n' > "$R/nginx/current"
printf 'old rotated line\n' > "$R/nginx/@400000001"
printf 'sshd accepted\n' > "$R/sshd/current"
touch -d '30 days ago' "$R/nginx/@400000001"

chk "list shows both services" "$("$BIN" -r "$R" list | tail -n +2 | awk '{print $1}' | tr '\n' ' ')" "nginx sshd "
chk "tail all prints headers" "$("$BIN" -r "$R" tail | grep -c '==>')" "2"
chk "tail one service, 1 line" "$("$BIN" -r "$R" tail nginx 1 | tail -1)" "error: disk full"
chk "search finds match" "$("$BIN" -r "$R" search 'disk full' | grep -c 'nginx:current')" "1"
chk "search scoped to service" "$("$BIN" -r "$R" search accepted sshd | grep -c sshd)" "1"
"$BIN" -r "$R" search nosuchpattern >/dev/null 2>&1 && no "search exits 1 on no match" || ok "search exits 1 on no match"
"$BIN" -r "$R" retain 7 nginx >/dev/null
[ -f "$R/nginx/@400000001" ] && no "retain deletes old rotated file" || ok "retain deletes old rotated file"
[ -s "$R/nginx/current" ] && ok "retain keeps current" || no "retain keeps current"
"$BIN" -r "$R" clear nginx >/dev/null
[ -s "$R/nginx/current" ] && no "clear truncates current" || ok "clear truncates current"
[ -s "$R/sshd/current" ] && ok "clear scoped to one service" || no "clear scoped to one service"
rc=0; "$BIN" -r /nonexistent list >/dev/null 2>&1 || rc=$?; chk "missing root exits 2" "$rc" "2"
rc=0; "$BIN" -r "$R" bogus >/dev/null 2>&1 || rc=$?; chk "unknown command exits 1" "$rc" "1"
[ $fail -eq 0 ] && echo "ALL TESTS PASSED" || { echo "TESTS FAILED"; exit 1; }

# regression: unknown service must propagate exit 1 (not swallowed by for-substitution)
for c in "clear nosuch" "tail nosuch" "retain 1 nosuch" "search x nosuch"; do
  out=$("$TOOL" -r "$ROOT" $c 2>&1); rc=$?
  check "$c exits 1 on unknown service" "1" "$rc"
done

# Central logging controls

`scripts/runit-logs` gives one entry point for the service logs that `svlogd`
collects, so operators can inspect, search, age out, and clear them without
touching each service directory by hand.

## Log layout

Logs are collected under a single root (default `/var/log/runit`, override with
`RUNIT_LOG_ROOT` or `-r ROOT`). One subdirectory per service, each holding
svlogd's `current` file plus rotated `@<tai64n>` files:

    /var/log/runit/nginx/current
    /var/log/runit/nginx/@400000005f...s
    /var/log/runit/sshd/current

Point a service's `log/run` at that directory, e.g.
`exec svlogd -tt /var/log/runit/nginx`, and it is collected automatically.

## Commands

    runit-logs [-r ROOT] list                      services, total bytes, file count
    runit-logs [-r ROOT] tail [SERVICE] [N]        last N lines (default 20); all services if omitted
    runit-logs [-r ROOT] search PATTERN [SERVICE]  grep -E across current and rotated files
    runit-logs [-r ROOT] retain DAYS [SERVICE]     delete rotated files older than DAYS
    runit-logs [-r ROOT] clear [SERVICE]           truncate current, remove rotated files
    runit-logs help

## Observable behavior

- `list` prints a header row `SERVICE BYTES FILES`, then one row per service
  directory, sorted by name. BYTES is the total of `current` plus rotated files.
- `tail` prints a `==> SERVICE <==` header before each service's lines, so the
  all-services form stays readable. A service with no `current` file prints only
  the header.
- `search` prints matches as `SERVICE:FILE:LINENO:TEXT`. Exit status is 0 when
  at least one line matched and 1 when nothing matched, so it can drive scripts.
- `retain DAYS` only removes rotated `@*` files with mtime older than DAYS and
  prints each path it deletes; `current` is never touched.
- `clear` truncates `current` in place (svlogd keeps writing to the open file)
  and deletes rotated files, printing `cleared SERVICE` per service.
- Exit status 2 with `runit-logs: log root not found: ROOT` when the root is
  missing; exit 1 with usage text for an unknown command, an unknown service, or
  a missing required argument.

## Demonstration

    mkdir -p /tmp/rl/nginx
    printf 'start ok\nerror: disk full\n' > /tmp/rl/nginx/current
    scripts/runit-logs -r /tmp/rl list
    scripts/runit-logs -r /tmp/rl tail nginx 1
    scripts/runit-logs -r /tmp/rl search 'disk full'
    scripts/runit-logs -r /tmp/rl retain 7
    scripts/runit-logs -r /tmp/rl clear nginx

## Tests

    sh tests/test-runit-logs.sh

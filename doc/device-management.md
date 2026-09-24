# Device management (runit-devices)

`scripts/runit-devices` detects device additions and removals and manages the
runit services associated with those devices.

## Installation

    install -m 0755 scripts/runit-devices /usr/bin/runit-devices
    install -d /var/lib/runit
    install -m 0644 your-rules /etc/runit/devices.rules

Requires python3 (>= 3.6) and, for live service control, `sv` on PATH.

## Rules file

One rule per line: a device glob and a service name. `#` starts a comment.

    net/eth0   dhcp
    net/*      netmon
    block/sd*  disk-monitor

## Usage

    runit-devices [--root DIR] [--state FILE] [--rules FILE] [--svdir DIR] [--dry-run] COMMAND

    list                    enumerate devices under --root
    detect [--commit]       diff against the saved snapshot, act on changes,
                            and with --commit write the new snapshot
    services DEVICE         print services matching DEVICE

Defaults: `--root /sys/class`, `--state /var/lib/runit/devices.json`,
`--svdir /var/service`.

## Demonstration

    printf 'net/eth0 dhcp\nnet/* netmon\n' > /tmp/rules
    mkdir -p /tmp/class/net/eth0
    runit-devices --root /tmp/class --rules /tmp/rules --state /tmp/state.json \
      --dry-run detect --commit
    rmdir /tmp/class/net/eth0
    runit-devices --root /tmp/class --rules /tmp/rules --state /tmp/state.json \
      --dry-run detect --commit

## Observable behavior

* `list` prints one device path per line, sorted, relative to `--root`.
* `detect` prints `+ DEVICE` for additions and `- DEVICE` for removals, each
  followed by indented `up SERVICE: ...` / `down SERVICE: ...` lines for every
  matching rule; a device matching several rules gets one line per service.
* With no changes it prints `no device changes`.
* `--dry-run` prints the `sv` command that would run without executing it.
* The snapshot is only rewritten with `--commit`, written atomically via a
  `.tmp` file and `os.replace`; a missing or unreadable snapshot is treated as
  an empty device set, so the first run reports every device as an addition.
* Exit status: 0 on success, 1 if any `sv` invocation fails or if `services`
  finds no matching rule (message on stderr).

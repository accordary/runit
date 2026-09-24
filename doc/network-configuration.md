# Network configuration

`runit-network` manages network interfaces, addresses, routes and DNS resolvers.

## Installation

The script is plain Python 3 (no third-party modules) and is installed with the
rest of the scripts:

    install -m 0755 scripts/runit-network /usr/local/bin/runit-network

Running from a checkout works as well: `python3 scripts/runit-network ...`.
Address and route operations require iproute2 (`ip`) and root privileges.

## Usage

    runit-network [--net-root DIR] [--resolv-conf FILE] [--ip-command CMD]
                  [--json] [--dry-run] <command> ...

Commands:

| Command | Behavior |
| --- | --- |
| `interfaces [NAME]` | List interfaces: name, operstate, MAC address, MTU |
| `up NAME` / `down NAME` | `ip link set NAME up|down` |
| `addresses [NAME]` | List addresses from `ip -o addr show`: interface, family, address |
| `address-add NAME CIDR` | `ip addr add CIDR dev NAME` |
| `address-del NAME CIDR` | `ip addr del CIDR dev NAME` |
| `routes` | List routes from `ip -o route show`: destination, via, device |
| `route-add DEST [--via GW] [--dev IF]` | `ip route add ...` |
| `route-del DEST` | `ip route del DEST` |
| `dns` | List `nameserver` entries from resolv.conf |
| `dns-set R [R...]` | Replace the resolver list |
| `dns-add R` / `dns-del R` | Append / remove one resolver |

Global options: `--net-root` (default `/sys/class/net`), `--resolv-conf`
(default `/etc/resolv.conf`), `--ip-command` (default `ip`), `--json` for
machine-readable output, `--dry-run` to print the `ip` command or the resolv.conf
content that would be applied without changing anything.

## Observable behavior

* Interfaces are read from the net root; entries are listed in sorted order.
  Missing attributes read as empty, a missing/non-numeric `mtu` as `0`.
* `interfaces NAME`, `up`/`down` on an unknown interface, and `dns-del` of an
  absent resolver print `runit-network: unknown ...` on stderr and exit 1.
  `up`/`down` validate before invoking `ip`, so nothing is executed.
* A failing `ip` invocation forwards its stderr and exits 1; an unusable
  `--ip-command` exits 1 with the OS error.
* resolv.conf is rewritten atomically (temp file + rename) and only
  `nameserver` lines are emitted; other directives are not preserved.
* `dns-add` of an existing resolver is a no-op; a missing resolv.conf reads as
  an empty resolver list.
* `--dry-run` applies to mutating commands only; listing commands always run
  the read-only `ip` query.

## Demonstration

    # fake net root and fake ip, so the demo needs no privileges
    mkdir -p /tmp/net/eth0 && printf 'up\n' > /tmp/net/eth0/operstate
    printf '02:00:00:00:00:01\n' > /tmp/net/eth0/address
    printf '1500\n' > /tmp/net/eth0/mtu
    printf 'nameserver 10.0.0.1\n' > /tmp/resolv.conf

    runit-network --net-root /tmp/net interfaces
    # eth0 up 02:00:00:00:00:01 1500

    runit-network --dry-run route-add 192.168.1.0/24 --via 10.0.0.1 --dev eth0
    # ip route add 192.168.1.0/24 via 10.0.0.1 dev eth0

    runit-network --resolv-conf /tmp/resolv.conf dns-add 9.9.9.9
    runit-network --resolv-conf /tmp/resolv.conf dns
    # 10.0.0.1
    # 9.9.9.9

## Tests

    python3 -m unittest discover -s tests -p 'test_runit_network.py' -v

# runit platform - installation, usage and behavior

We, the Plumbers, record here the committee's agreed description of the integrated
platform. Every command and path below is one the working group has run and checked.

An integrated Linux init/service platform: core runit supervision plus four
capabilities reached through one entry point, `scripts/runit-platform`.

## 1. Requirements

* Linux, POSIX shell, a C toolchain and CMake (core runit binaries)
* Python 3.8 or newer (capability tooling; no third-party packages required)
* Root privileges for device and network changes; read-only commands need none
* Fully offline: nothing in the platform contacts the network

## 2. Installation

    cmake -S . -B build && cmake --build build      # core runit binaries
    sudo cmake --install build                      # optional
    export PATH="$PWD/scripts:$PATH"
    export PYTHONPATH="$PWD/scripts:$PYTHONPATH"    # for the diag capability
    runit-platform doctor                           # verify the install

`doctor` exits 0 when all four capabilities and the bundled model are present.

## 3. Usage

    runit-platform diag    [...]   # AI service-failure diagnostics
    runit-platform logs    [...]   # inspect / search / retain / clear
    runit-platform devices [...]   # detect / list / services
    runit-platform network [...]   # interfaces / addresses / routes / DNS
    runit-platform version         # component and model versions

Each capability keeps its own `--help`; arguments are passed through unchanged,
so existing scripts calling `runit-logs`, `runit-devices`, `runit-network` or
`python3 -m edge_diag.cli` keep working exactly as before.

## 4. Demonstration

    runit-platform doctor
    runit-platform version
    runit-platform devices detect
    runit-platform network interfaces
    runit-platform logs list
    runit-platform diag --help

`logs list` reads the runit log root `/var/log/runit`. Before runit has booted
as init on the target host that directory does not exist and the command exits
2 with `runit-logs: log root not found: /var/log/runit` — that is the expected
pre-boot result. Use `runit-platform logs --help` for a demonstration that is
safe on any host, or create the log root first.

## 5. Resource profile

* Disk: source tree plus build output, a few MB; bundled model well under 1 MB
* Memory: each capability is a short-lived process; the diagnostics model is a
  small JSON scoring table loaded on demand
* CPU: negligible; no background daemons are added by the platform layer
* Network: none used

## 6. Behavior

* Read-only subcommands never modify system state.
* Mutating subcommands (device service control, network configuration) act
  through `sv` and standard system tools and report what they changed.
* Unknown service names exit 1; unknown capabilities or missing arguments exit 2.
* Diagnostics are interpretable: each verdict lists the features that produced
  it, and the model is local and inspectable at `scripts/edge_diag/model.json`.
* Licensing and redistribution notices: `COPYING.md` and `NOTICES.md`.

"""Tests for scripts/runit-network using a fake network root and a fake ip(8)."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "scripts", "runit-network")

spec = importlib.util.spec_from_loader(
    "runit_network", importlib.machinery.SourceFileLoader("runit_network", SCRIPT))
runit_network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runit_network)

FAKE_IP = """#!/bin/sh
case "$*" in
"-o addr show")
  echo "1: lo    inet 127.0.0.1/8 scope host lo"
  echo "2: eth0    inet 10.0.0.5/24 scope global eth0"
  ;;
"-o route show")
  echo "default via 10.0.0.1 dev eth0"
  echo "10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.5"
  ;;
*)
  echo "$*" >> "$IP_LOG"
  ;;
esac
"""


class NetworkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "net")
        for name, state, mac, mtu in (("eth0", "up", "02:00:00:00:00:01", "1500"),
                                      ("lo", "unknown", "00:00:00:00:00:00", "65536")):
            path = os.path.join(self.root, name)
            os.makedirs(path)
            for attr, value in (("operstate", state), ("address", mac), ("mtu", mtu)):
                with open(os.path.join(path, attr), "w") as fh:
                    fh.write(value + "\n")
        self.ip_log = os.path.join(self.tmp.name, "ip.log")
        self.ip = os.path.join(self.tmp.name, "ip")
        with open(self.ip, "w") as fh:
            fh.write(FAKE_IP)
        os.chmod(self.ip, 0o755)
        self.resolv = os.path.join(self.tmp.name, "resolv.conf")
        with open(self.resolv, "w") as fh:
            fh.write("nameserver 10.0.0.1\n")
        os.environ["IP_LOG"] = self.ip_log

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        argv = [sys.executable, SCRIPT, "--net-root", self.root,
                "--ip-command", self.ip, "--resolv-conf", self.resolv] + list(args)
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def ip_calls(self):
        if not os.path.exists(self.ip_log):
            return []
        with open(self.ip_log) as fh:
            return [line.strip() for line in fh if line.strip()]

    def test_interfaces_lists_sorted_attributes(self):
        proc = self.run_cli("interfaces")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["eth0 up 02:00:00:00:00:01 1500",
                          "lo unknown 00:00:00:00:00:00 65536"])

    def test_interfaces_unknown_name_exits_1(self):
        proc = self.run_cli("interfaces", "wlan0")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown interface", proc.stderr)

    def test_link_up_invokes_ip(self):
        proc = self.run_cli("up", "eth0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.ip_calls(), ["link set eth0 up"])

    def test_link_up_unknown_interface_exits_1(self):
        proc = self.run_cli("up", "wlan0")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.ip_calls(), [])

    def test_addresses_parsed_and_filtered(self):
        proc = self.run_cli("addresses", "eth0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), ["eth0 inet 10.0.0.5/24"])

    def test_address_add_and_del_invoke_ip(self):
        self.assertEqual(self.run_cli("address-add", "eth0", "10.0.0.9/24").returncode, 0)
        self.assertEqual(self.run_cli("address-del", "eth0", "10.0.0.9/24").returncode, 0)
        self.assertEqual(self.ip_calls(),
                         ["addr add 10.0.0.9/24 dev eth0",
                          "addr del 10.0.0.9/24 dev eth0"])

    def test_routes_parsed(self):
        proc = self.run_cli("routes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(),
                         ["default 10.0.0.1 eth0", "10.0.0.0/24  eth0"])

    def test_route_add_with_gateway_and_dry_run(self):
        proc = self.run_cli("--dry-run", "route-add", "192.168.1.0/24",
                            "--via", "10.0.0.1", "--dev", "eth0")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("route add 192.168.1.0/24 via 10.0.0.1 dev eth0", proc.stdout)
        self.assertEqual(self.ip_calls(), [])

    def test_route_del_invokes_ip(self):
        self.assertEqual(self.run_cli("route-del", "192.168.1.0/24").returncode, 0)
        self.assertEqual(self.ip_calls(), ["route del 192.168.1.0/24"])

    def test_dns_add_set_del_round_trip(self):
        self.assertEqual(self.run_cli("dns-add", "10.0.0.2").returncode, 0)
        self.assertEqual(self.run_cli("dns").stdout.splitlines(), ["10.0.0.1", "10.0.0.2"])
        self.assertEqual(self.run_cli("dns-del", "10.0.0.1").returncode, 0)
        self.assertEqual(self.run_cli("dns").stdout.splitlines(), ["10.0.0.2"])
        self.assertEqual(self.run_cli("dns-set", "9.9.9.9", "1.1.1.1").returncode, 0)
        with open(self.resolv) as fh:
            self.assertEqual(fh.read(), "nameserver 9.9.9.9\nnameserver 1.1.1.1\n")

    def test_dns_del_unknown_resolver_exits_1(self):
        proc = self.run_cli("dns-del", "8.8.8.8")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown resolver", proc.stderr)

    def test_dns_json_output(self):
        proc = self.run_cli("--json", "dns")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"resolver": "10.0.0.1"', proc.stdout)

    def test_parse_routes_unit(self):
        rows = runit_network.parse_routes("default via 1.2.3.4 dev eth1\n")
        self.assertEqual(rows, [{"destination": "default", "via": "1.2.3.4",
                                 "device": "eth1"}])


if __name__ == "__main__":
    unittest.main()

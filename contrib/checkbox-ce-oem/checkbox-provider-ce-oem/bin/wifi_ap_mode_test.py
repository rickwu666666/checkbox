#!/usr/bin/env python3
import argparse
import subprocess
import sys
import logging
from rpyc_client import rpyc_client

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class WiFiManager:
    def __init__(
        self,
        interface,
        type,
        mode,
        band,
        channel,
        key_mgmt,
        group,
        ssid,
        ssid_pwd,
        peer,
    ):
        self._command = "nmcli"
        self.interface = interface
        self.type = type
        self.mode = mode
        self.band = band
        self.channel = channel
        self.key_mgmt = key_mgmt
        self.group = group
        self.ssid = ssid if ssid is not None else "qa-test-ssid"
        self.ssid_pwd = ssid_pwd if ssid_pwd is not None else "insecure"
        self.peer = peer
        self.conname = "qa-test-ap"

    def run_command(self, command):
        try:
            subprocess.check_output(
                command, shell=True, stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            logging.error("Command failed: %s", e.output.decode())
            sys.exit(1)

    def init_conn(self):
        logging.info("Initializing connection")
        if self.type == "wifi":
            self.run_command(
                "{} c add type {} ifname {} con-name {} \
                    autoconnect no wifi.ssid {} wifi.mode \
                    {} ipv4.method shared".format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.ssid,
                    self.mode,
                )
            )
        if self.type == "wifi-p2p":
            self.run_command(
                "{} c add type {} ifname {} con-name {} wifi-p2p.peer {}".
                format(
                    self._command,
                    self.type,
                    self.interface,
                    self.conname,
                    self.peer,
                )
            )

    def set_band_channel(self):
        self.run_command(
            "{} c modify {} wifi.band {} wifi.channel {}".format(
                self._command, self.conname, self.band, self.channel
            )
        )

    def set_secured(self):
        self.run_command(
            "{} c modify {} wifi-sec.key-mgmt {} wifi-sec.psk {}\
                  wifi-sec.group {}".format(
                self._command,
                self.conname,
                self.key_mgmt,
                self.ssid_pwd,
                self.group,
            )
        )

    def up_conn(self):
        self.run_command("{} c up {}".format(self._command, self.conname))

    def del_conn(self):
        self.run_command("{} c delete {}".format(self._command, self.conname))

    def __enter__(self):
        self.init_conn()
        if self.type == "wifi":
            self.set_band_channel()
        logging.info("Initialized connection success!")

    def __exit__(self, exc_type, exc_value, traceback):
        self.del_conn()


def ping_test(manager, target_ip):
    logging.info("Attempting to ping HOST...")
    try:
        result = rpyc_client(
            target_ip,
            "wifi_ap_connect",
            "connect_ap",
            "wlan0",
            manager.ssid,
            manager.ssid_pwd,
        )
        logging.info(result.returncode)

    except Exception as e:
        raise logging.error("Ping test to DUT AP fail: s%", e)


def main():
    parser = argparse.ArgumentParser(description="WiFi test")

    parser.add_argument(
        "--type", required=False, default="wifi", help="Connection type."
    )
    parser.add_argument(
        "--mode",
        choices=["ap", "adhoc"],
        required=False,
        help="WiFi mode: ap or adhoc",
    )
    parser.add_argument(
        "--interface", required=False, help="WiFi interface to use"
    )
    parser.add_argument("--band", required=False, help="WiFi band to use")
    parser.add_argument(
        "--channel", required=False, help="WiFi channel to use"
    )
    parser.add_argument(
        "--keymgmt", required=False, help="Key management method"
    )
    parser.add_argument(
        "--group", required=False, help="Group key management method"
    )
    parser.add_argument("--ssid", required=False, help="SSID for AP mode")
    parser.add_argument("--ssid-pwd", required=False, help="Password for SSID")
    parser.add_argument(
        "--peer", required=False, help="MAC address for p2p peer"
    )
    parser.add_argument(
        "--target-ip",
        required=True,
        help="IP address of the rpyc RPyC server to connect to",
    )

    args = parser.parse_args()

    manager = WiFiManager(
        args.interface,
        args.type,
        args.mode,
        args.band,
        args.channel,
        args.keymgmt,
        args.group,
        args.ssid,
        args.ssid_pwd,
        args.peer,
    )
    with manager:
        if args.keymgmt is not None:
            manager.set_secured()
        manager.up_conn()
        ping_test(manager, args.target_ip)


if __name__ == "__main__":
    main()

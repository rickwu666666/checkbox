#!/usr/bin/env python3
import re
import checkbox_support.bt_helper as bt_helper
import time
import argparse
import subprocess
import os
import fcntl
from xml.dom import minidom

# UUID of bluetooth profile mapping
UUID = {
    "A2DP_SOURCE": "0000110a-0000-1000-8000-00805f9b34fb",
    "A2DP_SINK": "0000110b-0000-1000-8000-00805f9b34fb",
    "HFP_HS": "0000111e-0000-1000-8000-00805f9b34fb",
    "HFP_AG": "0000111f-0000-1000-8000-00805f9b34fb",
    "HID": "00001124-0000-1000-8000-00805f9b34fb",
    "HOGP": "00001812-0000-1000-8000-00805f9b34fb"
    }


class ExtendBtDevice(bt_helper.BtDevice):
    def __init__(self, dbus_iface, bt_mgr):
        super().__init__(dbus_iface, bt_mgr)

    def pair(self):
        """Pair the device.

        This function will try pairing with the device and block until device
        is paired, error occured or default timeout elapsed (whichever comes
        first).
        """
        self._prop_if.Set(bt_helper.DEVICE_IFACE, "Trusted", True)
        self._if.Pair(
            reply_handler=self._pair_ok, error_handler=self._pair_error
        )
        self._bt_mgr.wait()
        if self._pair_outcome:
            raise bt_helper.BtException(self._pair_outcome)


class ExtendBtManager(bt_helper.BtManager):
    def __init__(self, adapter=None, verbose=False):
        super().__init__(verbose)
        self.selected_adapter = None
        if adapter:
            self.get_bt_adapter_by_name(adapter)
            print("Selected adapter: {}".format(adapter))
        else:
            print(
                "No Bluetooth adapter selected."
                "Please select an adapter first."
            )

    def get_bt_devices(self, category=bt_helper.BT_ANY, filters={}):
        """Yields ExtendBtDevice objects currently known to the system.

        filters - specifies the characteristics of that a BT device must have
        to be yielded. The keys of filters dictionary represent names of
        parameters (as specified by the bluetooth DBus Api and represented by
        DBus proxy object), and its values must match proxy values.
        I.e. {'Paired': False}. For a full list of Parameters see:
        http://git.kernel.org/cgit/bluetooth/bluez.git/tree/doc/device-api.txt

        Note that this function returns objects corresponding to BT devices
        that were seen last time scanning was done."""
        for device in self._get_objects_by_iface(bt_helper.DEVICE_IFACE):
            obj = self.get_object_by_path(device.object_path)[bt_helper.DEVICE_IFACE]
            try:
                if category != bt_helper.BT_ANY:
                    if obj["Class"] != category:
                        continue
                rejected = False
                for filter in filters:
                    if obj[filter] != filters[filter]:
                        rejected = True
                        break
                if rejected:
                    continue
                yield ExtendBtDevice(
                    bt_helper.dbus.Interface(
                        device,
                        bt_helper.DEVICE_IFACE), self)
            except KeyError as exc:
                bt_helper.logger.info(
                    "Property %s not found on device %s",
                    exc,
                    device.object_path,
                )
                continue

    def power_on(self):
        print("Powering on Bluetooth...")
        self.selected_adapter.set_bool_prop("Powered", True)

    def power_off(self):
        print("Powering off Bluetooth...")
        self.selected_adapter.set_bool_prop("Powered", False)

    def get_power_state(self):
        power_state = self.selected_adapter._prop_if.Get(
            bt_helper.ADAPTER_IFACE, "Powered"
        )
        print("Current power state: {}".format("on" if power_state else "off"))
        return power_state

    def set_bt_name(self, name):
        self.selected_adapter._prop_if.Set(
            bt_helper.ADAPTER_IFACE, "Alias", bt_helper.dbus.String(name)
        )
        print("Bluetooth device name set to: {}".format(name))

    def get_bt_name(self):
        name = self.selected_adapter._prop_if.Get(
            bt_helper.ADAPTER_IFACE, "Alias"
        )
        print("Current Bluetooth device name: {}".format(name))
        return name

    def get_bt_adapter_by_name(self, target):
        for adapter in self._get_objects_by_iface(bt_helper.ADAPTER_IFACE):
            path = adapter.object_path
            if path.endswith(target):
                self.selected_adapter = bt_helper.BtAdapter(
                    bt_helper.dbus.Interface(adapter, bt_helper.ADAPTER_IFACE),
                    self,
                )
                return self.selected_adapter
        raise bt_helper.BtException("Adapter {} not found".format(target))

    def ensure_adapters_off(self):
        for adapter in self.get_bt_adapters():
            self.selected_adapter = adapter
            self.power_off()

    def unpair_all(self):
        paired_devices = self.get_bt_devices(
            category=bt_helper.BT_ANY,
            filters={"Paired": True},
        )
        for device in paired_devices:
            try:
                print("Unpairing", device)
                device.unpair()
            except bt_helper.BtException as exc:
                print("Unpairing failed", exc)

    def connect_profile(self, device, profile_uuid):
        if not device:
            raise bt_helper.BtException("No device selected to show profiles.")
        print(
            "Attempting to connect to {} using profile {}".format(
                device, profile_uuid
            )
        )

        try:
            device_path = device._if.object_path
            device_proxy = self._bus.get_object("org.bluez", device_path)
            device_interface = bt_helper.dbus.Interface(
                device_proxy, bt_helper.DEVICE_IFACE
            )
            device_interface.ConnectProfile(profile_uuid)

            print(
                "Connected to {} using profile {}".format(device, profile_uuid)
            )

        except bt_helper.dbus.exceptions.DBusException as exc:
            print(
                "Failed to connect to {} using profile {}: {}".format(
                    device, profile_uuid, exc
                )
            )
            raise SystemError("Profile connection failed!")

    def show_device_profiles(self, device):
        if not device:
            raise bt_helper.BtException("No device selected to show profiles.")
        try:
            connected_uuids = device._prop_if.Get(
                bt_helper.DEVICE_IFACE, "UUIDs"
            )

            print("Device profiles for {}:".format(device))
            for uuid in connected_uuids:
                print(" - {}".format(uuid))

            return connected_uuids

        except bt_helper.dbus.exceptions.DBusException as exc:
            print("Failed to retrieve profiles for {}: {}".format(device, exc))
            raise SystemError("Could not retrieve device profiles!")

    def show_adapter_profiles(self):
        try:
            supported_uuids = self.selected_adapter._prop_if.Get(
                bt_helper.ADAPTER_IFACE, "UUIDs"
            )

            print(
                "Supported profiles for adapter {}:".format(
                    self.selected_adapter
                )
            )
            for uuid in supported_uuids:
                print(" - {}".format(uuid))

            return supported_uuids

        except bt_helper.dbus.exceptions.DBusException as exc:
            print(
                "Failed to retrieve profiles for adapter {}: {}".format(
                    self.selected_adapter, exc
                )
            )
            raise SystemError("Could not retrieve adapter profiles!")

    def find_media_transports(self, device):
        """Find the media transport paths (e.g., `sep6/fd10`) for the device."""
        try:
            device_path = device._if.object_path
            device_proxy = self._bus.get_object("org.bluez", device_path)
            device_interface = bt_helper.dbus.Interface(
                device_proxy, "org.freedesktop.DBus.Introspectable"
            )
            device_nodes = minidom.parseString(device_interface.Introspect())
            device_nodes = device_nodes.documentElement
            for node in device_nodes.getElementsByTagName("node"):
                node_path = "{}/{}".format(
                    device_path, node.getAttribute("name"))
                node_proxy = self._bus.get_object("org.bluez", node_path)
                node_interface = bt_helper.dbus.Interface(
                    node_proxy, "org.freedesktop.DBus.Introspectable"
                )
                file_descriptor = minidom.parseString(
                    node_interface.Introspect())
                file_descriptor = file_descriptor.documentElement
                for fd in file_descriptor.getElementsByTagName("node"):
                    if "fd" in fd.getAttribute("name"):
                        return ("{}/{}".format(
                            node_path, fd.getAttribute("name")))
            raise bt_helper.BtException("Not found file descriptor!!")
        except bt_helper.dbus.exceptions.DBusException as e:
            raise bt_helper.BtException(e)

    def acquire_media_transports(self, device):
        """Acquire all media transports for a given device."""
        media_transports = self.find_media_transports(device)
        device_proxy = self._bus.get_object("org.bluez", media_transports)
        media_transport_interface = bt_helper.dbus.Interface(
            device_proxy, "org.bluez.MediaTransport1"
        )
        try:
            print("Acquire media transport on path: {}".
                  format(media_transports))
            self.fd, read_mtu, write_mtu = media_transport_interface.Acquire()
            return (self.fd, read_mtu, write_mtu)
        except bt_helper.dbus.exceptions.DBusException as e:
            raise bt_helper.BtException(e)

    def play_audio(self, audio_data="/home/u/Front_Center.wav"):
        # Assuming audio_data is prepared to write to the acquired fd
        os.write(self.fd, audio_data)


def audio_play(fd, write_mtu):
    try:
        print("Attempting to play sound ...")
        subprocess.run(['alsa_test', 'playback', '-d', '5'], check=True)
    except subprocess.CalledProcessError as e:
        print("Error playing audio file: {}".format(e))

    # fd = 4
    # flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    # fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    # with open("/home/u/Front_Center.wav", 'rb') as pcm_file:
    #     pcm_file.seek(44)
    #     while True:
    #         data = pcm_file.read(write_mtu)  # Read exactly write_mtu bytes
    #         if not data:
    #             print("End of audio file.")
    #             break

    #         # If data is smaller than write_mtu, pad it
    #         if len(data) < write_mtu:
    #             data += b'\x00' * (write_mtu - len(data))  # Zero-pad to match write_mtu

    #         try:
    #             # Write the raw PCM data to the Bluetooth file descriptor
    #             os.write(fd, data)
    #             time.sleep(0.01)  # Adjust the sleep to control playback speed
    #         except BlockingIOError:
    #             # Handle non-blocking behavior
    #             pass


def test_hfp_ag(manager, target=None):
    profile = "HFP_AG"
    print("Starting Bluetooth {} profile test ...".
          format(profile)
          )
    if manager.get_power_state() == 0:
        manager.power_on()
    # print("Attempting to unpair all devices ... ")
    # manager.unpair_all()
    # time.sleep(10)  # To wait untill devices removed
    # print("Attempting to scan target device ...")
    target_devices = manager.get_devices()
    for device in target_devices:
        if re.search(target, device.address):
            print("Find target device {}".format(device))
            print("Attempting to pair with {}".format(device.address))
            try:
                # device.pair()
                # print("Paired!")
                # time.sleep(5)
                # manager.show_device_profiles(device)
                # manager.connect_profile(device, UUID["HFP_HS"])
                # print("Connected profile!")
                # # time.sleep(5)
                fd, read_mtu, write_mtu = manager.acquire_media_transports(
                    device)
                print("Attempting to play sound ...")
                manager.play_audio(fd)
                # print("Attempting to unpair with {}".format(device.address))
                # try:
                #     device.unpair()
                #     print("Unpair successful.")
                # except Exception:
                #     raise SystemError("Unpair device failed!")
            except Exception:
                raise bt_helper.BtException("Device pair failed!")


def main():
    parser = argparse.ArgumentParser(description="Bluetooth Manager Script")
    parser.add_argument(
        "--adapter",
        type=str,
        required=True,
        help="The Bluetooth adapter to use (e.g., hci0)",
    )
    parser.add_argument(
        "--target",
        type=str,
        required=False,
        help="The MAC address of the target Bluetooth device",
    )
    parser.add_argument(
        "--function",
        type=str,
        required=False,
        choices=["test_bt_basic", "another_test_function"],
        help="The test function to run",
    )
    args = parser.parse_args()
    bt_manager = ExtendBtManager(adapter=args.adapter)
    test_hfp_ag(bt_manager, args.target)
    # if args.function == "test_bt_basic":
    #     test_bt_basic(bt_manager, args.interface, args.target)
    # elif args.function == "another_test_function":
    #     another_test_function(bt_manager, args.interface, args.target)


if __name__ == "__main__":
    main()
# 94:DB:56:83:CB:FF
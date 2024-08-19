#!/usr/bin/env python3
import re
import checkbox_support.bt_helper as bt_helper
import random
import string
import time
import argparse


# UUID of bluetooth profile
A2DP_SOURCE_UUID = "0000110a-0000-1000-8000-00805f9b34fb"
A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"
HFP_HS_UUID = "0000111e-0000-1000-8000-00805f9b34fb"
HFP_AG_UUID = "0000111f-0000-1000-8000-00805f9b34fb"
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
HOGP_UUID = "00001812-0000-1000-8000-00805f9b34fb"


class ExtendBtManager(bt_helper.BtManager):
    def __init__(self, verbose=False):
        super().__init__(verbose)
        self.selected_adapter = None

    def power_on(self):
        if self.selected_adapter is None:
            print(
                "No Bluetooth adapter selected. Please select an adapter first."
            )
            return
        print("Powering on Bluetooth...")
        self.selected_adapter.set_bool_prop("Powered", True)

    def power_off(self):
        if self.selected_adapter is None:
            print(
                "No Bluetooth adapter selected. Please select an adapter first."
            )
            return
        print("Powering off Bluetooth...")
        self.selected_adapter.set_bool_prop("Powered", False)

    def get_power_state(self):
        """Retrieve and print the current power state of the Bluetooth adapter."""
        if self.selected_adapter is None:
            print(
                "No Bluetooth adapter selected. Please select an adapter first."
            )
            return None

        power_state = self.selected_adapter._prop_if.Get(
            bt_helper.ADAPTER_IFACE, "Powered"
        )
        print("Current power state: {}".format("on" if power_state else "off"))
        return power_state

    def set_bt_name(self, name):
        """Set the Bluetooth device name."""
        if self.selected_adapter is None:
            print(
                "No Bluetooth adapter selected. Please select an adapter first."
            )
            return

        self.selected_adapter._prop_if.Set(
            bt_helper.ADAPTER_IFACE, "Alias", bt_helper.dbus.String(name)
        )
        print("Bluetooth device name set to: {}".format(name))

    def get_bt_name(self):
        """Get the current Bluetooth device name."""
        if self.selected_adapter is None:
            print(
                "No Bluetooth adapter selected. Please select an adapter first."
            )
            return None

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
            raise bt_helper.BtException(
                "No device selected for profile connection."
            )

        print(
            f"Attempting to connect to {device} using profile {profile_uuid}"
        )

        try:
            # Get the D-Bus object path for the device
            device_path = device._if.object_path

            # Create a D-Bus proxy object for the device
            device_proxy = self._bus.get_object("org.bluez", device_path)

            # Get the interface for Device1, which provides the ConnectProfile method
            device_interface = bt_helper.dbus.Interface(
                device_proxy, bt_helper.DEVICE_IFACE
            )

            # Call ConnectProfile with the specific profile UUID
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
        if not self.selected_adapter:
            raise bt_helper.BtException("No adapter selected to show profiles.")

        try:
            supported_uuids = self.selected_adapter._prop_if.Get(
                bt_helper.ADAPTER_IFACE, "UUIDs"
            )

            print("Supported profiles for adapter {}:".format(self.selected_adapter))
            for uuid in supported_uuids:
                print(" - {}".format(uuid))

            return supported_uuids

        except bt_helper.dbus.exceptions.DBusException as exc:
            print("Failed to retrieve profiles for adapter {}: {}".format(self.selected_adapter, exc))
            raise SystemError("Could not retrieve adapter profiles!")


def generate_random_string(length=5):
    letters = string.ascii_letters
    return "".join(random.choice(letters) for _ in range(length))


def set_name_test(manager):
    ori_name = manager.get_bt_name()
    name = generate_random_string()
    print("Attampting to set BT name to {}".format(name))
    manager.set_bt_name(name)
    time.sleep(10)  # a delay to wait seting available
    current_name = manager.get_bt_name()
    if current_name != name and current_name == ori_name:
        raise SystemError("Set BT name failed!")


def test_bt_basic(manager, target, td=None):
    print("Starting Bluetooth basic functional test.")
    manager.get_bt_adapter_by_name(target)
    # print("Test set bt name ...")
    # set_name_test(manager)
    if manager.get_power_state() == 0:
        manager.power_on()
    # time.sleep(10)
    bt_manager.unpair_all()
    time.sleep(5)
    print("Test scan ...")
    target_devices = manager.get_devices()
    for device in target_devices:
        print(device)
        if re.search(td, device.address):
            print("find td {}".format(device))
            print("Attempting to pair with {}".format(device.address))
            try:
                # device.pair()
                # # time.sleep(5)
                manager.show_device_profiles(device)
                # manager.connect_profile(device, HFP_HS_UUID)
                # time.sleep(5)
                # print("Attempting to unpair with {}".format(device.address))
                # try:
                #     device.unpair()
                #     print("Unpair successful.")
                # except Exception:
                #     raise SystemError("Unpair device failed!")
            except Exception:
                raise SystemError("Pair device failed!")


def main():
    parser = argparse.ArgumentParser(description="Bluetooth Manager Script")
    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        required=True,
        help="The Bluetooth interface to use (e.g., hci0)",
    )
    parser.add_argument(
        "-t",
        "--target",
        type=str,
        required=True,
        help="The MAC address of the target Bluetooth device",
    )
    parser.add_argument(
        "-f",
        "--function",
        type=str,
        required=True,
        choices=["test_bt_basic", "another_test_function"],
        help="The test function to run",
    )
    args = parser.parse_args()
    bt_manager = ExtendBtManager()
    bt_manager.get_bt_adapter_by_name(args.interface)
    bt_manager.show_adapter_profiles()
    # if args.function == "test_bt_basic":
    #     test_bt_basic(bt_manager, args.interface, args.target)
    # elif args.function == "another_test_function":
    #     another_test_function(bt_manager, args.interface, args.target)


if __name__ == "__main__":
    main()
    # bt_manager.ensure_adapters_off()
    # test_bt_basic(bt_manager, "hci0", "64:90:00:00:5A:AD")  # RG3
    # test_bt_basic(bt_manager, "hci0", "94:DB:56:83:CB:FF")  # my BT headset
    # test_bt_basic(bt_manager, "hci0", "8C:8D:28:42:58:5F")  # my laptop

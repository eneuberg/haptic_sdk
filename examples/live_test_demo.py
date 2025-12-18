#!/usr/bin/env python3
"""Live demo script testing DongleConnection and StatusMonitor functionalities.

This script runs through a sequence of tests with delays to demonstrate:
1. Connection establishment
2. Status monitoring
3. Command sending
4. Buffer management
"""

import time
import sys
import logging
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.dongle import DongleConnection, DongleStatus, ESC_STATUS_START
from sdk.dongle.status_monitor import StatusMonitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LiveDemo")

def print_step(step_num: int, title: str):
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*60}")
    time.sleep(1)

def on_raw_data(chunk: bytes):
    """Callback for raw byte chunks."""
    # Filter out status messages for cleaner output
    if ESC_STATUS_START in chunk:
        # It contains a status message, we might want to suppress printing the raw bytes
        # or just print a marker
        pass
    else:
        try:
            text = chunk.decode('utf-8', errors='ignore').strip()
            if text:
                print(f"[RAW STREAM] Received {len(chunk)} bytes: {text[:50]}...")
        except:
            print(f"[RAW STREAM] Received {len(chunk)} bytes (binary)")

def on_status_update(status: DongleStatus):
    """Callback for status updates."""
    print(f"\n>>> [STATUS UPDATE] Firmware: {status.firmware_version}")
    print(f"    USB: {'Connected' if status.usb_present else 'Disconnected'}")
    print(f"    BLE: {'Connected' if status.bluetooth_connected else 'Disconnected'}")
    print(f"    Uptime: {status.uptime_ms}ms")
    if status.led_mode:
        print(f"    LED Mode: {status.led_mode}")

def main():
    print("Starting Live Dongle Functionality Test...")
    
    # Initialize objects
    dongle = DongleConnection(baudrate=1_000_000)
    monitor = StatusMonitor()
    
    # STEP 1: Connection
    print_step(1, "Connecting to Dongle")
    if not dongle.connect():
        logger.error("Failed to connect to dongle! Please check USB connection.")
        return
    logger.info(f"Connected to {dongle._port}")
    
    # STEP 2: Subscription
    print_step(2, "Setting up Subscriptions")
    
    # Subscribe monitor to data stream (so it can parse statuses)
    dongle.subscribe_data(monitor.on_data)
    print("✓ Monitor subscribed to data stream")
    
    # Subscribe our print callback to monitor (to see parsed statuses)
    monitor.subscribe_status(on_status_update)
    print("✓ Demo callback subscribed to status updates")
    
    # Subscribe raw data printer (optional, to see other traffic)
    dongle.subscribe_data(on_raw_data)
    print("✓ Raw data printer subscribed")
    
    time.sleep(2)

    # STEP 3: Status Request
    print_step(3, "Requesting Status")
    print("Sending status request command...")
    monitor.request_status(dongle)
    
    print("Waiting 3 seconds for response...")
    time.sleep(3)
    
    latest = monitor.get_latest_status()
    if latest:
        print(f"✓ Verified: Latest status stored in monitor: {latest.firmware_version}")
    else:
        print("⚠ Warning: No status received yet.")

    # STEP 4: Buffer Stats
    print_step(4, "Checking Buffer Stats")
    size = monitor.get_buffer_size()
    print(f"Current Monitor Buffer Size: {size} bytes")
    print("Clearing buffer...")
    monitor.clear_buffer()
    print(f"Buffer Size after clear: {monitor.get_buffer_size()} bytes")
    time.sleep(2)

    # STEP 5: Command Sending
    print_step(5, "Sending Test Command")
    cmd = "!ping"
    print(f"Sending '{cmd}'...")
    dongle.send_command(cmd)
    time.sleep(2)
    
    # STEP 6: Stress Test (Optional)
    print_step(6, "Rapid Status Request Test")
    print("Requesting status 3 times rapidly...")
    for i in range(3):
        print(f"Request {i+1}...")
        monitor.request_status(dongle)
        time.sleep(0.5)
    
    time.sleep(2)

    # STEP 7: Cleanup
    print_step(7, "Disconnecting")
    dongle.disconnect()
    print("Disconnected.")
    print("\nTest Complete.")

if __name__ == "__main__":
    main()

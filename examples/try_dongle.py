#!/usr/bin/env python3
"""
Interactive Dongle Test Script.

This script demonstrates the high-level Dongle API.
Run it to connect to a dongle, monitor status, and send commands.
"""

import sys
import time
import logging
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.dongle.manager import Dongle

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    print("Initializing Dongle Manager...")
    dongle = Dongle()
    
    print("\nAttempting to connect (auto-detect)...")
    if not dongle.connect():
        print("Failed to connect! Is the dongle plugged in?")
        return

    print("Connected!")
    print(f"Dongle Connected: {dongle.is_dongle_connected}")
    
    try:
        print("\nMonitoring status for 10 seconds (Ctrl+C to stop)...")
        for i in range(10):
            status = dongle.get_latest_status()
            
            # Clear line
            print(f"\r[{i+1}/10] ", end="")
            
            if status:
                print(f"Glove: {'CONNECTED' if status.bluetooth_connected else 'DISCONNECTED'} | "
                      f"FW: {status.firmware_version or '?'} | "
                      f"Signal: {status.signal_strength or '?'} dBm", end="")
            else:
                print("Waiting for status...", end="")
                
            if dongle.is_status_stale:
                print(" [STALE]", end="")
                
            sys.stdout.flush()
            time.sleep(1)
            
        print("\n\nSending a test command (Enable All)...")
        # Example command - adjust as needed for your protocol
        dongle.write(b"!enableAll\n")
        print("Command sent.")
        
        print("\nReading response (2s timeout)...")
        start = time.time()
        while time.time() - start < 2.0:
            line = dongle.read_line()
            if line:
                print(f"Received: {line}")
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("\nDisconnecting...")
        dongle.disconnect()
        print("Done.")

if __name__ == "__main__":
    main()

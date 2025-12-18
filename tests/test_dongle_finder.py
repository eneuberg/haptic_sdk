#!/usr/bin/env python3
"""Test script for the dongle_finder package.

This script attempts to find the Haptic Glove Dongle using its VID/PID
and manufacturer/product strings.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sdk.dongle.dongle_finder import find_dongles, find_single_dongle, DongleInfo
from sdk.dongle.dongle_finder.errors import DongleNotFoundError, MultipleDonglesError

# Haptic Glove Dongle USB identifiers
HAPTIC_GLOVE_VID = 0x5FFE
HAPTIC_GLOVE_PID = 0x1000
HAPTIC_GLOVE_MANUFACTURER = "Felya Labs"
HAPTIC_GLOVE_PRODUCT = "Haptic Glove Dongle"


def test_find_all_dongles():
    """Test finding all matching dongles."""
    print("=" * 60)
    print("TEST: Find all Haptic Glove Dongles")
    print("=" * 60)
    
    try:
        dongles = find_dongles(
            expected_vid=HAPTIC_GLOVE_VID,
            expected_pid=HAPTIC_GLOVE_PID,
        )
        
        print(f"✓ Found {len(dongles)} matching dongle(s)")
        
        for idx, dongle in enumerate(dongles, 1):
            print(f"\nDongle #{idx}:")
            print(f"  Port:         {dongle.port}")
            print(f"  VID:          0x{dongle.vid:04X}" if dongle.vid else "  VID:          None")
            print(f"  PID:          0x{dongle.pid:04X}" if dongle.pid else "  PID:          None")
            print(f"  Manufacturer: {dongle.manufacturer}")
            print(f"  Product:      {dongle.product}")
            print(f"  Serial #:     {dongle.serial_number}")
            print(f"  Device ID:    {dongle.device_id}")
            print(f"  HWID:         {dongle.hwid}")
        
        return dongles
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def test_find_single_dongle():
    """Test finding exactly one dongle."""
    print("\n" + "=" * 60)
    print("TEST: Find single Haptic Glove Dongle")
    print("=" * 60)
    
    try:
        dongle = find_single_dongle(
            expected_vid=HAPTIC_GLOVE_VID,
            expected_pid=HAPTIC_GLOVE_PID,
        )
        
        print(f"✓ Found exactly one dongle at: {dongle.port}")
        print(f"  Product: {dongle.product}")
        print(f"  Serial:  {dongle.serial_number}")
        return dongle
    
    except DongleNotFoundError:
        print("✗ No matching dongle found")
        print("  Make sure the Haptic Glove Dongle is plugged in")
        return None
    
    except MultipleDonglesError as e:
        print(f"✗ Multiple dongles found ({len(e.devices)} devices)")
        print("  This test expects exactly one dongle")
        for idx, dongle in enumerate(e.devices, 1):
            print(f"  Device {idx}: {dongle.port} (Serial: {dongle.serial_number})")
        return None
    
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


def test_find_by_product_string():
    """Test finding dongle by product substring."""
    print("\n" + "=" * 60)
    print("TEST: Find by product substring")
    print("=" * 60)
    
    try:
        dongles = find_dongles(product_substring="Haptic Glove")
        
        print(f"✓ Found {len(dongles)} dongle(s) with 'Haptic Glove' in product name")
        for dongle in dongles:
            print(f"  - {dongle.port}: {dongle.product}")
        
        return dongles
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def test_custom_matcher():
    """Test using a custom matcher function."""
    print("\n" + "=" * 60)
    print("TEST: Custom matcher (Felya Labs manufacturer)")
    print("=" * 60)
    
    def is_felya_labs_device(info: DongleInfo) -> bool:
        """Match any device from Felya Labs."""
        return info.manufacturer == HAPTIC_GLOVE_MANUFACTURER
    
    try:
        dongles = find_dongles(matcher=is_felya_labs_device)
        
        print(f"✓ Found {len(dongles)} Felya Labs device(s)")
        for dongle in dongles:
            print(f"  - {dongle.port}: {dongle.product}")
        
        return dongles
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def test_all_serial_ports():
    """List all serial ports for debugging."""
    print("\n" + "=" * 60)
    print("DEBUG: All available serial ports")
    print("=" * 60)
    
    from serial.tools import list_ports
    
    ports = list_ports.comports()
    
    if not ports:
        print("No serial ports found")
        return
    
    print(f"Found {len(ports)} serial port(s):\n")
    
    for idx, port in enumerate(ports, 1):
        print(f"Port #{idx}:")
        print(f"  Device:       {port.device}")
        print(f"  Name:         {port.name}")
        print(f"  Description:  {port.description}")
        vid_str = f"0x{port.vid:04X}" if port.vid else "None"
        pid_str = f"0x{port.pid:04X}" if port.pid else "None"
        print(f"  VID:PID:      {vid_str}:{pid_str}")
        print(f"  Manufacturer: {port.manufacturer}")
        print(f"  Product:      {port.product}")
        print(f"  Serial #:     {port.serial_number}")
        print(f"  HWID:         {port.hwid}")
        print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("HAPTIC GLOVE DONGLE FINDER TEST SUITE")
    print("=" * 60)
    print(f"\nLooking for:")
    print(f"  VID: 0x{HAPTIC_GLOVE_VID:04X}")
    print(f"  PID: 0x{HAPTIC_GLOVE_PID:04X}")
    print(f"  Manufacturer: {HAPTIC_GLOVE_MANUFACTURER}")
    print(f"  Product: {HAPTIC_GLOVE_PRODUCT}")
    print()
    
    # Run tests
    test_all_serial_ports()
    test_find_all_dongles()
    test_find_single_dongle()
    test_find_by_product_string()
    test_custom_matcher()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()

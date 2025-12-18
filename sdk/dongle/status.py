"""Dongle status protocol definitions.

Handles parsing of status messages from USB CDC dongle.
Status messages use escape sequence protocol: \x1B[STATUS_RESPONSE]\r\n + JSON payload
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


# Protocol delimiters
ESC_STATUS_REQUEST = b'@@@[STATUS]@@@'
ESC_STATUS_START = b'\xFF\x34[STATUS_RESPONSE]'
ESC_STATUS_END = b'\xFF\x34'

DEFAULT_STATUS_STALENESS_THRESHOLD = 2.0  # seconds

@dataclass(frozen=True)
class DongleStatus:
    """Status information from USB CDC dongle.
    
    Parsed from JSON payload in status response messages.
    
    Attributes:
        timestamp: Local timestamp when status was received
        device: Device identifier string
        firmware_version: Dongle firmware version string
        uptime_ms: Dongle uptime in milliseconds
        usb_present: USB VBUS detected
        usb_serial_connected: USB CDC serial connected
        bluetooth_connected: BLE connection to glove active
        nus_subscribed: Nordic UART Service subscribed
        bt_mtu: Bluetooth MTU size
        max_payload: Maximum payload size
        usb_rx_bps: USB receive bytes per second
        ble_rx_bps: BLE receive bytes per second
        led_mode: Current LED pattern
        raw_json: Original JSON data for debugging
    """
    timestamp: float
    device: Optional[str]
    firmware_version: Optional[str]
    uptime_ms: int
    usb_present: bool
    usb_serial_connected: bool
    bluetooth_connected: bool
    nus_subscribed: bool
    bt_mtu: int
    max_payload: int
    usb_rx_bps: int
    ble_rx_bps: int
    led_mode: Optional[str]
    raw_json: Optional[dict] = None
    
    @property
    def dongle_connected(self) -> bool:
        """Alias for usb_present."""
        return self.usb_present
    
    @property
    def is_stale(self, threshold: float = DEFAULT_STATUS_STALENESS_THRESHOLD) -> bool:
        """Check if status is stale (> DEFAULT_STATUS_STALENESS_THRESHOLD seconds old)."""
        return (time.time() - self.timestamp) > threshold
    
    @classmethod
    def from_json(cls, json_data: dict, timestamp: Optional[float] = None) -> DongleStatus:
        """Parse status from JSON payload.
        
        Args:
            json_data: Parsed JSON dictionary from status message
            timestamp: Timestamp to use, or None for current time
            
        Returns:
            DongleStatus instance
            
        Example JSON format:
            {
                "device": "BT_DONGLE_NUS",
                "version": "1.0.0",
                "uptime_ms": 135046,
                "usb_present": true,
                "usb_serial_connected": true,
                "bt_connected": false,
                "nus_subscribed": false,
                "bt_mtu": 0,
                "max_payload": 20,
                "led_mode": "slow_blink"
            }
        """
        if timestamp is None:
            timestamp = time.time()
        
        return cls(
            timestamp=timestamp,
            device=json_data.get("device"),
            firmware_version=json_data.get("version"),
            uptime_ms=json_data.get("uptime_ms", 0),
            usb_present=json_data.get("usb_present", False),
            usb_serial_connected=json_data.get("usb_serial_connected", False),
            bluetooth_connected=json_data.get("bt_connected", False),
            nus_subscribed=json_data.get("nus_subscribed", False),
            bt_mtu=json_data.get("bt_mtu", 0),
            max_payload=json_data.get("max_payload", 0),
            usb_rx_bps=json_data.get("usb_rx_bps", 0),
            ble_rx_bps=json_data.get("ble_rx_bps", 0),
            led_mode=json_data.get("led_mode"),
            raw_json=json_data,
        )
    
    @classmethod
    def disconnected(cls, timestamp: Optional[float] = None) -> DongleStatus:
        """Create a status representing disconnected state.
        
        Args:
            timestamp: Timestamp to use, or None for current time
            
        Returns:
            DongleStatus with all connections inactive
        """
        if timestamp is None:
            timestamp = time.time()
        
        return cls(
            timestamp=timestamp,
            device=None,
            firmware_version=None,
            uptime_ms=0,
            usb_present=False,
            usb_serial_connected=False,
            bluetooth_connected=False,
            nus_subscribed=False,
            bt_mtu=0,
            max_payload=0,
            usb_rx_bps=0,
            ble_rx_bps=0,
            led_mode=None,
            raw_json=None,
        )


def parse_status_json(json_bytes: bytes) -> Optional[DongleStatus]:
    """Parse status message JSON payload.
    
    Args:
        json_bytes: JSON bytes from status message
        
    Returns:
        DongleStatus instance, or None if parsing fails
    """
    try:
        json_str = json_bytes.decode('utf-8', errors='ignore').strip()
        if not json_str:
            return None
        
        data = json.loads(json_str)
        return DongleStatus.from_json(data)
    
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        # Return None on parse error
        return None

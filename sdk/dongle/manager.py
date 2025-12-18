"""Dongle abstraction layer.

Manages the low-level connection and status monitoring, exposing a simplified
interface for the protocol layer.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .connection import DongleConnection
from .status import DongleStatus
from .status_monitor import StatusMonitor
from .buffer import StreamBuffer

logger = logging.getLogger(__name__)

DONGLE_MAX_BUFFER_SIZE = 4096 * 1024  # 4MB
DONGLE_STATUS_POLL_INTERVAL = 0.2   # seconds

class Dongle:
    """High-level interface to the Haptic Glove Dongle.
    
    This class acts as a facade, managing:
    1. The physical connection (DongleConnection)
    2. Status monitoring and parsing (StatusMonitor)
    3. Data buffering for the protocol layer (StreamBuffer)
    
    It provides a pull-based interface (read/read_line) for data,
    avoiding the need for the protocol layer to handle callbacks.
    """
    
    def __init__(self, port: Optional[str] = None):
        """Initialize Dongle manager.
        
        Args:
            port: Serial port path, or None to auto-detect.
        """
                # Components
        self._connection = DongleConnection(port=port)
        # Pass connection to monitor for automatic polling
        self._monitor = StatusMonitor(connection=self._connection)
        self._buffer = StreamBuffer(max_size=DONGLE_MAX_BUFFER_SIZE) # 512KB buffer
        
        # Buffer collects all data for the protocol layer
        self._connection.subscribe_data(self._on_data_received)
    
    def _on_data_received(self, chunk: bytes) -> None:
        """Internal callback to push data to buffer."""
        self._buffer.write(chunk)
    
    def connect(self, autoreconnect: bool = True, auto_monitor_status: bool = True) -> bool:
        """Connect to the dongle.
        
        Args:
            autoreconnect: If True, automatically attempt to reconnect if connection is lost.
            auto_monitor_status: If True, start automatic status polling + status monitoring on connect.
        
        Returns:
            True if connection successful immediately.
        """
        
        success: bool = False
        
        if self._connection.connect():
            if auto_monitor_status:
                self._monitor.start(interval=DONGLE_STATUS_POLL_INTERVAL)
            success = True
        
        self._connection.set_autoreconnect(autoreconnect)
        return success
        
    def disconnect(self) -> None:
        """Disconnect from the dongle."""
        self._connection.set_autoreconnect(False)
        self._monitor.stop()
        self._connection.disconnect()

    # --- Data Interface (Pull Model) ---
    
    def read(self, size: int = -1) -> bytes:
        """Read raw bytes from the stream buffer.
        
        Args:
            size: Number of bytes to read (-1 for all).
            
        Returns:
            Bytes read.
        """
        return self._buffer.read(size)
        
    def read_line(self) -> bytes:
        """Read a line from the stream buffer.
        
        Returns:
            Line bytes including newline, or empty if no line available.
        """
        return self._buffer.read_line()
        
    def write(self, data: bytes) -> bool:
        """Write raw bytes to the dongle.
        
        Args:
            data: Bytes to send.
            
        Returns:
            True if successful.
        """
        return self._connection.write(data)
        
    def write_line(self, line: bytes) -> bool:
        """Write a line to the dongle.
        
        Args:
            line: Line bytes (without newline).
            
        Returns:
            True if successful.
        """
        if not line.endswith(b'\n'):
            line += b'\n'
        return self._connection.write(line)
        
    # --- Status Interface ---
    
    @property
    def is_dongle_connected(self) -> bool:
        """Check if USB dongle is connected."""
        return self._connection.is_connected()
        
    @property
    def is_glove_connected(self) -> bool:
        """Check if glove is connected via Bluetooth.
        
        Returns False if dongle itself is not connected.
        """
        if not self.is_dongle_connected:
            return False
        status = self._monitor.get_latest_status()
        return status.bluetooth_connected if status else False
        
    @property
    def is_ready(self) -> bool:
        """Check if system is ready to receive commands (USB + BLE)."""
        return self.is_dongle_connected and self.is_glove_connected
        
    @property
    def is_status_stale(self) -> bool:
        """Check if status information is stale (> 2.0s old)."""
        status = self._monitor.get_latest_status()
        if not status:
            return True
        return status.is_stale

    def get_status(self) -> DongleStatus:
        """Get the latest detailed status.
        
        If no status has been received yet, returns a default status
        reflecting the current connection state (e.g. Dongle connected, Glove disconnected).
        """
        status = self._monitor.get_latest_status()
        if status:
            return status
            
        # If we are connected but haven't received status yet, return a placeholder
        # that reflects at least the USB connection state we know about.
        if self.is_dongle_connected:
            # We know USB is connected, but don't know about BLE yet.
            # We'll use disconnected() as base but set usb_present=True
            base = DongleStatus.disconnected()
            # Since it's frozen, we use replace (if dataclasses.replace is available)
            # or just construct it manually. Since it's frozen, we can't modify it.
            # Let's construct a "connected but unknown" status.
            return DongleStatus(
                timestamp=time.time(),
                device="Unknown",
                firmware_version=None,
                uptime_ms=0,
                usb_present=True,
                usb_serial_connected=True,
                bluetooth_connected=False,
                nus_subscribed=False,
                bt_mtu=0,
                max_payload=0,
                usb_rx_bps=0,
                ble_rx_bps=0,
                led_mode=None,
                raw_json=None
            )
            
        return DongleStatus.disconnected()
        
    def request_status(self) -> None:
        """Manually request a status update."""
        self._monitor.request_status()
    
    @property
    def buffer_size(self) -> int:
        """Get current number of bytes in the read buffer."""
        return self._buffer.size

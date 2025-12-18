"""Low-level USB CDC connection to haptic glove dongle.

The dongle is a USB CDC Bluetooth bridge device that:
- Connects to PC via USB (VID=0x5FFE, PID=0x1000)
- Connects to glove via Bluetooth Low Energy
- Forwards data bidirectionally between PC and glove
- Provides status messages about connection state

This module handles:
- USB CDC serial connection management
- Raw byte stream forwarding with callbacks
- Connection state monitoring

Note: This is a RAW BYTE STREAM layer. It does not interpret
      messages. Use StatusMonitor to observe status messages.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, List, Optional

import serial
import serial.tools.list_ports

from .dongle_finder import find_single_dongle, DongleNotFoundError, is_dongle_available
from .status import DongleStatus

logger = logging.getLogger(__name__)

EXPECTED_VID = 0x5FFE
EXPECTED_PID = 0x1000
PRODUCT_SUBSTRING = "Haptic Glove Dongle"

CONNECTION_BAUD = 1_000_000  # 1M baud
READ_TIMEOUT = 0.1  # seconds
READ_CHUNK_SIZE = 4096  # bytes

class DongleConnection:
    """Low-level USB CDC connection to haptic glove dongle.
    
    Provides a RAW BYTE STREAM interface to the dongle.
    Does not interpret or parse messages - just forwards bytes.
    
    Responsibilities:
    - Open/close serial connection to dongle
    - Forward raw byte chunks to subscribers
    - Send raw bytes to dongle
    - Maintain connection state
    
    Example:
        >>> from sdk.dongle.status_monitor import StatusMonitor
        >>> 
        >>> # Create raw stream connection
        >>> dongle = DongleConnection()
        >>> dongle.connect()
        True
        >>> 
        >>> # Subscribe to raw byte stream
        >>> dongle.subscribe_data(lambda chunk: print(f"Data: {chunk}"))
        <function>
        >>> 
        >>> # Use StatusMonitor to observe status messages
        >>> monitor = StatusMonitor()
        >>> dongle.subscribe_data(monitor.on_data)
        >>> monitor.subscribe_status(lambda s: print(f"Status: {s}"))
        >>> 
        >>> # Send commands
        >>> dongle.write(b"!setSetpointAll -thumb 0.5 ...")
        >>> dongle.disconnect()
    """
    
    def __init__(self,
                 port: Optional[str] = None,
                 baudrate: int = CONNECTION_BAUD,
                 timeout: float = READ_TIMEOUT,
                 chunk_size: int = READ_CHUNK_SIZE):
        """Initialize dongle connection.
        
        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0'), or None to auto-detect
            baudrate: Serial baud rate (default 1M)
            timeout: Read timeout in seconds
            chunk_size: Maximum bytes to read per chunk (default 4KB)
        """
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._chunk_size = chunk_size
        
        # Serial connection
        self._serial: Optional[serial.Serial] = None
        self._connected = False
        
        # Threading
        self._active = False
        self._reader_thread: Optional[threading.Thread] = None
        
        # Autoreconnect
        self._autoreconnect = False
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_reconnect = threading.Event()
        
        # Callbacks
        self._data_callbacks: List[Callable[[bytes], None]] = []
        
        # Thread safety
        self._callback_lock = threading.Lock()
    
    def connect(self) -> bool:
        """Open USB CDC connection to dongle.
        
        If port is None, attempts to auto-detect dongle by VID/PID.
        
        Returns:
            True if connection successful, False otherwise
        """
        if self._connected:
            logger.warning("Already connected")
            return True
        
        # Auto-detect dongle if port not specified
        if self._port is None:
            try:
                info = find_single_dongle(
                    expected_vid=EXPECTED_VID,
                    expected_pid=EXPECTED_PID,
                    product_substring=PRODUCT_SUBSTRING
                )
                self._port = info.port
                logger.info(f"Auto-detected dongle on {self._port}")
            except DongleNotFoundError as e:
                logger.error(f"Dongle not found: {e}")
                return False
            except Exception as e:
                logger.error(f"Error finding dongle: {e}")
                return False
        
        # Open serial port
        try:
            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout,
            )
            
            # Clear buffers
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
            
            logger.info(f"Connected to dongle on {self._port} @ {self._baudrate} baud")
        
        except serial.SerialException as e:
            logger.error(f"Failed to open {self._port}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error opening port: {e}")
            return False
        
        # Start reader thread
        self._active = True
        self._connected = True
        self._start_reader_thread()
        
        return True
    
    def disconnect(self) -> None:
        """Close dongle connection and cleanup resources."""
        if not self._connected:
            return
        
        self._active = False
        self._connected = False
        
        # Wait for reader thread to finish
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        
        # Close serial port
        if self._serial:
            try:
                self._serial.close()
            except Exception as e:
                logger.error(f"Error closing serial port: {e}")
            finally:
                self._serial = None
        
        logger.info("Disconnected from dongle")
    
    def is_connected(self) -> bool:
        """Check if dongle USB connection is active.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._serial is not None

    def is_dongle_available(self) -> bool:
        """Check if dongle is available for connection.
        
        Checks if the dongle is physically present and recognized by the OS,
        without attempting to open a connection.
        
        Returns:
            True if dongle is found/available.
        """
        if self.is_connected():
            return True
            
        return is_dongle_available(
            port=self._port,
            expected_vid=EXPECTED_VID,
            expected_pid=EXPECTED_PID,
            product_substring=PRODUCT_SUBSTRING
        )

    def set_autoreconnect(self, enabled: bool) -> None:
        """Enable or disable automatic reconnection.
        
        Args:
            enabled: True to enable autoreconnect.
        """
        if self._autoreconnect == enabled:
            return
            
        self._autoreconnect = enabled
        
        if enabled:
            self._stop_reconnect.clear()
            # Only start if not connected and not already running
            if not self.is_connected() and (self._reconnect_thread is None or not self._reconnect_thread.is_alive()):
                self._start_reconnect_thread()
        else:
            self._stop_reconnect.set()
            if self._reconnect_thread and self._reconnect_thread.is_alive():
                self._reconnect_thread.join(timeout=1.0)
            self._reconnect_thread = None

    def _start_reconnect_thread(self) -> None:
        """Start background thread for autoreconnect."""
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True,
            name="DongleReconnect"
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        """Background loop to monitor connection and reconnect if needed."""
        logger.info("Autoreconnect loop started")
        while not self._stop_reconnect.is_set():
            if self.is_connected():
                break
            
            if self.is_dongle_available():
                logger.info("Dongle detected, attempting autoreconnect...")
                if self.connect():
                    logger.info("Autoreconnect successful")
                    break
            
            self._stop_reconnect.wait(1.0)
        logger.info("Autoreconnect loop stopped")
    
    def write(self, data: bytes) -> bool:
        """Send raw bytes to dongle (forwarded to glove).
        
        Args:
            data: Raw bytes to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        
        if not self.is_connected() or self._serial is None:
            logger.warning("Cannot send, not connected", exc_info=True)
            return False
        
        try:
            self._serial.write(data)
            self._serial.flush()
            return True
        except serial.SerialException as e:
            logger.error(f"Send error: {e}")
            self._handle_error(e)
            return False
        except Exception as e:
            logger.error(f"Unexpected send error: {e}")
            self._handle_error(e)
            return False
    
    def subscribe_data(self,
                      callback: Callable[[bytes], None]
                      ) -> Callable[[], None]:
        """Subscribe to raw byte stream from dongle.
        
        Callback will be invoked with raw byte chunks as they arrive.
        Multiple subscribers can observe the same stream.
        
        Args:
            callback: Function to call with byte chunks
            
        Returns:
            Unsubscribe function (call to remove subscription)
            
        Example:
            >>> def on_data(chunk):
            ...     print(f"Received {len(chunk)} bytes: {chunk}")
            >>> unsub = dongle.subscribe_data(on_data)
            >>> # Later...
            >>> unsub()
        """
        with self._callback_lock:
            self._data_callbacks.append(callback)
        
        def unsubscribe():
            with self._callback_lock:
                if callback in self._data_callbacks:
                    self._data_callbacks.remove(callback)
        
        return unsubscribe
    
    # Internal methods
    
    def _start_reader_thread(self) -> None:
        """Start background thread for reading from dongle."""
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
            name="DongleReader"
        )
        self._reader_thread.start()
    
    def _reader_loop(self) -> None:
        """Read raw bytes from dongle and dispatch to callbacks."""
        logger.debug("Reader thread started")
        
        while self._active and self._serial:
            try:
                # Read chunk of bytes (non-blocking with timeout)
                chunk = self._serial.read(self._chunk_size)
                
                if chunk:
                    # Broadcast raw bytes to all subscribers
                    self._notify_data_callbacks(chunk)
                
            except serial.SerialException as e:
                if self._active:
                    logger.error(f"Serial read error: {e}")
                    self._handle_error(e)
                break
            except Exception as e:
                if self._active:
                    logger.error(f"Reader error: {e}")
                    self._handle_error(e)
        
        logger.debug("Reader thread exiting")
    
    def _notify_data_callbacks(self, data: bytes) -> None:
        """Notify all data subscribers.
        
        Args:
            data: Raw byte chunk to send to callbacks
        """
        with self._callback_lock:
            callbacks = list(self._data_callbacks)
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in data callback: {e}")

    def _handle_error(self, error: Exception) -> None:
        """Handle connection error by closing resources.
        
        Called when a fatal error occurs (e.g. device unplugged).
        Does not join threads to avoid deadlock if called from reader thread.
        """
        logger.warning(f"Handling connection error: {error}")
        self._active = False
        self._connected = False
        
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        
        logger.info("Connection closed due to error")
        
        # Trigger autoreconnect if enabled
        if self._autoreconnect:
            if self._reconnect_thread is None or not self._reconnect_thread.is_alive():
                self._start_reconnect_thread()

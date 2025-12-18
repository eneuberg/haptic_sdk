"""Serial transport implementation for haptic glove communication.

Implements the Transport interface using the Dongle layer for hardware communication
and the Protocol layer for message parsing/serialization.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional, List

from ..transport.base import Transport
from ..models import GloveState, Command
from ..protocol import Protocol, ASCIIProtocol, StateBuilder
from ..dongle import Dongle, DongleStatus


class SerialTransport(Transport):
    """Transport layer using serial dongle connection.
    
    Responsibilities:
    - Manage dongle connection lifecycle
    - Parse data using protocol layer
    - Accumulate state via StateBuilder
    - Notify subscribers of state changes
    - Send commands via protocol + dongle
    """
    
    def __init__(
        self,
        dongle: Optional[Dongle] = None,
        protocol: Optional[Protocol] = None,
        port: Optional[str] = None,
    ):
        """Initialize SerialTransport.
        
        Args:
            dongle: Existing Dongle instance, or None to create new
            protocol: Protocol implementation (default: ASCIIProtocol)
            port: Serial port for new dongle connection (if dongle is None)
        """
        # Use provided dongle or create new
        self._dongle = dongle or Dongle(port=port)
        
        # Use provided protocol or default to ASCII
        self._protocol = protocol or ASCIIProtocol()
        
        self._state_builder = StateBuilder()
        
        self._connected = False
        self._subscribers: List[Callable[[GloveState], None]] = []
        self._subscriber_lock = threading.Lock()
        
        # Command queue for rate-limited sending
        self._command_queue: queue.Queue[Optional[Command]] = queue.Queue()
        self._sender_thread: Optional[threading.Thread] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._active = False
        
        # Rate limiting
        self._last_send_time = 0.0
        self._min_send_interval = 0.01  # 10ms between commands
    
    def connect(self) -> bool:
        """Connect to glove via dongle."""
        if self._connected:
            return True
            
        # Connect dongle
        if not self._dongle.connect():
            return False
        
        self._active = True
        self._connected = True
        
        self._start_threads()
        
        # Update state
        self._state_builder.set_connected(True)
        self._notify_subscribers()
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from glove."""
        self._active = False
        self._connected = False
        
        # Stop sender thread
        self._command_queue.put(None)
        
        if self._sender_thread and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=1.0)
            
        # Stop reader thread (it checks self._active)
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        
        # Disconnect dongle
        self._dongle.disconnect()
        
        # Update state
        self._state_builder.set_connected(False)
        self._notify_subscribers()
    
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected and self._dongle.is_dongle_connected
    
    def subscribe_state(
        self,
        callback: Callable[[GloveState], None]
    ) -> Callable[[], None]:
        """Subscribe to state updates."""
        with self._subscriber_lock:
            self._subscribers.append(callback)
        
        # Send current state
        try:
            state = self._state_builder.snapshot()
            callback(state)
        except Exception:
            pass
        
        def unsubscribe():
            with self._subscriber_lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        
        return unsubscribe
    
    def send_command(self, command: Command) -> None:
        """Send command to glove."""
        if not self._connected:
            return
        
        self._command_queue.put(command)
    
    def _start_threads(self) -> None:
        """Start reader and sender threads."""
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
            name="TransportReader"
        )
        self._reader_thread.start()
        
        self._sender_thread = threading.Thread(
            target=self._sender_loop,
            daemon=True,
            name="TransportSender"
        )
        self._sender_thread.start()
    
    def _reader_loop(self) -> None:
        """Read lines from dongle and update state."""
        while self._active:
            try:
                # Check dongle status for connection changes
                self._check_dongle_status()
                
                # Read line from dongle buffer
                line_bytes = self._dongle.read_line()
                if not line_bytes:
                    time.sleep(0.001) # Yield if no data
                    continue
                
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                
                # Parse via protocol
                update = self._protocol.parse_line(line)
                if update:
                    self._state_builder.apply(update)
                    self._notify_subscribers()
                    
            except Exception as e:
                if self._active:
                    self._log(f"Reader error: {e}")
                time.sleep(0.1)
    
    def _check_dongle_status(self) -> None:
        """Check dongle status and update state builder."""
        # If dongle disconnects (USB), we are effectively disconnected
        if not self._dongle.is_dongle_connected:
            if self._state_builder._connected:
                self._state_builder.set_connected(False)
                self._notify_subscribers()
            return

        # If dongle is connected, check BLE status
        is_ble_connected = self._dongle.is_glove_connected
        
        # Update state builder if changed
        if self._state_builder._connected != is_ble_connected:
            self._state_builder.set_connected(is_ble_connected)
            self._notify_subscribers()
            self._log(f"Glove connection state changed: {is_ble_connected}")

    def _sender_loop(self) -> None:
        """Process command queue with rate limiting."""
        while True:
            try:
                # Get command (blocking)
                command = self._command_queue.get(timeout=1.0)
                
                if command is None:  # Sentinel
                    break
                
                # Rate limiting
                now = time.monotonic()
                elapsed = now - self._last_send_time
                if elapsed < self._min_send_interval:
                    time.sleep(self._min_send_interval - elapsed)
                
                # Serialize and send
                data = self._protocol.serialize_command(command)
                self._dongle.write(data)
                
                self._last_send_time = time.monotonic()
                
            except queue.Empty:
                continue
            except Exception as e:
                if self._active:
                    self._log(f"Sender error: {e}")
    
    def _notify_subscribers(self) -> None:
        """Notify all subscribers with current state snapshot."""
        state = self._state_builder.snapshot()
        
        with self._subscriber_lock:
            subscribers = list(self._subscribers)
        
        for callback in subscribers:
            try:
                callback(state)
            except Exception as e:
                self._log(f"Subscriber error: {e}")

    def _log(self, message: str) -> None:
        print(f"[SerialTransport] {message}")

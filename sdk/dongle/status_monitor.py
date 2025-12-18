"""Status monitor that observes raw byte stream for status messages.

The StatusMonitor subscribes to the raw byte stream from the dongle
and maintains an internal buffer to detect and extract status messages.
It does not intercept or modify the stream - it merely observes it.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .connection import DongleConnection

from .status import (
    DongleStatus,
    ESC_STATUS_REQUEST,
    ESC_STATUS_START,
    ESC_STATUS_END,
    parse_status_json,
)

logger = logging.getLogger(__name__)

STATUS_MONITOR_MAX_BUFFER_SIZE = 64 * 1024  # 64KB
DEFAULT_POLL_INTERVAL = 1.0  # seconds

class StatusMonitor:
    """Observes byte stream and extracts status messages.
    
    Subscribes to raw byte stream from dongle connection.
    Maintains internal buffer to detect status message patterns.
    Parses JSON when complete status message is detected.
    
    Can optionally poll for status updates automatically.
    
    Performance Note:
        This monitor runs in the context of the reader thread callback.
        Complex processing here will block the reader thread.
        The buffer handling is optimized to be fast (O(N) scan),
        but extremely high data rates combined with large buffers
        could introduce latency.
    
    This is a passive observer - it does not intercept or modify
    the byte stream. All bytes are still delivered to other subscribers.
    """
    
    MAX_BUFFER_SIZE = STATUS_MONITOR_MAX_BUFFER_SIZE
    
    def __init__(self, connection: DongleConnection):
        """Initialize status monitor.
        
        Args:
            connection: DongleConnection to use for requesting status updates.
        """
        self._connection = connection
        
        # Internal buffer for incomplete messages
        self._buffer = bytearray()
        
        # Latest parsed status
        self._latest_status: Optional[DongleStatus] = None
        
        # Status update callbacks
        self._status_callbacks: List[Callable[[DongleStatus], None]] = []
        
        # Thread safety
        self._buffer_lock = threading.Lock()
        self._callback_lock = threading.Lock()
        self._status_lock = threading.Lock()
        
        # Automatic Monitoring (Polling + Processing)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._poll_interval = DEFAULT_POLL_INTERVAL
        # Limit queue size to prevent memory leaks if processing stops
        self._data_queue: queue.Queue[bytes] = queue.Queue(maxsize=1000) 
        
        # Subscribe to connection
        self._connection.subscribe_data(self.on_data)
            
    def start(self, interval: float = DEFAULT_POLL_INTERVAL) -> None:
        """Start automatic monitoring (processing + polling).
        
        Args:
            interval: Seconds between status requests.
        """
        if self._running:
            self._poll_interval = interval
            return
            
        self._poll_interval = interval
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="StatusMonitor"
        )
        self._thread.start()
        logger.debug(f"Status monitor started (interval={interval}s)")
        
    def stop(self) -> None:
        """Stop automatic monitoring."""
        if not self._running:
            return
            
        self._running = False
        if self._thread and self._thread.is_alive():
            # Send dummy data to unblock queue.get
            self._data_queue.put(b'')
            self._thread.join(timeout=1.0)
        self._thread = None
        logger.debug("Status monitor stopped")
    
    def on_data(self, chunk: bytes) -> None:
        """Receive incoming byte chunk from dongle.
        
        Args:
            chunk: Raw bytes from dongle
        """
        try:
            self._data_queue.put(chunk, block=False)
        except queue.Full:
            # Queue is full, drop oldest item to make room (FIFO behavior)
            try:
                self._data_queue.get_nowait()
                self._data_queue.put(chunk, block=False)
                logger.warning("Status monitor queue full, dropped oldest chunk")
            except (queue.Empty, queue.Full):
                # If queue became empty (race) or is still full (race), drop new chunk
                pass
            
    def process_pending(self) -> None:
        """Process all pending data in the queue (Synchronous).
        
        Useful for testing or manual processing when automatic mode is off.
        """
        while True:
            try:
                chunk = self._data_queue.get_nowait()
                if chunk:
                    self._process_chunk(chunk)
            except queue.Empty:
                break
                
    def _monitor_loop(self) -> None:
        """Background loop for processing and polling."""
        last_poll_time = 0.0
        
        while self._running:
            # 1. Process Data
            try:
                # Wait for data with short timeout to allow polling check
                chunk = self._data_queue.get(timeout=0.1)
                if chunk:
                    self._process_chunk(chunk)
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error in status monitor loop: {e}")
                
            # 2. Poll Status
            now = time.time()
            if now - last_poll_time >= self._poll_interval:
                if self._connection.is_connected():
                    self.request_status()
                last_poll_time = now
                
    def _process_chunk(self, chunk: bytes) -> None:
        """Internal method to process a single chunk."""
        with self._buffer_lock:
            # Append to buffer
            self._buffer.extend(chunk)
            
            # Trim buffer if too large
            self._trim_buffer()
            
            # Extract all complete status messages
            while True:
                status = self._try_extract_status()
                if not status:
                    break
                
                # Update latest status
                with self._status_lock:
                    self._latest_status = status
                
                # Notify subscribers
                self._notify_callbacks(status)
    
    def _try_extract_status(self) -> Optional[DongleStatus]:
        """Scan buffer for complete status message.
        
        Looks for pattern: \xFF\x34[STATUS_RESPONSE]....\xFF\x34'
        
        Returns:
            DongleStatus if complete message found and parsed, None otherwise
        """
        # Look for status response delimiter
        start_idx = self._buffer.find(ESC_STATUS_START)
        if start_idx == -1:
            return None
        
        # Look for end marker
        json_start = start_idx + len(ESC_STATUS_START)
        end_idx = self._buffer.find(ESC_STATUS_END, json_start)
        if end_idx == -1:
            # Incomplete message - wait for more data
            return None
        
        # Extract JSON bytes
        json_bytes = bytes(self._buffer[json_start:end_idx])
        
        # Remove processed bytes from buffer (including the status message)
        self._buffer = self._buffer[end_idx + len(ESC_STATUS_END):]
        
        # Parse JSON
        status = parse_status_json(json_bytes)
        
        if status is None:
            logger.warning(f"Failed to parse status JSON: {json_bytes[:100]}")
        
        return status
    
    def _trim_buffer(self) -> None:
        """Prevent buffer overflow by trimming old data.
        
        If buffer exceeds maximum size, keep only the most recent data
        (FIFO behavior).
        """
        if len(self._buffer) <= self.MAX_BUFFER_SIZE:
            return
        
        # Simple FIFO trim: keep the last MAX_BUFFER_SIZE bytes
        # This ensures we always have the most recent data window
        # without aggressive dropping.
        self._buffer = self._buffer[-self.MAX_BUFFER_SIZE:]
        logger.debug(f"Buffer trimmed to {self.MAX_BUFFER_SIZE} bytes")
    
    def get_latest_status(self) -> Optional[DongleStatus]:
        """Get most recently received status.
        
        Returns:
            Latest DongleStatus, or None if no status received yet
        """
        with self._status_lock:
            return self._latest_status
    
    def subscribe_status(self, callback: Callable[[DongleStatus], None]) -> Callable[[], None]:
        """Subscribe to status updates.
        
        Args:
            callback: Function to call with DongleStatus when received
            
        Returns:
            Unsubscribe function
        """
        with self._callback_lock:
            self._status_callbacks.append(callback)
        
        def unsubscribe():
            with self._callback_lock:
                if callback in self._status_callbacks:
                    self._status_callbacks.remove(callback)
        
        return unsubscribe
    
    def _notify_callbacks(self, status: DongleStatus) -> None:
        """Notify all status subscribers.
        
        Args:
            status: Status to send to callbacks
        """
        with self._callback_lock:
            callbacks = list(self._status_callbacks)
        
        for callback in callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def request_status(self) -> None:
        """Request status update from dongle.
        
        Sends status request command through the dongle connection.
        Status response will be detected in the byte stream.
        """
        try:
            self._connection.write(ESC_STATUS_REQUEST)
        except Exception as e:
            logger.error(f"Failed to request status: {e}")
    
    def clear_buffer(self) -> None:
        """Clear internal buffer.
        
        Useful for testing or resetting state.
        """
        with self._buffer_lock:
            self._buffer.clear()
    
    def get_buffer_size(self) -> int:
        """Get current buffer size in bytes.
        
        Returns:
            Number of bytes in internal buffer
        """
        with self._buffer_lock:
            return len(self._buffer)

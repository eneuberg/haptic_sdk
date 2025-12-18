"""Stream buffer implementation for Dongle layer.

Provides a thread-safe FIFO buffer with overwrite-on-overflow behavior.
"""
import threading
import logging

logger = logging.getLogger(__name__)

class StreamBuffer:
    """Thread-safe byte buffer with FIFO read and overwrite-on-overflow write."""
    
    def __init__(self, max_size: int = 256 * 1024):
        """Initialize buffer.
        
        Args:
            max_size: Maximum buffer size in bytes. If exceeded, oldest data is dropped.
        """
        self._max_size = max_size
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self._overflow_count = 0
        
    def write(self, data: bytes) -> None:
        """Write data to buffer.
        
        If buffer becomes full, oldest data is dropped to make room.
        """
        if not data:
            return
            
        with self._lock:
            # If new data is larger than max size, just keep the end of it
            if len(data) >= self._max_size:
                self._buffer = bytearray(data[-self._max_size:])
                self._overflow_count += 1
                logger.warning("Buffer overflow: Input chunk larger than buffer, data lost.")
                return

            # Calculate space needed
            current_len = len(self._buffer)
            new_len = current_len + len(data)
            
            if new_len > self._max_size:
                # We need to drop bytes from the start
                drop_count = new_len - self._max_size
                del self._buffer[:drop_count]
                self._overflow_count += 1
                if self._overflow_count % 100 == 1: # Log periodically
                    logger.warning(f"Buffer overflow: Dropped {drop_count} bytes of old data.")
            
            self._buffer.extend(data)
            
    def read(self, size: int = -1) -> bytes:
        """Read bytes from buffer.
        
        Args:
            size: Number of bytes to read. If -1, read all available.
            
        Returns:
            Bytes read.
        """
        with self._lock:
            if not self._buffer:
                return b""
                
            if size < 0 or size >= len(self._buffer):
                # Read all
                data = bytes(self._buffer)
                self._buffer.clear()
                return data
            else:
                # Read partial
                data = bytes(self._buffer[:size])
                del self._buffer[:size]
                return data
                
    def read_line(self) -> bytes:
        """Read a single line ending in \\n.
        
        Returns:
            Line bytes including \\n, or empty bytes if no newline found.
        """
        with self._lock:
            idx = self._buffer.find(b'\n')
            if idx == -1:
                return b""
                
            # Include the newline
            end = idx + 1
            line = bytes(self._buffer[:end])
            del self._buffer[:end]
            return line
            
    @property
    def size(self) -> int:
        """Current number of bytes in buffer."""
        with self._lock:
            return len(self._buffer)
            
    def clear(self) -> None:
        """Clear buffer."""
        with self._lock:
            self._buffer.clear()

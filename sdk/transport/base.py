"""Abstract base class for transport layer.

The Transport interface provides a clean abstraction for communication with
haptic glove hardware. Implementations can be serial, ROS2, WebSocket, or any
other protocol that can send commands and receive state updates.

Key principles:
- Immutable state updates (GloveState snapshots)
- Command-based control (no direct protocol access)
- Pub/sub pattern for state updates
- Transport-agnostic for easy swapping
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ..models import GloveState, Command


class Transport(ABC):
    """Abstract transport interface for haptic glove communication.
    
    Transports are responsible for:
    1. Managing connection lifecycle
    2. Sending commands to the glove
    3. Publishing state updates to subscribers
    
    Transports should NOT contain business logic like calibration or streaming.
    They are pure communication channels.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the glove.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the glove.
        
        Should be safe to call multiple times.
        Should clean up all resources (threads, sockets, etc.).
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is currently connected.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def subscribe_state(
        self, 
        callback: Callable[[GloveState], None]
    ) -> Callable[[], None]:
        """Subscribe to state updates from the glove.
        
        The callback will be invoked whenever a new state snapshot is available.
        Callbacks should be non-blocking to avoid delaying other subscribers.
        
        Args:
            callback: Function that receives GloveState snapshots
            
        Returns:
            Unsubscribe function to remove this callback
            
        Example:
            >>> def on_state(state: GloveState):
            ...     print(f"Position: {state.fingers['thumb'].position}")
            >>> unsubscribe = transport.subscribe_state(on_state)
            >>> # Later...
            >>> unsubscribe()
        """
        pass
    
    @abstractmethod
    def send_command(self, command: Command) -> None:
        """Send a command to the glove.
        
        Commands are queued and sent asynchronously. This method should not block.
        The transport handles serialization and protocol details.
        
        Args:
            command: Command object to send (SetpointCommand, CalibrationCommand, etc.)
            
        Example:
            >>> from haptic_glove.models import SetpointCommand
            >>> cmd = SetpointCommand(fingers={"thumb": 0.5, "index": 0.8})
            >>> transport.send_command(cmd)
        """
        pass
    
    def __enter__(self) -> Transport:
        """Context manager support - connect on enter."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager support - disconnect on exit."""
        self.disconnect()

"""Abstract base class for glove communication protocols.

Defines the interface for parsing incoming data and serializing commands.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models import Command
from .parser import StateUpdate


class Protocol(ABC):
    """Abstract protocol for glove communication.
    
    Protocols handle:
    - Parsing incoming data into state updates
    - Serializing commands into wire format
    """
    
    @abstractmethod
    def parse_line(self, line: str) -> Optional[StateUpdate]:
        """Parse incoming line into state update.
        
        Args:
            line: Decoded string from glove
            
        Returns:
            StateUpdate if line contains state data, None otherwise
        """
        pass
    
    @abstractmethod
    def serialize_command(self, command: Command) -> bytes:
        """Serialize command into wire format.
        
        Args:
            command: Command object to serialize
            
        Returns:
            Bytes ready to send to dongle/glove
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Protocol identifier (e.g., 'ascii', 'ros2')."""
        pass

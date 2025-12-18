"""ASCII text-based protocol implementation.

Wraps the existing ProtocolParser and ProtocolSerializer.
"""
from __future__ import annotations

from typing import Optional

from ..models import Command
from .base import Protocol
from .parser import ProtocolParser, StateUpdate
from .serializer import ProtocolSerializer


class ASCIIProtocol(Protocol):
    """ASCII text-based protocol for haptic glove.
    
    Uses:
    - STREAM frames for finger positions
    - STREAM_RAW for raw ADC values
    - STRIMU for IMU data
    - ! prefixed commands (e.g., !setSetpointAll)
    """
    
    def __init__(self):
        self._parser = ProtocolParser()
        self._serializer = ProtocolSerializer()
    
    def parse_line(self, line: str) -> Optional[StateUpdate]:
        """Parse a single line from the serial stream."""
        return self._parser.parse_line(line)
    
    def serialize_command(self, command: Command) -> bytes:
        """Serialize command to ASCII bytes with newline."""
        cmd_str = self._serializer.serialize_command(command)
        return (cmd_str + '\n').encode('utf-8')
    
    @property
    def name(self) -> str:
        return "ascii"

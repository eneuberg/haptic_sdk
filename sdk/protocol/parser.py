"""Protocol parser for haptic glove serial communication.

Parses incoming serial frames into structured state updates.
Pure functions with no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class UpdateType(Enum):
    """Type of state update from firmware."""
    FINGER_POSITIONS = "finger_positions"
    RAW_POSITIONS = "raw_positions"
    IMU_HEADING = "imu_heading"


@dataclass
class StateUpdate:
    """A parsed update from the firmware.
    
    Attributes:
        update_type: Type of update
        values: List of float values from the frame
    """
    update_type: UpdateType
    values: List[float]


class ProtocolParser:
    """Parser for haptic glove serial protocol.
    
    Handles three frame types:
    - STREAM <val1>,<val2>,<val3>,<val4>,<val5> - Normalized finger positions
    - STREAM_RAW <val1>,<val2>,<val3>,<val4>,<val5> - Raw sensor values
    - STRIMU <roll>,<pitch>,<yaw> - IMU orientation
    """
    
    @staticmethod
    def parse_line(line: str) -> Optional[StateUpdate]:
        """Parse a single line from the serial stream.
        
        Args:
            line: Raw line from serial (with or without newline)
            
        Returns:
            StateUpdate if line was parsed successfully, None otherwise
            
        Examples:
            >>> parser = ProtocolParser()
            >>> update = parser.parse_line("STREAM 0.5,0.6,0.7,0.8,0.9")
            >>> update.update_type
            <UpdateType.FINGER_POSITIONS: 'finger_positions'>
            >>> update.values
            [0.5, 0.6, 0.7, 0.8, 0.9]
        """
        line = line.strip()
        
        if not line:
            return None
        
        # Parse IMU data
        if line.startswith("STRIMU"):
            payload = line.replace("STRIMU", "", 1).strip()
            values = ProtocolParser._parse_csv(payload)
            if len(values) == 3:
                return StateUpdate(
                    update_type=UpdateType.IMU_HEADING,
                    values=values
                )
            return None
        
        # Parse raw finger positions
        if line.startswith("STREAM_RAW"):
            payload = line.replace("STREAM_RAW", "", 1).strip()
            values = ProtocolParser._parse_csv(payload)
            if len(values) == 5:
                return StateUpdate(
                    update_type=UpdateType.RAW_POSITIONS,
                    values=values
                )
            return None
        
        # Parse normalized finger positions
        if line.startswith("STREAM"):
            payload = line.replace("STREAM", "", 1).strip()
            values = ProtocolParser._parse_csv(payload)
            if len(values) == 5:
                return StateUpdate(
                    update_type=UpdateType.FINGER_POSITIONS,
                    values=values
                )
            return None
        
        # Unknown frame type
        return None
    
    @staticmethod
    def _parse_csv(payload: str) -> List[float]:
        """Parse comma or semicolon separated values.
        
        Args:
            payload: String with values like "1.0,2.0,3.0" or "<1.0;2.0;3.0>"
            
        Returns:
            List of parsed float values, empty list on error
        """
        # Remove angle brackets if present
        payload = payload.strip().lstrip("<").rstrip(">")
        
        if not payload:
            return []
        
        # Replace semicolons with commas
        payload = payload.replace(";", ",")
        
        result = []
        for token in payload.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                result.append(float(token))
            except ValueError:
                # Invalid float, return empty list
                return []
        
        return result

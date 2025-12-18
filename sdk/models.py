"""Immutable data models for haptic glove state and commands.

All models are frozen dataclasses to ensure immutability and thread-safety.
These models serve as the contract between transport, controller, and application layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union

# Finger identifiers
FINGER_NAMES = ("thumb", "index", "middle", "ring", "pinky")


@dataclass(frozen=True)
class FingerState:
    """Immutable state of a single finger.
    
    Attributes:
        name: Finger identifier (thumb, index, middle, ring, pinky)
        position: Normalized position 0.0 (closed) to 1.0 (open)
        setpoint: Target position for haptic feedback
        calibrated: Whether this finger has been calibrated
        enabled: Whether haptic motor is enabled
        raw_min: Minimum raw sensor value (for calibration)
        raw_max: Maximum raw sensor value (for calibration)
    """
    name: str
    position: float = 0.0
    setpoint: float = 0.0
    calibrated: bool = False
    enabled: bool = False
    raw_min: int = 4095
    raw_max: int = 0


@dataclass(frozen=True)
class IMUState:
    """Immutable IMU orientation state.
    
    Attributes:
        roll: Roll angle in degrees
        pitch: Pitch angle in degrees
        yaw: Yaw angle in degrees
    """
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class GloveState:
    """Complete immutable snapshot of glove state.
    
    This is the primary state object published by transports and
    consumed by controllers and applications.
    
    Attributes:
        timestamp: Unix timestamp when state was captured
        fingers: Dict mapping finger name to FingerState
        imu: IMU orientation state
        connected: Whether glove is connected
        calibrating: Whether calibration is in progress
        streaming: Whether finger position streaming is active
        imu_streaming: Whether IMU streaming is active
    """
    timestamp: float
    fingers: Dict[str, FingerState]
    imu: IMUState
    connected: bool = False
    calibrating: bool = False
    streaming: bool = False
    imu_streaming: bool = False


@dataclass(frozen=True)
class CalibrationData:
    """Calibration parameters for all fingers.
    
    Attributes:
        timestamp: When calibration was performed
        fingers: Dict mapping finger name to (raw_min, raw_max, invert) tuple
    """
    timestamp: float
    fingers: Dict[str, tuple[int, int, bool]]  # name -> (raw_min, raw_max, invert)
    
    def to_dict(self) -> Dict:
        """Convert to serializable dict for JSON persistence."""
        return {
            "timestamp": self.timestamp,
            "fingers": {
                name: {
                    "raw_min": params[0],
                    "raw_max": params[1],
                    "invert": params[2],
                }
                for name, params in self.fingers.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> CalibrationData:
        """Load from deserialized dict."""
        fingers = {
            name: (
                params["raw_min"],
                params["raw_max"],
                params.get("invert", False),
            )
            for name, params in data["fingers"].items()
        }
        return cls(
            timestamp=data["timestamp"],
            fingers=fingers,
        )


# Command types

class CalibrationAction(Enum):
    """Calibration command actions."""
    START = "start"
    STOP = "stop"


class StreamType(Enum):
    """Stream command types."""
    FINGER_POSITION = "finger_position"
    IMU = "imu"


@dataclass(frozen=True)
class SetpointCommand:
    """Command to set finger target positions.
    
    Attributes:
        fingers: Dict mapping finger name to target position (0.0-1.0)
        side: Optional side filter ('both', 'above', 'below')
    """
    fingers: Dict[str, float]
    side: Optional[str] = None


@dataclass(frozen=True)
class CalibrationCommand:
    """Command to start or stop calibration.
    
    Attributes:
        action: START or STOP
    """
    action: CalibrationAction


@dataclass(frozen=True)
class EnableCommand:
    """Command to enable/disable finger motors.
    
    Attributes:
        fingers: Dict mapping finger name to enabled state, or None for all
        enabled: Whether to enable (True) or disable (False)
    """
    fingers: Optional[Dict[str, bool]] = None  # None means all fingers
    enabled: bool = True


@dataclass(frozen=True)
class PIDCommand:
    """Command to set PID controller gains.
    
    Attributes:
        kp: Proportional gain (None to leave unchanged)
        kd: Derivative gain (None to leave unchanged)
        fingers: Optional dict for per-finger gains, None for global
    """
    kp: Optional[float] = None
    kd: Optional[float] = None
    fingers: Optional[Dict[str, tuple[Optional[float], Optional[float]]]] = None


@dataclass(frozen=True)
class StreamCommand:
    """Command to start or stop streaming.
    
    Attributes:
        stream_type: Type of stream (finger position or IMU)
        start: True to start streaming, False to stop
        raw: For finger position, whether to stream raw values
    """
    stream_type: StreamType
    start: bool
    raw: bool = False


@dataclass(frozen=True)
class ApplyCalibrationCommand:
    """Command to apply calibration data.
    
    Attributes:
        calibration: Calibration data to apply
    """
    calibration: CalibrationData


@dataclass(frozen=True)
class RestartCommand:
    """Command to restart the device."""
    pass


# Union type for all commands
Command = Union[
    SetpointCommand,
    CalibrationCommand,
    EnableCommand,
    PIDCommand,
    StreamCommand,
    ApplyCalibrationCommand,
    RestartCommand,
]

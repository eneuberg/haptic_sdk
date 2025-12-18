"""State builder that accumulates protocol updates into GloveState snapshots.

Maintains mutable state internally but produces immutable snapshots.
"""
from __future__ import annotations

import time
from typing import Dict

from ..models import FingerState, IMUState, GloveState, FINGER_NAMES
from .parser import StateUpdate, UpdateType


RAW_MAX = 4095


class StateBuilder:
    """Accumulates state updates and produces GloveState snapshots.
    
    The StateBuilder maintains internal mutable state (finger positions,
    calibration data, IMU values) and updates it as protocol frames arrive.
    When snapshot() is called, it produces an immutable GloveState.
    """
    
    def __init__(self):
        """Initialize with default state."""
        # Finger state (mutable internal state)
        self._fingers: Dict[str, Dict] = {
            name: {
                "name": name,
                "position": 0.0,
                "setpoint": 0.0,
                "calibrated": False,
                "enabled": False,
                "raw_min": RAW_MAX,
                "raw_max": 0,
                "invert": (name == "thumb"),  # Thumb is inverted by default
            }
            for name in FINGER_NAMES
        }
        
        # IMU state (mutable internal state)
        self._imu = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
        
        # Global flags
        self._calibrating = False
        self._streaming = False
        self._connected = False
    
    def apply(self, update: StateUpdate) -> None:
        """Apply a state update to internal state.
        
        Args:
            update: Parsed state update from protocol
        """
        if update.update_type == UpdateType.FINGER_POSITIONS:
            self._apply_finger_positions(update.values)
        elif update.update_type == UpdateType.RAW_POSITIONS:
            self._apply_raw_positions(update.values)
        elif update.update_type == UpdateType.IMU_HEADING:
            self._apply_imu_heading(update.values)
    
    def snapshot(self) -> GloveState:
        """Create an immutable snapshot of current state.
        
        Returns:
            Immutable GloveState with current values
        """
        # Create immutable finger states
        fingers = {
            name: FingerState(
                name=name,
                position=data["position"],
                setpoint=data["setpoint"],
                calibrated=data["calibrated"],
                enabled=data["enabled"],
                raw_min=data["raw_min"],
                raw_max=data["raw_max"],
            )
            for name, data in self._fingers.items()
        }
        
        # Create immutable IMU state
        imu = IMUState(
            roll=self._imu["roll"],
            pitch=self._imu["pitch"],
            yaw=self._imu["yaw"],
        )
        
        # Create immutable glove state
        return GloveState(
            timestamp=time.time(),
            fingers=fingers,
            imu=imu,
            connected=self._connected,
            calibrating=self._calibrating,
            streaming=self._streaming,
        )
    
    def set_calibrating(self, calibrating: bool) -> None:
        """Set calibration flag."""
        self._calibrating = calibrating
        if calibrating:
            # Reset calibration ranges
            for finger_data in self._fingers.values():
                finger_data["raw_min"] = RAW_MAX
                finger_data["raw_max"] = 0
    
    def set_streaming(self, streaming: bool) -> None:
        """Set streaming flag."""
        self._streaming = streaming
    
    def set_connected(self, connected: bool) -> None:
        """Set connection flag."""
        self._connected = connected
    
    def set_finger_enabled(self, finger_name: str, enabled: bool) -> None:
        """Set finger motor enabled state."""
        if finger_name in self._fingers:
            self._fingers[finger_name]["enabled"] = enabled
    
    def set_finger_setpoint(self, finger_name: str, setpoint: float) -> None:
        """Set finger target position."""
        if finger_name in self._fingers:
            self._fingers[finger_name]["setpoint"] = max(0.0, min(1.0, setpoint))
    
    def apply_calibration(self, finger_name: str, raw_min: int, raw_max: int) -> None:
        """Apply calibration data to a finger."""
        if finger_name in self._fingers:
            finger_data = self._fingers[finger_name]
            finger_data["raw_min"] = raw_min
            finger_data["raw_max"] = raw_max
            finger_data["calibrated"] = (raw_max > raw_min)
    
    def _apply_finger_positions(self, values: list[float]) -> None:
        """Apply normalized finger position update."""
        for finger_name, value in zip(FINGER_NAMES, values):
            value = max(0.0, min(1.0, value))
            self._fingers[finger_name]["position"] = value
    
    def _apply_raw_positions(self, values: list[float]) -> None:
        """Apply raw finger position update and track calibration ranges."""
        for finger_name, raw_value in zip(FINGER_NAMES, values):
            finger_data = self._fingers[finger_name]
            raw_value = max(0.0, min(RAW_MAX, raw_value))
            
            # Update calibration ranges if calibrating
            if self._calibrating:
                if raw_value < finger_data["raw_min"]:
                    finger_data["raw_min"] = int(raw_value)
                if raw_value > finger_data["raw_max"]:
                    finger_data["raw_max"] = int(raw_value)
            
            # Calculate position based on calibration
            raw_min = finger_data["raw_min"]
            raw_max = finger_data["raw_max"]
            
            if finger_data["calibrated"] and raw_max > raw_min:
                # Calibrated: map raw value to [0, 1] range
                normalized = (raw_value - raw_min) / (raw_max - raw_min)
                normalized = max(0.0, min(1.0, normalized))
                
                # Apply inversion if needed
                if finger_data["invert"]:
                    normalized = 1.0 - normalized
                
                finger_data["position"] = normalized
            else:
                # Not calibrated: use raw normalized value
                finger_data["position"] = raw_value / RAW_MAX
    
    def _apply_imu_heading(self, values: list[float]) -> None:
        """Apply IMU heading update."""
        if len(values) >= 3:
            self._imu["roll"] = values[0]
            self._imu["pitch"] = values[1]
            self._imu["yaw"] = values[2]

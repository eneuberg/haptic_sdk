"""Protocol serializer for haptic glove commands.

Converts command objects to serial protocol strings.
Pure functions with no side effects.
"""
from __future__ import annotations

from typing import Optional

from ..models import (
    Command,
    SetpointCommand,
    CalibrationCommand,
    EnableCommand,
    PIDCommand,
    StreamCommand,
    ApplyCalibrationCommand,
    RestartCommand,
    CalibrationAction,
    StreamType,
    FINGER_NAMES,
)


class ProtocolSerializer:
    """Serializer for haptic glove command protocol.
    
    Converts command objects into protocol strings that the firmware understands.
    """
    
    @staticmethod
    def serialize_command(command: Command) -> str:
        """Convert a command object to a protocol string.
        
        Args:
            command: Command object to serialize
            
        Returns:
            Protocol string ready to send over serial
            
        Examples:
            >>> cmd = SetpointCommand(fingers={"thumb": 0.5, "index": 0.8})
            >>> ProtocolSerializer.serialize_command(cmd)
            '!setSetpointAll -thumb 0.50000 -index 0.80000 ...'
        """
        if isinstance(command, SetpointCommand):
            return ProtocolSerializer._serialize_setpoint(command)
        elif isinstance(command, CalibrationCommand):
            return ProtocolSerializer._serialize_calibration(command)
        elif isinstance(command, EnableCommand):
            return ProtocolSerializer._serialize_enable(command)
        elif isinstance(command, PIDCommand):
            return ProtocolSerializer._serialize_pid(command)
        elif isinstance(command, StreamCommand):
            return ProtocolSerializer._serialize_stream(command)
        elif isinstance(command, ApplyCalibrationCommand):
            return ProtocolSerializer._serialize_apply_calibration(command)
        elif isinstance(command, RestartCommand):
            return "!restart"
        else:
            raise ValueError(f"Unknown command type: {type(command)}")
    
    @staticmethod
    def _serialize_setpoint(cmd: SetpointCommand) -> str:
        """Serialize SetpointCommand.
        
        Protocol: !setSetpointAll -thumb 0.5 -index 0.8 ... [-side both|above|below]
        """
        parts = ["!setSetpointAll"]
        
        # Add finger setpoints
        for finger_name in FINGER_NAMES:
            value = cmd.fingers.get(finger_name, 0.0)
            value = max(0.0, min(1.0, value))  # Clamp to [0, 1]
            parts.append(f"-{finger_name} {value:.5f}")
        
        # Add side filter if specified
        if cmd.side in {"both", "above", "below"}:
            parts.append(f"-side {cmd.side}")
        
        return " ".join(parts)
    
    @staticmethod
    def _serialize_calibration(cmd: CalibrationCommand) -> str:
        """Serialize CalibrationCommand.
        
        Protocol:
        - Start: !startStreamFingerPos -raw 1
        - Stop: !stopStreamFingerPos
        """
        if cmd.action == CalibrationAction.START:
            return "!startStreamFingerPos -raw 1"
        else:  # STOP
            return "!stopStreamFingerPos"
    
    @staticmethod
    def _serialize_enable(cmd: EnableCommand) -> str:
        """Serialize EnableCommand.
        
        Protocol: !setFingerEnable -finger <name> -enable <0|1>
        
        If cmd.fingers is None, enables/disables all fingers.
        """
        if cmd.fingers is None:
            # Enable/disable all fingers
            commands = []
            enable_value = 1 if cmd.enabled else 0
            for finger_name in FINGER_NAMES:
                commands.append(f"!setFingerEnable -finger {finger_name} -enable {enable_value}")
            return "\n".join(commands)
        else:
            # Enable/disable specific fingers
            commands = []
            for finger_name, enabled in cmd.fingers.items():
                enable_value = 1 if enabled else 0
                commands.append(f"!setFingerEnable -finger {finger_name} -enable {enable_value}")
            return "\n".join(commands)
    
    @staticmethod
    def _serialize_pid(cmd: PIDCommand) -> str:
        """Serialize PIDCommand.
        
        Protocol:
        - Global: !setKpAll -kp <value>, !setKdAll -kd <value>
        - Per-finger: !setFingerPID -finger <name> -kp <value> -kd <value>
        """
        commands = []
        
        if cmd.fingers is None:
            # Global PID
            if cmd.kp is not None:
                commands.append(f"!setKpAll -kp {cmd.kp:.5f}")
            if cmd.kd is not None:
                commands.append(f"!setKdAll -kd {cmd.kd:.5f}")
        else:
            # Per-finger PID
            for finger_name, (kp, kd) in cmd.fingers.items():
                parts = [f"!setFingerPID -finger {finger_name}"]
                if kp is not None:
                    parts.append(f"-kp {kp:.5f}")
                if kd is not None:
                    parts.append(f"-kd {kd:.5f}")
                commands.append(" ".join(parts))
        
        return "\n".join(commands) if commands else ""
    
    @staticmethod
    def _serialize_stream(cmd: StreamCommand) -> str:
        """Serialize StreamCommand.
        
        Protocol:
        - Start finger stream: !startStreamFingerPos [-raw 1]
        - Stop finger stream: !stopStreamFingerPos
        - Start IMU stream: !startImuStream
        - Stop IMU stream: !stopImuStream
        """
        if cmd.stream_type == StreamType.FINGER_POSITION:
            if cmd.start:
                if cmd.raw:
                    return "!startStreamFingerPos -raw 1"
                else:
                    return "!startStreamFingerPos"
            else:
                return "!stopStreamFingerPos"
        else:  # IMU
            if cmd.start:
                return "!startImuStream"
            else:
                return "!stopImuStream"
    
    @staticmethod
    def _serialize_apply_calibration(cmd: ApplyCalibrationCommand) -> str:
        """Serialize ApplyCalibrationCommand.
        
        Protocol: !setFingerCalibration -finger <name> -min <value> -max <value>
        """
        commands = []
        
        for finger_name, (raw_min, raw_max, invert) in cmd.calibration.fingers.items():
            commands.append(
                f"!setFingerCalibration -finger {finger_name} "
                f"-min {raw_min} -max {raw_max}"
            )
        
        return "\n".join(commands)

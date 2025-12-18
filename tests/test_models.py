"""Unit tests for immutable data models (Phase 1).

Tests verify:
- Immutability (frozen dataclasses)
- Type correctness
- Serialization/deserialization
- Default values
- Command creation
"""
import unittest
import time
from dataclasses import FrozenInstanceError

from sdk.models import (
    FingerState,
    IMUState,
    GloveState,
    CalibrationData,
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


class TestFingerState(unittest.TestCase):
    """Tests for FingerState immutable model."""
    
    def test_creation_with_defaults(self):
        """Test creating finger state with default values."""
        finger = FingerState(name="thumb")
        self.assertEqual(finger.name, "thumb")
        self.assertEqual(finger.position, 0.0)
        self.assertEqual(finger.setpoint, 0.0)
        self.assertFalse(finger.calibrated)
        self.assertFalse(finger.enabled)
        self.assertEqual(finger.raw_min, 4095)
        self.assertEqual(finger.raw_max, 0)
    
    def test_creation_with_custom_values(self):
        """Test creating finger state with custom values."""
        finger = FingerState(
            name="index",
            position=0.75,
            setpoint=0.5,
            calibrated=True,
            enabled=True,
            raw_min=100,
            raw_max=4000,
        )
        self.assertEqual(finger.name, "index")
        self.assertEqual(finger.position, 0.75)
        self.assertEqual(finger.setpoint, 0.5)
        self.assertTrue(finger.calibrated)
        self.assertTrue(finger.enabled)
        self.assertEqual(finger.raw_min, 100)
        self.assertEqual(finger.raw_max, 4000)
    
    def test_immutability(self):
        """Test that FingerState is immutable."""
        finger = FingerState(name="thumb", position=0.5)
        with self.assertRaises(FrozenInstanceError):
            finger.position = 0.8
        with self.assertRaises(FrozenInstanceError):
            finger.enabled = True


class TestIMUState(unittest.TestCase):
    """Tests for IMUState immutable model."""
    
    def test_creation_with_defaults(self):
        """Test creating IMU state with default values."""
        imu = IMUState()
        self.assertEqual(imu.roll, 0.0)
        self.assertEqual(imu.pitch, 0.0)
        self.assertEqual(imu.yaw, 0.0)
    
    def test_creation_with_custom_values(self):
        """Test creating IMU state with custom values."""
        imu = IMUState(roll=10.5, pitch=-5.2, yaw=180.0)
        self.assertEqual(imu.roll, 10.5)
        self.assertEqual(imu.pitch, -5.2)
        self.assertEqual(imu.yaw, 180.0)
    
    def test_immutability(self):
        """Test that IMUState is immutable."""
        imu = IMUState(roll=1.0)
        with self.assertRaises(FrozenInstanceError):
            imu.roll = 2.0


class TestGloveState(unittest.TestCase):
    """Tests for GloveState immutable model."""
    
    def test_creation_minimal(self):
        """Test creating glove state with minimal required fields."""
        timestamp = time.time()
        fingers = {name: FingerState(name=name) for name in FINGER_NAMES}
        imu = IMUState()
        
        state = GloveState(
            timestamp=timestamp,
            fingers=fingers,
            imu=imu,
        )
        
        self.assertEqual(state.timestamp, timestamp)
        self.assertEqual(len(state.fingers), 5)
        self.assertEqual(state.imu.roll, 0.0)
        self.assertFalse(state.connected)
        self.assertFalse(state.calibrating)
        self.assertFalse(state.streaming)
        self.assertFalse(state.imu_streaming)
    
    def test_creation_complete(self):
        """Test creating glove state with all fields."""
        timestamp = time.time()
        fingers = {
            name: FingerState(name=name, position=0.5, calibrated=True)
            for name in FINGER_NAMES
        }
        imu = IMUState(roll=1.0, pitch=2.0, yaw=3.0)
        
        state = GloveState(
            timestamp=timestamp,
            fingers=fingers,
            imu=imu,
            connected=True,
            calibrating=True,
            streaming=True,
            imu_streaming=True,
        )
        
        self.assertTrue(state.connected)
        self.assertTrue(state.calibrating)
        self.assertTrue(state.streaming)
        self.assertTrue(state.imu_streaming)
        self.assertTrue(all(f.calibrated for f in state.fingers.values()))
    
    def test_immutability(self):
        """Test that GloveState is immutable."""
        state = GloveState(
            timestamp=time.time(),
            fingers={},
            imu=IMUState(),
        )
        with self.assertRaises(FrozenInstanceError):
            state.connected = True
        with self.assertRaises(FrozenInstanceError):
            state.timestamp = time.time()


class TestCalibrationData(unittest.TestCase):
    """Tests for CalibrationData model and serialization."""
    
    def test_creation(self):
        """Test creating calibration data."""
        timestamp = time.time()
        fingers = {
            "thumb": (100, 4000, True),
            "index": (150, 3900, False),
        }
        
        cal = CalibrationData(timestamp=timestamp, fingers=fingers)
        
        self.assertEqual(cal.timestamp, timestamp)
        self.assertEqual(len(cal.fingers), 2)
        self.assertEqual(cal.fingers["thumb"], (100, 4000, True))
        self.assertEqual(cal.fingers["index"], (150, 3900, False))
    
    def test_serialization_to_dict(self):
        """Test converting calibration data to dict."""
        timestamp = 1234567890.0
        fingers = {
            "thumb": (100, 4000, True),
            "index": (150, 3900, False),
        }
        cal = CalibrationData(timestamp=timestamp, fingers=fingers)
        
        data = cal.to_dict()
        
        self.assertEqual(data["timestamp"], timestamp)
        self.assertEqual(data["fingers"]["thumb"]["raw_min"], 100)
        self.assertEqual(data["fingers"]["thumb"]["raw_max"], 4000)
        self.assertTrue(data["fingers"]["thumb"]["invert"])
        self.assertEqual(data["fingers"]["index"]["raw_min"], 150)
        self.assertEqual(data["fingers"]["index"]["raw_max"], 3900)
        self.assertFalse(data["fingers"]["index"]["invert"])
    
    def test_deserialization_from_dict(self):
        """Test loading calibration data from dict."""
        data = {
            "timestamp": 1234567890.0,
            "fingers": {
                "thumb": {"raw_min": 100, "raw_max": 4000, "invert": True},
                "index": {"raw_min": 150, "raw_max": 3900, "invert": False},
            }
        }
        
        cal = CalibrationData.from_dict(data)
        
        self.assertEqual(cal.timestamp, 1234567890.0)
        self.assertEqual(cal.fingers["thumb"], (100, 4000, True))
        self.assertEqual(cal.fingers["index"], (150, 3900, False))
    
    def test_round_trip_serialization(self):
        """Test that serialization round-trip preserves data."""
        original = CalibrationData(
            timestamp=time.time(),
            fingers={
                "thumb": (100, 4000, True),
                "index": (150, 3900, False),
                "middle": (200, 3800, False),
            }
        )
        
        data = original.to_dict()
        restored = CalibrationData.from_dict(data)
        
        self.assertEqual(restored.timestamp, original.timestamp)
        self.assertEqual(restored.fingers, original.fingers)
    
    def test_immutability(self):
        """Test that CalibrationData is immutable."""
        cal = CalibrationData(timestamp=time.time(), fingers={})
        with self.assertRaises(FrozenInstanceError):
            cal.timestamp = time.time()


class TestCommands(unittest.TestCase):
    """Tests for command types."""
    
    def test_setpoint_command(self):
        """Test SetpointCommand creation."""
        cmd = SetpointCommand(
            fingers={"thumb": 0.5, "index": 0.8},
            side="above"
        )
        self.assertEqual(cmd.fingers["thumb"], 0.5)
        self.assertEqual(cmd.fingers["index"], 0.8)
        self.assertEqual(cmd.side, "above")
        
        # Test without side
        cmd2 = SetpointCommand(fingers={"thumb": 0.3})
        self.assertIsNone(cmd2.side)
    
    def test_calibration_command(self):
        """Test CalibrationCommand creation."""
        cmd_start = CalibrationCommand(action=CalibrationAction.START)
        self.assertEqual(cmd_start.action, CalibrationAction.START)
        
        cmd_stop = CalibrationCommand(action=CalibrationAction.STOP)
        self.assertEqual(cmd_stop.action, CalibrationAction.STOP)
    
    def test_enable_command(self):
        """Test EnableCommand creation."""
        # Enable all
        cmd1 = EnableCommand(enabled=True)
        self.assertIsNone(cmd1.fingers)
        self.assertTrue(cmd1.enabled)
        
        # Disable all
        cmd2 = EnableCommand(enabled=False)
        self.assertFalse(cmd2.enabled)
        
        # Enable specific fingers
        cmd3 = EnableCommand(
            fingers={"thumb": True, "index": False},
            enabled=True
        )
        self.assertTrue(cmd3.fingers["thumb"])
        self.assertFalse(cmd3.fingers["index"])
    
    def test_pid_command(self):
        """Test PIDCommand creation."""
        # Global PID
        cmd1 = PIDCommand(kp=1.5, kd=0.3)
        self.assertEqual(cmd1.kp, 1.5)
        self.assertEqual(cmd1.kd, 0.3)
        self.assertIsNone(cmd1.fingers)
        
        # Only Kp
        cmd2 = PIDCommand(kp=2.0)
        self.assertEqual(cmd2.kp, 2.0)
        self.assertIsNone(cmd2.kd)
        
        # Per-finger PID
        cmd3 = PIDCommand(
            fingers={"thumb": (1.5, 0.3), "index": (2.0, None)}
        )
        self.assertEqual(cmd3.fingers["thumb"], (1.5, 0.3))
        self.assertEqual(cmd3.fingers["index"], (2.0, None))
    
    def test_stream_command(self):
        """Test StreamCommand creation."""
        # Start finger position stream
        cmd1 = StreamCommand(
            stream_type=StreamType.FINGER_POSITION,
            start=True,
            raw=False
        )
        self.assertEqual(cmd1.stream_type, StreamType.FINGER_POSITION)
        self.assertTrue(cmd1.start)
        self.assertFalse(cmd1.raw)
        
        # Start raw stream
        cmd2 = StreamCommand(
            stream_type=StreamType.FINGER_POSITION,
            start=True,
            raw=True
        )
        self.assertTrue(cmd2.raw)
        
        # Stop IMU stream
        cmd3 = StreamCommand(
            stream_type=StreamType.IMU,
            start=False
        )
        self.assertEqual(cmd3.stream_type, StreamType.IMU)
        self.assertFalse(cmd3.start)
    
    def test_apply_calibration_command(self):
        """Test ApplyCalibrationCommand creation."""
        cal = CalibrationData(
            timestamp=time.time(),
            fingers={"thumb": (100, 4000, True)}
        )
        cmd = ApplyCalibrationCommand(calibration=cal)
        self.assertEqual(cmd.calibration, cal)
    
    def test_restart_command(self):
        """Test RestartCommand creation."""
        cmd = RestartCommand()
        self.assertIsNotNone(cmd)
    
    def test_command_immutability(self):
        """Test that commands are immutable."""
        cmd = SetpointCommand(fingers={"thumb": 0.5})
        with self.assertRaises(FrozenInstanceError):
            cmd.fingers = {"index": 0.3}


class TestConstants(unittest.TestCase):
    """Tests for module constants."""
    
    def test_finger_names(self):
        """Test that FINGER_NAMES contains expected values."""
        self.assertEqual(len(FINGER_NAMES), 5)
        self.assertIn("thumb", FINGER_NAMES)
        self.assertIn("index", FINGER_NAMES)
        self.assertIn("middle", FINGER_NAMES)
        self.assertIn("ring", FINGER_NAMES)
        self.assertIn("pinky", FINGER_NAMES)

if __name__ == '__main__':
    unittest.main()
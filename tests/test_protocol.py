"""Unit tests for Protocol layer (Phase 3).

Tests verify:
- Parser handles all frame types correctly
- Serializer produces correct protocol strings
- StateBuilder accumulates updates correctly
- Edge cases and malformed input
"""
import sys
import time

sys.path.insert(0, '.')

from sdk.protocol import ProtocolParser, ProtocolSerializer, StateBuilder, StateUpdate, UpdateType
from sdk.models import (
    SetpointCommand, CalibrationCommand, EnableCommand, PIDCommand,
    StreamCommand, ApplyCalibrationCommand, RestartCommand,
    CalibrationAction, StreamType, CalibrationData, FINGER_NAMES
)


def run_tests():
    """Run all Phase 3 protocol tests."""
    print('=' * 60)
    print('PHASE 3: PROTOCOL LAYER TESTS')
    print('=' * 60)
    
    test_count = 0
    passed = 0
    
    def test(name):
        nonlocal test_count
        test_count += 1
        print(f'{test_count}. {name}', end=' ... ')
    
    def ok():
        nonlocal passed
        passed += 1
        print('✓')
    
    def fail(msg):
        print(f'✗ FAILED: {msg}')
        sys.exit(1)
    
    # ===== PARSER TESTS =====
    
    test('Parse STREAM frame')
    update = ProtocolParser.parse_line("STREAM 0.1,0.2,0.3,0.4,0.5")
    if not update or update.update_type != UpdateType.FINGER_POSITIONS:
        fail('Failed to parse STREAM')
    if update.values != [0.1, 0.2, 0.3, 0.4, 0.5]:
        fail(f'Wrong values: {update.values}')
    ok()
    
    test('Parse STREAM_RAW frame')
    update = ProtocolParser.parse_line("STREAM_RAW 100,200,300,400,500")
    if not update or update.update_type != UpdateType.RAW_POSITIONS:
        fail('Failed to parse STREAM_RAW')
    if update.values != [100.0, 200.0, 300.0, 400.0, 500.0]:
        fail(f'Wrong values: {update.values}')
    ok()
    
    test('Parse STRIMU frame')
    update = ProtocolParser.parse_line("STRIMU 10.5,-5.2,180.0")
    if not update or update.update_type != UpdateType.IMU_HEADING:
        fail('Failed to parse STRIMU')
    if update.values != [10.5, -5.2, 180.0]:
        fail(f'Wrong values: {update.values}')
    ok()
    
    test('Parse frame with angle brackets')
    update = ProtocolParser.parse_line("STREAM <0.5,0.6,0.7,0.8,0.9>")
    if not update or len(update.values) != 5:
        fail('Failed to parse with angle brackets')
    ok()
    
    test('Parse frame with semicolons')
    update = ProtocolParser.parse_line("STRIMU 1.0;2.0;3.0")
    if not update or update.values != [1.0, 2.0, 3.0]:
        fail('Failed to parse semicolons')
    ok()
    
    test('Parse frame with extra whitespace')
    update = ProtocolParser.parse_line("  STREAM  0.1 , 0.2 , 0.3 , 0.4 , 0.5  ")
    if not update or len(update.values) != 5:
        fail('Failed to parse with whitespace')
    ok()
    
    test('Parse empty line')
    update = ProtocolParser.parse_line("")
    if update is not None:
        fail('Empty line should return None')
    ok()
    
    test('Parse unknown frame type')
    update = ProtocolParser.parse_line("UNKNOWN 1,2,3")
    if update is not None:
        fail('Unknown frame should return None')
    ok()
    
    test('Parse malformed STREAM (wrong count)')
    update = ProtocolParser.parse_line("STREAM 0.1,0.2,0.3")
    if update is not None:
        fail('Malformed STREAM should return None')
    ok()
    
    test('Parse malformed values (non-numeric)')
    update = ProtocolParser.parse_line("STREAM a,b,c,d,e")
    if update is not None:
        fail('Non-numeric values should return None')
    ok()
    
    # ===== SERIALIZER TESTS =====
    
    test('Serialize SetpointCommand')
    cmd = SetpointCommand(fingers={"thumb": 0.5, "index": 0.8})
    result = ProtocolSerializer.serialize_command(cmd)
    if not result.startswith("!setSetpointAll"):
        fail('Wrong command prefix')
    if "-thumb 0.50000" not in result:
        fail('Thumb value missing')
    if "-index 0.80000" not in result:
        fail('Index value missing')
    ok()
    
    test('Serialize SetpointCommand with side')
    cmd = SetpointCommand(fingers={"thumb": 0.5}, side="above")
    result = ProtocolSerializer.serialize_command(cmd)
    if "-side above" not in result:
        fail('Side parameter missing')
    ok()
    
    test('Serialize CalibrationCommand START')
    cmd = CalibrationCommand(action=CalibrationAction.START)
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!startStreamFingerPos -raw 1":
        fail(f'Wrong command: {result}')
    ok()
    
    test('Serialize CalibrationCommand STOP')
    cmd = CalibrationCommand(action=CalibrationAction.STOP)
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!stopStreamFingerPos":
        fail(f'Wrong command: {result}')
    ok()
    
    test('Serialize EnableCommand all fingers')
    cmd = EnableCommand(enabled=True)
    result = ProtocolSerializer.serialize_command(cmd)
    lines = result.split('\n')
    if len(lines) != 5:
        fail(f'Expected 5 lines, got {len(lines)}')
    if not all("!setFingerEnable" in line for line in lines):
        fail('Missing enable commands')
    ok()
    
    test('Serialize EnableCommand specific fingers')
    cmd = EnableCommand(fingers={"thumb": True, "index": False}, enabled=True)
    result = ProtocolSerializer.serialize_command(cmd)
    if "-finger thumb -enable 1" not in result:
        fail('Thumb enable missing')
    if "-finger index -enable 0" not in result:
        fail('Index disable missing')
    ok()
    
    test('Serialize PIDCommand global')
    cmd = PIDCommand(kp=1.5, kd=0.3)
    result = ProtocolSerializer.serialize_command(cmd)
    if "!setKpAll -kp 1.50000" not in result:
        fail('Kp command missing')
    if "!setKdAll -kd 0.30000" not in result:
        fail('Kd command missing')
    ok()
    
    test('Serialize PIDCommand partial')
    cmd = PIDCommand(kp=2.0)
    result = ProtocolSerializer.serialize_command(cmd)
    if "!setKpAll" not in result:
        fail('Kp command missing')
    if "!setKdAll" in result:
        fail('Kd should not be present')
    ok()
    
    test('Serialize StreamCommand finger start')
    cmd = StreamCommand(stream_type=StreamType.FINGER_POSITION, start=True, raw=False)
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!startStreamFingerPos":
        fail(f'Wrong command: {result}')
    ok()
    
    test('Serialize StreamCommand finger start raw')
    cmd = StreamCommand(stream_type=StreamType.FINGER_POSITION, start=True, raw=True)
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!startStreamFingerPos -raw 1":
        fail(f'Wrong command: {result}')
    ok()
    
    test('Serialize StreamCommand IMU')
    cmd = StreamCommand(stream_type=StreamType.IMU, start=True)
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!startImuStream":
        fail(f'Wrong command: {result}')
    ok()
    
    test('Serialize ApplyCalibrationCommand')
    cal = CalibrationData(
        timestamp=time.time(),
        fingers={"thumb": (100, 4000, True), "index": (150, 3900, False)}
    )
    cmd = ApplyCalibrationCommand(calibration=cal)
    result = ProtocolSerializer.serialize_command(cmd)
    if "-finger thumb -min 100 -max 4000" not in result:
        fail('Thumb calibration missing')
    if "-finger index -min 150 -max 3900" not in result:
        fail('Index calibration missing')
    ok()
    
    test('Serialize RestartCommand')
    cmd = RestartCommand()
    result = ProtocolSerializer.serialize_command(cmd)
    if result != "!restart":
        fail(f'Wrong command: {result}')
    ok()
    
    # ===== STATE BUILDER TESTS =====
    
    test('StateBuilder initial state')
    builder = StateBuilder()
    state = builder.snapshot()
    if len(state.fingers) != 5:
        fail(f'Wrong finger count: {len(state.fingers)}')
    if state.connected or state.calibrating or state.streaming:
        fail('Initial flags should be False')
    ok()
    
    test('StateBuilder apply finger positions')
    builder = StateBuilder()
    update = StateUpdate(UpdateType.FINGER_POSITIONS, [0.1, 0.2, 0.3, 0.4, 0.5])
    builder.apply(update)
    state = builder.snapshot()
    if state.fingers["thumb"].position != 0.1:
        fail('Thumb position wrong')
    if state.fingers["pinky"].position != 0.5:
        fail('Pinky position wrong')
    ok()
    
    test('StateBuilder apply raw positions')
    builder = StateBuilder()
    update = StateUpdate(UpdateType.RAW_POSITIONS, [500, 1000, 1500, 2000, 2500])
    builder.apply(update)
    state = builder.snapshot()
    # Without calibration, should use raw normalized values
    if state.fingers["thumb"].position <= 0:
        fail('Thumb position not set')
    ok()
    
    test('StateBuilder apply IMU')
    builder = StateBuilder()
    update = StateUpdate(UpdateType.IMU_HEADING, [10.5, -5.2, 180.0])
    builder.apply(update)
    state = builder.snapshot()
    if state.imu.roll != 10.5 or state.imu.pitch != -5.2 or state.imu.yaw != 180.0:
        fail(f'IMU values wrong: {state.imu.roll}, {state.imu.pitch}, {state.imu.yaw}')
    ok()
    
    test('StateBuilder calibration workflow')
    builder = StateBuilder()
    builder.set_calibrating(True)
    
    # Send raw values during calibration
    update1 = StateUpdate(UpdateType.RAW_POSITIONS, [100, 150, 200, 250, 300])
    builder.apply(update1)
    update2 = StateUpdate(UpdateType.RAW_POSITIONS, [4000, 3900, 3800, 3700, 3600])
    builder.apply(update2)
    
    state = builder.snapshot()
    if not state.calibrating:
        fail('Calibrating flag not set')
    if state.fingers["thumb"].raw_min != 100:
        fail(f'Thumb raw_min wrong: {state.fingers["thumb"].raw_min}')
    if state.fingers["thumb"].raw_max != 4000:
        fail(f'Thumb raw_max wrong: {state.fingers["thumb"].raw_max}')
    ok()
    
    test('StateBuilder apply calibration')
    builder = StateBuilder()
    builder.apply_calibration("thumb", 100, 4000)
    state = builder.snapshot()
    if not state.fingers["thumb"].calibrated:
        fail('Finger not marked as calibrated')
    if state.fingers["thumb"].raw_min != 100:
        fail('Calibration min not applied')
    ok()
    
    test('StateBuilder set flags')
    builder = StateBuilder()
    builder.set_connected(True)
    builder.set_streaming(True)
    builder.set_calibrating(True)
    state = builder.snapshot()
    if not (state.connected and state.streaming and state.calibrating):
        fail('Flags not set correctly')
    ok()
    
    test('StateBuilder set finger enabled')
    builder = StateBuilder()
    builder.set_finger_enabled("thumb", True)
    builder.set_finger_enabled("index", False)
    state = builder.snapshot()
    if not state.fingers["thumb"].enabled:
        fail('Thumb not enabled')
    if state.fingers["index"].enabled:
        fail('Index should not be enabled')
    ok()
    
    test('StateBuilder set finger setpoint')
    builder = StateBuilder()
    builder.set_finger_setpoint("thumb", 0.75)
    state = builder.snapshot()
    if state.fingers["thumb"].setpoint != 0.75:
        fail(f'Setpoint wrong: {state.fingers["thumb"].setpoint}')
    ok()
    
    test('StateBuilder setpoint clamping')
    builder = StateBuilder()
    builder.set_finger_setpoint("thumb", 1.5)  # Should clamp to 1.0
    builder.set_finger_setpoint("index", -0.5)  # Should clamp to 0.0
    state = builder.snapshot()
    if state.fingers["thumb"].setpoint != 1.0:
        fail('Setpoint not clamped to 1.0')
    if state.fingers["index"].setpoint != 0.0:
        fail('Setpoint not clamped to 0.0')
    ok()
    
    test('StateBuilder multiple updates')
    builder = StateBuilder()
    for i in range(10):
        update = StateUpdate(UpdateType.FINGER_POSITIONS, [i/10.0] * 5)
        builder.apply(update)
    state = builder.snapshot()
    if abs(state.fingers["thumb"].position - 0.9) > 0.01:
        fail('Final position wrong after multiple updates')
    ok()
    
    test('StateBuilder immutable snapshots')
    builder = StateBuilder()
    state1 = builder.snapshot()
    builder.set_connected(True)
    state2 = builder.snapshot()
    if state1.connected:
        fail('Previous snapshot was mutated')
    if not state2.connected:
        fail('New snapshot not updated')
    ok()
    
    # ===== INTEGRATION TESTS =====
    
    test('Parse then apply to StateBuilder')
    builder = StateBuilder()
    line = "STREAM 0.5,0.6,0.7,0.8,0.9"
    update = ProtocolParser.parse_line(line)
    builder.apply(update)
    state = builder.snapshot()
    if state.fingers["thumb"].position != 0.5:
        fail('Integration failed')
    ok()
    
    test('Serialize then verify format')
    cmd = SetpointCommand(fingers={"thumb": 0.5})
    protocol_str = ProtocolSerializer.serialize_command(cmd)
    if not protocol_str.startswith("!"):
        fail('Protocol string should start with !')
    if "thumb" not in protocol_str:
        fail('Protocol missing finger name')
    ok()
    
    print('=' * 60)
    print(f'RESULTS: {passed}/{test_count} tests passed')
    print('=' * 60)
    
    if passed == test_count:
        print('✅ ALL TESTS PASSED')
        return True
    else:
        print('❌ SOME TESTS FAILED')
        return False


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

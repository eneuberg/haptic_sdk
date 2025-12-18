"""Unit tests for Transport abstraction (Phase 2).

Tests verify:
- Transport is properly abstract (can't be instantiated)
- All required methods are abstract
- Context manager support
- Type signatures
- Multiple subscribers
- Thread safety
- Error handling
- Edge cases
"""
import sys
import time
import threading
from abc import ABC

sys.path.insert(0, '.')

from sdk.transport.base import Transport
from sdk.models import (
    GloveState, FingerState, IMUState, FINGER_NAMES,
    SetpointCommand, CalibrationCommand, EnableCommand,
    PIDCommand, StreamCommand, ApplyCalibrationCommand,
    RestartCommand, CalibrationAction, StreamType,
    CalibrationData, Command
)


class TestTransportABC:
    """Tests for Transport abstract base class."""
    
    def test_is_abstract(self):
        """Test that Transport cannot be instantiated directly."""
        try:
            transport = Transport()
            return False, "Transport should be abstract"
        except TypeError as e:
            if "abstract" in str(e).lower():
                return True, "Transport is properly abstract"
            return False, f"Wrong error: {e}"
    
    def test_has_connect_method(self):
        """Test that Transport defines connect method."""
        if not hasattr(Transport, 'connect'):
            return False, "Missing connect method"
        if not callable(getattr(Transport, 'connect')):
            return False, "connect is not callable"
        return True, "connect method exists"
    
    def test_has_disconnect_method(self):
        """Test that Transport defines disconnect method."""
        if not hasattr(Transport, 'disconnect'):
            return False, "Missing disconnect method"
        if not callable(getattr(Transport, 'disconnect')):
            return False, "disconnect is not callable"
        return True, "disconnect method exists"
    
    def test_has_is_connected_method(self):
        """Test that Transport defines is_connected method."""
        if not hasattr(Transport, 'is_connected'):
            return False, "Missing is_connected method"
        if not callable(getattr(Transport, 'is_connected')):
            return False, "is_connected is not callable"
        return True, "is_connected method exists"
    
    def test_has_subscribe_state_method(self):
        """Test that Transport defines subscribe_state method."""
        if not hasattr(Transport, 'subscribe_state'):
            return False, "Missing subscribe_state method"
        if not callable(getattr(Transport, 'subscribe_state')):
            return False, "subscribe_state is not callable"
        return True, "subscribe_state method exists"
    
    def test_has_send_command_method(self):
        """Test that Transport defines send_command method."""
        if not hasattr(Transport, 'send_command'):
            return False, "Missing send_command method"
        if not callable(getattr(Transport, 'send_command')):
            return False, "send_command is not callable"
        return True, "send_command method exists"
    
    def test_is_abc_subclass(self):
        """Test that Transport inherits from ABC."""
        if not issubclass(Transport, ABC):
            return False, "Transport should inherit from ABC"
        return True, "Transport inherits from ABC"
    
    def test_context_manager_support(self):
        """Test that Transport has context manager methods."""
        if not hasattr(Transport, '__enter__'):
            return False, "Missing __enter__ method"
        if not hasattr(Transport, '__exit__'):
            return False, "Missing __exit__ method"
        return True, "Context manager methods exist"


class ConcreteTransport(Transport):
    """Concrete implementation for testing with realistic behavior."""
    
    def __init__(self, fail_connect=False, auto_disconnect=False):
        self.connected = False
        self.commands = []
        self.subscribers = []
        self.fail_connect = fail_connect
        self.auto_disconnect = auto_disconnect
        self.state_history = []
        self._lock = threading.Lock()
        self.connect_count = 0
        self.disconnect_count = 0
    
    def connect(self) -> bool:
        with self._lock:
            self.connect_count += 1
            if self.fail_connect:
                return False
            self.connected = True
            return True
    
    def disconnect(self) -> None:
        with self._lock:
            self.disconnect_count += 1
            self.connected = False
            self.subscribers.clear()
    
    def is_connected(self) -> bool:
        with self._lock:
            if self.auto_disconnect and self.connected:
                self.connected = False
            return self.connected
    
    def subscribe_state(self, callback):
        with self._lock:
            self.subscribers.append(callback)
        
        def unsubscribe():
            with self._lock:
                if callback in self.subscribers:
                    self.subscribers.remove(callback)
        
        return unsubscribe
    
    def send_command(self, command: Command) -> None:
        with self._lock:
            self.commands.append(command)
    
    def publish_state(self, state: GloveState) -> None:
        """Helper method to simulate state updates."""
        with self._lock:
            self.state_history.append(state)
            subscribers = list(self.subscribers)
        
        for callback in subscribers:
            try:
                callback(state)
            except Exception:
                pass  # Don't let one bad subscriber break others


class TestConcreteImplementation:
    """Tests for concrete Transport implementation."""
    
    def test_can_instantiate_concrete(self):
        """Test that concrete implementation can be instantiated."""
        try:
            transport = ConcreteTransport()
            return True, "Concrete transport instantiated"
        except Exception as e:
            return False, f"Failed to instantiate: {e}"
    
    def test_connect_works(self):
        """Test that connect method works."""
        transport = ConcreteTransport()
        result = transport.connect()
        if not result:
            return False, "connect returned False"
        if not transport.is_connected():
            return False, "is_connected returned False after connect"
        return True, "connect works"
    
    def test_connect_failure(self):
        """Test that connect can fail gracefully."""
        transport = ConcreteTransport(fail_connect=True)
        result = transport.connect()
        if result:
            return False, "connect should have failed"
        if transport.is_connected():
            return False, "Should not be connected after failed connect"
        return True, "connect failure handled"
    
    def test_disconnect_works(self):
        """Test that disconnect method works."""
        transport = ConcreteTransport()
        transport.connect()
        transport.disconnect()
        if transport.is_connected():
            return False, "Still connected after disconnect"
        return True, "disconnect works"
    
    def test_disconnect_idempotent(self):
        """Test that disconnect can be called multiple times safely."""
        transport = ConcreteTransport()
        transport.connect()
        transport.disconnect()
        transport.disconnect()
        transport.disconnect()
        if transport.disconnect_count != 3:
            return False, f"Expected 3 disconnect calls, got {transport.disconnect_count}"
        return True, "disconnect is idempotent"
    
    def test_connect_without_disconnect(self):
        """Test multiple connects without disconnect."""
        transport = ConcreteTransport()
        transport.connect()
        transport.connect()
        if transport.connect_count != 2:
            return False, f"Expected 2 connect calls, got {transport.connect_count}"
        return True, "multiple connects work"
    
    def test_subscribe_state_works(self):
        """Test that subscribe_state returns unsubscribe function."""
        transport = ConcreteTransport()
        called = []
        
        def callback(state):
            called.append(state)
        
        unsubscribe = transport.subscribe_state(callback)
        if not callable(unsubscribe):
            return False, "subscribe_state didn't return callable"
        
        if callback not in transport.subscribers:
            return False, "callback not added to subscribers"
        
        unsubscribe()
        if callback in transport.subscribers:
            return False, "callback not removed after unsubscribe"
        
        return True, "subscribe_state works"
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers can coexist."""
        transport = ConcreteTransport()
        called1 = []
        called2 = []
        called3 = []
        
        unsub1 = transport.subscribe_state(lambda s: called1.append(s))
        unsub2 = transport.subscribe_state(lambda s: called2.append(s))
        unsub3 = transport.subscribe_state(lambda s: called3.append(s))
        
        if len(transport.subscribers) != 3:
            return False, f"Expected 3 subscribers, got {len(transport.subscribers)}"
        
        # Publish state
        state = GloveState(
            timestamp=time.time(),
            fingers={name: FingerState(name=name) for name in FINGER_NAMES},
            imu=IMUState(),
        )
        transport.publish_state(state)
        
        if len(called1) != 1 or len(called2) != 1 or len(called3) != 1:
            return False, "Not all subscribers received state"
        
        # Unsubscribe one
        unsub2()
        if len(transport.subscribers) != 2:
            return False, "Subscriber not removed"
        
        # Publish again
        transport.publish_state(state)
        if len(called1) != 2 or len(called2) != 1 or len(called3) != 2:
            return False, "Unsubscribed callback was called"
        
        return True, "multiple subscribers work"
    
    def test_subscriber_exception_doesnt_break_others(self):
        """Test that one subscriber's exception doesn't affect others."""
        transport = ConcreteTransport()
        called = []
        
        def bad_callback(state):
            raise RuntimeError("Intentional error")
        
        def good_callback(state):
            called.append(state)
        
        transport.subscribe_state(bad_callback)
        transport.subscribe_state(good_callback)
        
        state = GloveState(
            timestamp=time.time(),
            fingers={},
            imu=IMUState(),
        )
        transport.publish_state(state)
        
        if len(called) != 1:
            return False, "Good callback wasn't called after bad callback exception"
        
        return True, "subscriber exceptions isolated"
    
    def test_unsubscribe_idempotent(self):
        """Test that unsubscribe can be called multiple times."""
        transport = ConcreteTransport()
        called = []
        
        unsubscribe = transport.subscribe_state(lambda s: called.append(s))
        unsubscribe()
        unsubscribe()
        unsubscribe()
        
        if len(transport.subscribers) != 0:
            return False, "Subscribers not empty after unsubscribe"
        
        return True, "unsubscribe is idempotent"
    
    def test_send_command_works(self):
        """Test that send_command queues commands."""
        transport = ConcreteTransport()
        cmd = SetpointCommand(fingers={"thumb": 0.5})
        transport.send_command(cmd)
        
        if len(transport.commands) != 1:
            return False, "Command not queued"
        if transport.commands[0] != cmd:
            return False, "Wrong command queued"
        
        return True, "send_command works"
    
    def test_send_multiple_commands(self):
        """Test sending multiple different command types."""
        transport = ConcreteTransport()
        
        cmd1 = SetpointCommand(fingers={"thumb": 0.5})
        cmd2 = CalibrationCommand(action=CalibrationAction.START)
        cmd3 = EnableCommand(enabled=True)
        cmd4 = PIDCommand(kp=1.5, kd=0.3)
        cmd5 = StreamCommand(stream_type=StreamType.FINGER_POSITION, start=True)
        cmd6 = RestartCommand()
        
        transport.send_command(cmd1)
        transport.send_command(cmd2)
        transport.send_command(cmd3)
        transport.send_command(cmd4)
        transport.send_command(cmd5)
        transport.send_command(cmd6)
        
        if len(transport.commands) != 6:
            return False, f"Expected 6 commands, got {len(transport.commands)}"
        
        if not isinstance(transport.commands[0], SetpointCommand):
            return False, "Command type mismatch"
        
        return True, "multiple commands work"
    
    def test_context_manager(self):
        """Test that context manager works."""
        transport = ConcreteTransport()
        
        with transport as t:
            if not t.is_connected():
                return False, "Not connected in context"
            if t != transport:
                return False, "Context manager didn't return self"
        
        if transport.is_connected():
            return False, "Still connected after context exit"
        
        return True, "context manager works"
    
    def test_context_manager_on_exception(self):
        """Test that context manager disconnects even on exception."""
        transport = ConcreteTransport()
        
        try:
            with transport:
                if not transport.is_connected():
                    return False, "Not connected in context"
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass
        
        if transport.is_connected():
            return False, "Still connected after exception"
        
        return True, "context manager handles exceptions"
    
    def test_disconnect_clears_subscribers(self):
        """Test that disconnect removes all subscribers."""
        transport = ConcreteTransport()
        transport.connect()
        
        transport.subscribe_state(lambda s: None)
        transport.subscribe_state(lambda s: None)
        transport.subscribe_state(lambda s: None)
        
        if len(transport.subscribers) != 3:
            return False, "Subscribers not added"
        
        transport.disconnect()
        
        if len(transport.subscribers) != 0:
            return False, "Subscribers not cleared on disconnect"
        
        return True, "disconnect clears subscribers"
    
    def test_thread_safety(self):
        """Test concurrent access to transport."""
        transport = ConcreteTransport()
        errors = []
        
        def send_commands():
            for i in range(50):
                try:
                    cmd = SetpointCommand(fingers={"thumb": i / 50.0})
                    transport.send_command(cmd)
                except Exception as e:
                    errors.append(e)
        
        def subscribe_unsubscribe():
            for _ in range(50):
                try:
                    unsub = transport.subscribe_state(lambda s: None)
                    time.sleep(0.0001)
                    unsub()
                except Exception as e:
                    errors.append(e)
        
        threads = [
            threading.Thread(target=send_commands),
            threading.Thread(target=send_commands),
            threading.Thread(target=subscribe_unsubscribe),
            threading.Thread(target=subscribe_unsubscribe),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        if errors:
            return False, f"Thread safety errors: {errors[0]}"
        
        if len(transport.commands) != 100:
            return False, f"Expected 100 commands, got {len(transport.commands)}"
        
        return True, "thread safety verified"


def run_tests():
    """Run all Phase 2 tests."""
    print('=' * 60)
    print('PHASE 2: TRANSPORT ABSTRACTION TESTS')
    print('=' * 60)
    
    test_count = 0
    passed = 0
    
    # Test Transport ABC
    abc_tests = TestTransportABC()
    for method_name in dir(abc_tests):
        if method_name.startswith('test_'):
            test_count += 1
            method = getattr(abc_tests, method_name)
            success, message = method()
            status = '✓' if success else '✗'
            print(f'{test_count}. {method_name[5:].replace("_", " ")} ... {status}')
            if not success:
                print(f'   ERROR: {message}')
                return False
            passed += 1
    
    # Test concrete implementation
    concrete_tests = TestConcreteImplementation()
    for method_name in dir(concrete_tests):
        if method_name.startswith('test_'):
            test_count += 1
            method = getattr(concrete_tests, method_name)
            success, message = method()
            status = '✓' if success else '✗'
            print(f'{test_count}. {method_name[5:].replace("_", " ")} ... {status}')
            if not success:
                print(f'   ERROR: {message}')
                return False
            passed += 1
    
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

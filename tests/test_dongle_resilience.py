"""Integration tests for Dongle resilience and error handling."""

import unittest
import time
import threading
from unittest.mock import MagicMock, patch, ANY
import serial

from sdk.dongle.manager import Dongle
from sdk.dongle.connection import DongleConnection
from sdk.dongle.status_monitor import StatusMonitor
from sdk.dongle.status import DongleStatus

class TestDongleResilience(unittest.TestCase):
    """Test resilience against hardware failures and edge cases."""
    
    def setUp(self):
        self.dongle = Dongle()
        # We need to access the internal connection for mocking
        self.connection = self.dongle._connection
        self.monitor = self.dongle._monitor
        
    def test_hardware_disconnect_detection(self):
        """Test that hardware disconnect is detected."""
        # 1. Setup mock serial
        mock_serial = MagicMock(spec=serial.Serial)
        mock_serial.read.return_value = b'' # Normal behavior
        
        # Mock find_single_dongle to avoid auto-detect failure
        with patch('serial.Serial', return_value=mock_serial), \
             patch('sdk.dongle.connection.find_single_dongle'):
            
            # Connect with explicit port to skip auto-detect logic if possible, 
            # but mocking find_single_dongle handles the auto-detect case too.
            self.dongle.connect()
            self.assertTrue(self.dongle.is_dongle_connected)
            
            # 2. Simulate hardware disconnect (read raises SerialException)
            # We need to inject this into the running thread or simulate the effect
            # Since we can't easily inject into the thread in a unit test without
            # race conditions, we'll test the _reader_loop logic directly or 
            # verify the connection state update.
            
            # Let's simulate what happens in the reader loop
            self.connection._serial = mock_serial
            self.connection._connected = True
            self.connection._active = True
            
            # Simulate the exception that would happen in the thread
            mock_serial.read.side_effect = serial.SerialException("Device disconnected")
            
            # Run one iteration of the reader loop logic manually to verify behavior
            # (We can't easily run the actual thread and catch the exact moment)
            try:
                # This mimics the try/except block in _reader_loop
                self.connection._serial.read(10)
            except serial.SerialException as e:
                # This is where the fix needs to happen:
                # The connection should mark itself as disconnected
                # We call the method we INTEND to implement/use
                if hasattr(self.connection, '_handle_error'):
                    self.connection._handle_error(e)
                
            # ASSERTION: Connection should be marked as closed
            self.assertFalse(self.connection.is_connected(), 
                             "Connection should be False after SerialException")
            self.assertIsNone(self.connection._serial, 
                              "Serial object should be cleared after disconnect")

    def test_status_staleness(self):
        """Test that status becomes stale if updates stop."""
        # 1. Inject a fresh status
        status = DongleStatus.from_json({"bt_connected": True}, timestamp=time.time())
        self.monitor._latest_status = status
        
        # Mock connection to be True so is_glove_connected checks status
        self.connection._connected = True
        self.connection._serial = MagicMock()
        
        self.assertTrue(self.dongle.is_glove_connected)
        self.assertFalse(self.dongle.is_status_stale)
        
        # 2. Wait (simulate time passing without updates)
        # We can't easily wait 2 seconds in a unit test, so we'll mock time
        # But since we can't mock time.time() globally easily without patching everywhere,
        # we'll just inject an OLD status.
        
        old_status = DongleStatus.from_json({"bt_connected": True}, timestamp=time.time() - 3.0)
        self.monitor._latest_status = old_status
        
        self.assertTrue(self.dongle.is_status_stale)

    def test_busy_port_connection(self):
        """Test connecting to a busy port."""
        with patch('serial.Serial', side_effect=serial.SerialException("Device busy")):
            result = self.dongle.connect()
            self.assertFalse(result)
            self.assertFalse(self.dongle.is_dongle_connected)

if __name__ == '__main__':
    unittest.main()

"""Unit tests for DongleConnection class (raw byte stream)."""

import time
import unittest
from unittest.mock import Mock, MagicMock, patch, call

from sdk.dongle.connection import DongleConnection
from sdk.dongle.status import DongleStatus


class TestDongleConnectionInit(unittest.TestCase):
    """Tests for DongleConnection initialization."""
    
    def test_init_defaults(self):
        """Test initialization with default parameters."""
        dongle = DongleConnection()
        
        self.assertIsNone(dongle._port)
        self.assertEqual(dongle._baudrate, 1_000_000)
        self.assertEqual(dongle._timeout, 0.1)
        self.assertEqual(dongle._chunk_size, 4096)
        self.assertFalse(dongle.is_connected())
    
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        dongle = DongleConnection(
            port="/dev/ttyUSB5",
            baudrate=115200,
            timeout=0.5,
            chunk_size=8192
        )
        
        self.assertEqual(dongle._port, "/dev/ttyUSB5")
        self.assertEqual(dongle._baudrate, 115200)
        self.assertEqual(dongle._timeout, 0.5)
        self.assertEqual(dongle._chunk_size, 8192)


class TestDongleConnectionConnect(unittest.TestCase):
    """Tests for connection management."""
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_connect_explicit_port(self, mock_serial_class):
        """Test connecting with explicit port."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        result = dongle.connect()
        
        self.assertTrue(result)
        self.assertTrue(dongle.is_connected())
        mock_serial_class.assert_called_once_with(
            port="/dev/ttyUSB0",
            baudrate=1_000_000,
            timeout=0.1
        )
        mock_serial.reset_input_buffer.assert_called_once()
        mock_serial.reset_output_buffer.assert_called_once()
    
    @patch('sdk.dongle.connection.find_single_dongle')
    @patch('sdk.dongle.connection.serial.Serial')
    def test_connect_auto_detect(self, mock_serial_class, mock_find):
        """Test connecting with auto-detection."""
        from sdk.dongle.dongle_finder import DongleInfo
        
        # Mock dongle finder
        mock_info = DongleInfo(
            port="/dev/ttyUSB0",
            vid=0x5FFE,
            pid=0x1000,
            serial_number="12345",
            manufacturer="Test Manufacturer",
            product="Haptic Glove Dongle",
            hwid="USB VID:PID=5FFE:1000"
        )
        mock_find.return_value = mock_info
        
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        # Connect without port
        dongle = DongleConnection()
        result = dongle.connect()
        
        self.assertTrue(result)
        mock_find.assert_called_once()
        self.assertEqual(dongle._port, "/dev/ttyUSB0")
    
    def test_connect_already_connected(self):
        """Test connecting when already connected."""
        dongle = DongleConnection(port="/dev/ttyUSB0")
        dongle._connected = True
        dongle._serial = MagicMock()
        
        result = dongle.connect()
        self.assertTrue(result)

    def test_is_dongle_available_connected(self):
        """Test availability check when connected."""
        dongle = DongleConnection()
        dongle._connected = True
        dongle._serial = MagicMock()
        self.assertTrue(dongle.is_dongle_available())

    @patch('sdk.dongle.connection.is_dongle_available')
    def test_is_dongle_available_autodetect(self, mock_is_available_func):
        """Test availability check via autodetect."""
        mock_is_available_func.return_value = True
        dongle = DongleConnection()
        self.assertTrue(dongle.is_dongle_available())
        mock_is_available_func.assert_called_once()

    @patch('serial.tools.list_ports.comports')
    def test_is_dongle_available_explicit(self, mock_comports):
        """Test availability check with explicit port."""
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB0"
        mock_comports.return_value = [mock_port]
        
        self.assertTrue(dongle.is_dongle_available())
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_connect_serial_exception(self, mock_serial_class):
        """Test connect failure due to serial exception."""
        import serial
        mock_serial_class.side_effect = serial.SerialException("Port not found")
        
        dongle = DongleConnection(port="/dev/ttyUSB99")
        result = dongle.connect()
        
        self.assertFalse(result)
        self.assertFalse(dongle.is_connected())
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_disconnect(self, mock_serial_class):
        """Test disconnecting."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        dongle.connect()
        
        # Disconnect
        dongle.disconnect()
        
        self.assertFalse(dongle.is_connected())
        mock_serial.close.assert_called_once()


class TestDongleConnectionSending(unittest.TestCase):
    """Tests for sending data."""
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_write(self, mock_serial_class):
        """Test sending raw bytes."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        dongle.connect()
        
        # Send raw data
        data = b'test data'
        result = dongle.write(data)
        
        self.assertTrue(result)
        mock_serial.write.assert_called_with(data)
        mock_serial.flush.assert_called()
    
    def test_send_when_disconnected(self):
        """Test sending when not connected does nothing."""
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        # Should not raise exception
        result = dongle.write(b'test')
        self.assertFalse(result)


class TestDongleConnectionSubscriptions(unittest.TestCase):
    """Tests for subscription callbacks (raw byte stream)."""
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_subscribe_data(self, mock_serial_class):
        """Test subscribing to raw byte stream."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        # Subscribe
        callback = Mock()
        unsub = dongle.subscribe_data(callback)
        
        self.assertIsNotNone(unsub)
        self.assertIn(callback, dongle._data_callbacks)
        
        # Unsubscribe
        unsub()
        self.assertNotIn(callback, dongle._data_callbacks)
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_data_callback_invoked(self, mock_serial_class):
        """Test that data callbacks are invoked with raw chunks."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        # Subscribe
        callback = Mock()
        dongle.subscribe_data(callback)
        
        # Simulate raw byte chunk (including status message)
        test_chunk = b'STREAM 0.5,0.6,0.7\n~~~STATUS_RESPONSE~~~\n{"test":1}\r\n'
        dongle._notify_data_callbacks(test_chunk)
        
        # Callback should receive entire chunk
        callback.assert_called_once_with(test_chunk)
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_multiple_subscribers(self, mock_serial_class):
        """Test multiple subscribers all receive chunks."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        # Subscribe multiple callbacks
        callback1 = Mock()
        callback2 = Mock()
        dongle.subscribe_data(callback1)
        dongle.subscribe_data(callback2)
        
        # Send chunk
        test_chunk = b'test data'
        dongle._notify_data_callbacks(test_chunk)
        
        # Both should receive
        callback1.assert_called_once_with(test_chunk)
        callback2.assert_called_once_with(test_chunk)
    
    @patch('sdk.dongle.connection.serial.Serial')
    def test_callback_exception_handling(self, mock_serial_class):
        """Test that exceptions in callbacks don't crash reader."""
        mock_serial = MagicMock()
        mock_serial_class.return_value = mock_serial
        
        dongle = DongleConnection(port="/dev/ttyUSB0")
        
        # Subscribe bad callback
        def bad_callback(chunk):
            raise ValueError("Test exception")
        
        good_chunks = []
        
        dongle.subscribe_data(bad_callback)
        dongle.subscribe_data(good_chunks.append)
        
        # Should not crash
        test_chunk = b'test'
        dongle._notify_data_callbacks(test_chunk)
        
        # Good callback should still work
        self.assertEqual(len(good_chunks), 1)
        self.assertEqual(good_chunks[0], test_chunk)


class TestDongleConnectionReconnect(unittest.TestCase):
    """Test DongleConnection autoreconnect logic."""
    
    def setUp(self):
        self.dongle = DongleConnection()
        
    def tearDown(self):
        self.dongle.set_autoreconnect(False)
        self.dongle.disconnect()

    def test_autoreconnect_thread_lifecycle(self):
        """Test that autoreconnect thread starts and stops."""
        self.assertIsNone(self.dongle._reconnect_thread)
        
        self.dongle.set_autoreconnect(True)
        self.assertIsNotNone(self.dongle._reconnect_thread)
        self.assertTrue(self.dongle._reconnect_thread.is_alive())
        
        self.dongle.set_autoreconnect(False)
        self.assertIsNone(self.dongle._reconnect_thread)

    @patch('sdk.dongle.connection.is_dongle_available')
    @patch('sdk.dongle.connection.serial.Serial')
    def test_reconnect_logic(self, mock_serial, mock_available):
        """Test that it attempts to reconnect when disconnected."""
        # Setup: Disconnected, but available
        mock_available.return_value = True
        mock_serial.return_value = MagicMock()
        
        # Start autoreconnect
        self.dongle.set_autoreconnect(True)
        
        # Wait for loop to run
        time.sleep(2.0)
        
        # Should have attempted connection
        self.assertTrue(self.dongle.is_connected())
        
    def test_handle_error_triggers_reconnect(self):
        """Test that _handle_error restarts the reconnect thread."""
        self.dongle._autoreconnect = True
        # Simulate error
        self.dongle._handle_error(Exception("Test error"))
        
        # Should have started reconnect thread
        self.assertIsNotNone(self.dongle._reconnect_thread)
        self.assertTrue(self.dongle._reconnect_thread.is_alive())


if __name__ == '__main__':
    unittest.main()

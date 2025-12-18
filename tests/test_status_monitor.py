"""Unit tests for StatusMonitor class."""

import time
import unittest
import queue
from unittest.mock import MagicMock

from sdk.dongle.status_monitor import StatusMonitor
from sdk.dongle.status import DongleStatus, ESC_STATUS_START, ESC_STATUS_END


class TestStatusMonitor(unittest.TestCase):
    """Test StatusMonitor byte stream observation."""
    
    def setUp(self):
        """Create fresh monitor for each test."""
        self.mock_conn = MagicMock()
        self.monitor = StatusMonitor(connection=self.mock_conn)
    
    def test_empty_buffer(self):
        """Monitor with no data has no status."""
        self.assertIsNone(self.monitor.get_latest_status())
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_complete_status_message(self):
        """Complete status message is detected and parsed."""
        # Send complete status message
        json_str = '{"device":"BT_DONGLE_NUS","version":"1.0.0","uptime_ms":1000,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        message = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        
        self.monitor.on_data(message)
        self.monitor.process_pending()
        
        # Status should be parsed
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertIsInstance(status, DongleStatus)
        self.assertEqual(status.firmware_version, "1.0.0")
        self.assertFalse(status.bluetooth_connected)
        self.assertTrue(status.dongle_connected)
        
        # Buffer should be empty after processing
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_partial_status_message_two_chunks(self):
        """Status message split across two chunks is detected."""
        # Send first part
        part1 = ESC_STATUS_START[:10]
        self.monitor.on_data(part1)
        self.monitor.process_pending()
        
        # No status yet
        self.assertIsNone(self.monitor.get_latest_status())
        self.assertEqual(self.monitor.get_buffer_size(), len(part1))
        
        # Send rest
        json_str = '{"device":"BT_DONGLE_NUS","version":"1.0.0","uptime_ms":1000,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        part2 = ESC_STATUS_START[10:] + json_str.encode('utf-8') + ESC_STATUS_END
        self.monitor.on_data(part2)
        self.monitor.process_pending()
        
        # Status should be parsed
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.firmware_version, "1.0.0")
        
        # Buffer should be empty
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_partial_status_message_many_chunks(self):
        """Status message split across many tiny chunks."""
        json_str = '{"device":"TEST","version":"2.0.0","uptime_ms":5000,"usb_present":true,"usb_serial_connected":true,"bt_connected":true,"nus_subscribed":true,"bt_mtu":247,"max_payload":240,"led_mode":"solid"}'
        message = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        
        # Send one byte at a time
        for byte in message:
            self.monitor.on_data(bytes([byte]))
        self.monitor.process_pending()
        
        # Status should be parsed
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.firmware_version, "2.0.0")
        self.assertTrue(status.bluetooth_connected)
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_multiple_status_messages_in_one_chunk(self):
        """Multiple status messages in single chunk are all detected."""
        json_a = '{"device":"A","version":"1.0","uptime_ms":100,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        json_b = '{"device":"B","version":"2.0","uptime_ms":200,"usb_present":true,"usb_serial_connected":true,"bt_connected":true,"nus_subscribed":true,"bt_mtu":247,"max_payload":240,"led_mode":"solid"}'
        
        chunk = (
            ESC_STATUS_START + json_a.encode('utf-8') + ESC_STATUS_END +
            ESC_STATUS_START + json_b.encode('utf-8') + ESC_STATUS_END
        )
        
        statuses = []
        self.monitor.subscribe_status(statuses.append)
        
        self.monitor.on_data(chunk)
        self.monitor.process_pending()
        
        # Both messages should be detected
        self.assertEqual(len(statuses), 2)
        self.assertEqual(statuses[0].firmware_version, "1.0")
        self.assertEqual(statuses[1].firmware_version, "2.0")
        self.assertFalse(statuses[0].bluetooth_connected)
        self.assertTrue(statuses[1].bluetooth_connected)
        
        # Latest should be second one
        self.assertEqual(self.monitor.get_latest_status().firmware_version, "2.0")
    
    def test_status_with_surrounding_data(self):
        """Status message surrounded by other data."""
        json_str = '{"device":"X","version":"3.0","uptime_ms":300,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        chunk = (
            b'STREAM 1,2,3,4,5\n'
            b'[DONGLE] Some log message\n' +
            ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END +
            b'STREAM 6,7,8,9,10\n'
        )
        
        self.monitor.on_data(chunk)
        self.monitor.process_pending()
        
        # Status should be detected
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.firmware_version, "3.0")
        
        # Buffer should contain remaining data after status
        buffer_size = self.monitor.get_buffer_size()
        self.assertGreater(buffer_size, 0)
    
    def test_interleaved_data_and_status(self):
        """Data and status messages interleaved."""
        json_str = '{"device":"Y","version":"1.1","uptime_ms":111,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        self.monitor.on_data(b'Some data\n')
        self.monitor.on_data(ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END)
        self.monitor.on_data(b'More data\n')
        self.monitor.process_pending()
        
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.firmware_version, "1.1")
    
    def test_invalid_json_in_status(self):
        """Invalid JSON in status message is handled gracefully."""
        bad_message = ESC_STATUS_START + b'{invalid json here}' + ESC_STATUS_END
        
        self.monitor.on_data(bad_message)
        self.monitor.process_pending()
        
        # Should not crash, just return None
        status = self.monitor.get_latest_status()
        self.assertIsNone(status)
        
        # Buffer should be cleared after trying to parse
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_incomplete_status_at_end(self):
        """Incomplete status message remains in buffer."""
        incomplete = ESC_STATUS_START + b'{"device":"Z"'
        
        self.monitor.on_data(incomplete)
        self.monitor.process_pending()
        
        # No status yet
        self.assertIsNone(self.monitor.get_latest_status())
        
        # Buffer should contain incomplete message
        self.assertEqual(self.monitor.get_buffer_size(), len(incomplete))
    
    def test_buffer_overflow_protection(self):
        """Buffer is trimmed when it exceeds maximum size."""
        # Fill buffer with lots of data
        big_chunk = b'X' * (StatusMonitor.MAX_BUFFER_SIZE + 1000)
        
        self.monitor.on_data(big_chunk)
        self.monitor.process_pending()
        
        # Buffer should be trimmed
        self.assertLessEqual(self.monitor.get_buffer_size(), StatusMonitor.MAX_BUFFER_SIZE)
    
    def test_buffer_overflow_keeps_status_marker(self):
        """When buffer overflows, keep data after last status marker."""
        # Fill buffer with data, then add status marker
        filler = b'X' * (StatusMonitor.MAX_BUFFER_SIZE + 100)
        marker = ESC_STATUS_START + b'{"incomplete'
        
        self.monitor.on_data(filler + marker)
        self.monitor.process_pending()
        
        # Buffer should be trimmed but keep the status marker
        buffer_size = self.monitor.get_buffer_size()
        self.assertLessEqual(buffer_size, StatusMonitor.MAX_BUFFER_SIZE)
        self.assertGreater(buffer_size, 0)
    
    def test_subscribe_and_unsubscribe(self):
        """Status callbacks can be subscribed and unsubscribed."""
        statuses1 = []
        statuses2 = []
        
        unsub1 = self.monitor.subscribe_status(statuses1.append)
        unsub2 = self.monitor.subscribe_status(statuses2.append)
        
        # Send status
        json_str = '{"device":"A","version":"1.0","uptime_ms":100,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        message = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        self.monitor.on_data(message)
        self.monitor.process_pending()
        
        # Both should receive
        self.assertEqual(len(statuses1), 1)
        self.assertEqual(len(statuses2), 1)
        
        # Unsubscribe first
        unsub1()
        
        # Send another status
        json_str2 = '{"device":"B","version":"2.0","uptime_ms":200,"usb_present":true,"usb_serial_connected":true,"bt_connected":true,"nus_subscribed":true,"bt_mtu":247,"max_payload":240,"led_mode":"solid"}'
        message2 = ESC_STATUS_START + json_str2.encode('utf-8') + ESC_STATUS_END
        self.monitor.on_data(message2)
        self.monitor.process_pending()
        
        # Only second should receive
        self.assertEqual(len(statuses1), 1)
        self.assertEqual(len(statuses2), 2)
    
    def test_callback_exception_doesnt_crash(self):
        """Exception in callback doesn't crash monitor."""
        def bad_callback(status):
            raise ValueError("Test exception")
        
        good_statuses = []
        
        self.monitor.subscribe_status(bad_callback)
        self.monitor.subscribe_status(good_statuses.append)
        
        json_str = '{"device":"A","version":"1.0","uptime_ms":100,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        message = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        
        # Should not crash
        self.monitor.on_data(message)
        self.monitor.process_pending()
        
        # Good callback should still receive
        self.assertEqual(len(good_statuses), 1)
    
    def test_clear_buffer(self):
        """Buffer can be cleared manually."""
        self.monitor.on_data(b'Some data in buffer')
        self.monitor.process_pending()
        self.assertGreater(self.monitor.get_buffer_size(), 0)
        
        self.monitor.clear_buffer()
        
        self.assertEqual(self.monitor.get_buffer_size(), 0)
    
    def test_status_without_delimiter_end(self):
        """Status message without end marker stays in buffer."""
        json_str = '{"device":"A","version":"1.0","uptime_ms":100,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        incomplete = ESC_STATUS_START + json_str.encode('utf-8')
        # Missing ESC_STATUS_END at end
        
        self.monitor.on_data(incomplete)
        self.monitor.process_pending()
        
        # No status yet (waiting for end marker)
        self.assertIsNone(self.monitor.get_latest_status())
        self.assertGreater(self.monitor.get_buffer_size(), 0)
        
        # Now send the ending
        self.monitor.on_data(ESC_STATUS_END)
        self.monitor.process_pending()
        
        # Status should be parsed
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        self.assertEqual(status.firmware_version, "1.0")
    
    def test_multiple_partial_chunks(self):
        """Complex scenario with multiple partial chunks."""
        # Construct message
        json_str = '{"device":"TEST","version":"1.5","uptime_ms":1500,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        full_msg = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        
        # Split into chunks
        chunks = [
            b'DATA LINE 1\n',
            full_msg[:10],
            full_msg[10:20],
            full_msg[20:40],
            full_msg[40:80],
            full_msg[80:120],
            full_msg[120:],
            b'DATA LINE 2\n',
        ]
        
        statuses = []
        self.monitor.subscribe_status(statuses.append)
        
        for chunk in chunks:
            self.monitor.on_data(chunk)
        self.monitor.process_pending()
        
        # One status should be detected
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].firmware_version, "1.5")
    
    def test_status_timestamp(self):
        """Status has timestamp set."""
        json_str = '{"device":"A","version":"1.0","uptime_ms":100,"usb_present":true,"usb_serial_connected":true,"bt_connected":false,"nus_subscribed":false,"bt_mtu":0,"max_payload":20,"led_mode":"slow_blink"}'
        message = ESC_STATUS_START + json_str.encode('utf-8') + ESC_STATUS_END
        
        before = time.time()
        self.monitor.on_data(message)
        self.monitor.process_pending()
        after = time.time()
        
        status = self.monitor.get_latest_status()
        self.assertIsNotNone(status)
        
        # Timestamp should be within reasonable range
        self.assertGreaterEqual(status.timestamp, before)
        self.assertLessEqual(status.timestamp, after)


class TestStatusMonitorQueue(unittest.TestCase):
    """Test StatusMonitor queue and threading behavior."""
    
    def setUp(self):
        """Create fresh monitor for each test."""
        self.mock_conn = MagicMock()
        self.monitor = StatusMonitor(connection=self.mock_conn)
        # We don't start the thread automatically in setUp to allow testing manual control
    
    def tearDown(self):
        """Ensure thread is stopped."""
        if self.monitor._running:
            self.monitor.stop()

    def test_queue_fifo_overflow(self):
        """Test that queue drops oldest data when full (FIFO behavior)."""
        # Set a small maxsize for testing
        self.monitor._data_queue = queue.Queue(maxsize=3)
        
        # Add 3 items (filling the queue)
        self.monitor.on_data(b'1')
        self.monitor.on_data(b'2')
        self.monitor.on_data(b'3')
        
        # Queue should be full
        self.assertTrue(self.monitor._data_queue.full())
        
        # Add 4th item - should force drop of '1'
        self.monitor.on_data(b'4')
        
        # Verify contents
        # We expect '2', '3', '4' in the queue
        self.assertEqual(self.monitor._data_queue.get_nowait(), b'2')
        self.assertEqual(self.monitor._data_queue.get_nowait(), b'3')
        self.assertEqual(self.monitor._data_queue.get_nowait(), b'4')
        self.assertTrue(self.monitor._data_queue.empty())

    def test_process_pending_drains_queue(self):
        """Test that process_pending processes all items in queue."""
        self.monitor.on_data(b'data1')
        self.monitor.on_data(b'data2')
        
        self.assertFalse(self.monitor._data_queue.empty())
        
        # Process pending
        self.monitor.process_pending()
        
        # Queue should be empty
        self.assertTrue(self.monitor._data_queue.empty())
        # Buffer should contain data
        self.assertEqual(self.monitor.get_buffer_size(), 10) # len('data1') + len('data2')

    def test_thread_lifecycle(self):
        """Test start and stop of the background thread."""
        self.assertFalse(self.monitor._running)
        self.assertIsNone(self.monitor._thread)
        
        self.monitor.start()
        
        self.assertTrue(self.monitor._running)
        self.assertIsNotNone(self.monitor._thread)
        self.assertTrue(self.monitor._thread.is_alive())
        
        self.monitor.stop()
        
        self.assertFalse(self.monitor._running)
        self.assertIsNone(self.monitor._thread)

    def test_thread_processes_data(self):
        """Test that the background thread actually processes data."""
        self.monitor.start()
        
        # Send data
        self.monitor.on_data(b'test_data')
        
        # Wait a bit for thread to process
        time.sleep(0.1)
        
        # Queue should be empty (processed by thread)
        self.assertTrue(self.monitor._data_queue.empty())
        # Buffer should have data
        self.assertEqual(self.monitor.get_buffer_size(), 9) # len('test_data')


if __name__ == '__main__':
    unittest.main()

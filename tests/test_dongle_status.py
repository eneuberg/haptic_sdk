"""Unit tests for dongle status protocol."""

import json
import time
import unittest

from sdk.dongle.status import (
    DongleStatus,
    ESC_STATUS_REQUEST,
    ESC_STATUS_START,
    ESC_STATUS_END,
    parse_status_json,
)


class TestDongleStatus(unittest.TestCase):
    """Tests for DongleStatus dataclass."""
    
    def test_from_json_full(self):
        """Test parsing complete JSON status."""
        json_data = {
            "device": "BT_DONGLE_NUS",
            "version": "1.0.0",
            "uptime_ms": 135046,
            "usb_present": True,
            "usb_serial_connected": True,
            "bt_connected": True,
            "nus_subscribed": True,
            "bt_mtu": 247,
            "max_payload": 244,
            "led_mode": "solid"
        }
        
        status = DongleStatus.from_json(json_data, timestamp=1234.5)
        
        self.assertEqual(status.timestamp, 1234.5)
        self.assertTrue(status.dongle_connected)  # usb_present
        self.assertTrue(status.bluetooth_connected)  # bt_connected
        self.assertEqual(status.firmware_version, "1.0.0")  # version
        self.assertEqual(status.uptime_ms, 135046)
        self.assertTrue(status.nus_subscribed)
        self.assertEqual(status.bt_mtu, 247)
        self.assertEqual(status.max_payload, 244)
        self.assertEqual(status.led_mode, "solid")
        self.assertEqual(status.raw_json, json_data)
    
    def test_from_json_minimal(self):
        """Test parsing minimal JSON status."""
        json_data = {
            "bt_connected": False
        }
        
        status = DongleStatus.from_json(json_data)
        
        self.assertFalse(status.dongle_connected)  # Default False
        self.assertFalse(status.bluetooth_connected)  # bt_connected
        self.assertIsNone(status.firmware_version)
    
    def test_from_json_auto_timestamp(self):
        """Test automatic timestamp when not provided."""
        before = time.time()
        status = DongleStatus.from_json({"bt_connected": True})
        after = time.time()
        
        self.assertGreaterEqual(status.timestamp, before)
        self.assertLessEqual(status.timestamp, after)
    
    def test_disconnected(self):
        """Test creating disconnected status."""
        status = DongleStatus.disconnected(timestamp=5678.9)
        
        self.assertEqual(status.timestamp, 5678.9)
        self.assertFalse(status.dongle_connected)
        self.assertFalse(status.bluetooth_connected)
    
    def test_immutability(self):
        """Test that DongleStatus is immutable."""
        status = DongleStatus.disconnected()
        
        with self.assertRaises(AttributeError):
            status.uptime_ms = 50


class TestStatusJsonParsing(unittest.TestCase):
    """Tests for JSON status parsing."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON status."""
        json_str = '{"bt_connected": true, "version": "1.0.0"}'
        json_bytes = json_str.encode('utf-8')
        
        status = parse_status_json(json_bytes)
        
        self.assertIsNotNone(status)
        self.assertTrue(status.bluetooth_connected)
        self.assertEqual(status.firmware_version, "1.0.0")
    
    def test_parse_json_with_whitespace(self):
        """Test parsing JSON with leading/trailing whitespace."""
        json_str = '  \n{"bt_connected": false}\n  '
        json_bytes = json_str.encode('utf-8')
        
        status = parse_status_json(json_bytes)
        
        self.assertIsNotNone(status)
        self.assertFalse(status.bluetooth_connected)
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        invalid_json = b'{invalid json}'
        
        status = parse_status_json(invalid_json)
        
        self.assertIsNone(status)
    
    def test_parse_empty_json(self):
        """Test parsing empty string returns None."""
        status = parse_status_json(b'')
        
        self.assertIsNone(status)
    
    def test_parse_non_utf8(self):
        """Test parsing non-UTF8 bytes returns None."""
        invalid_bytes = b'\xff\xfe\xfd'
        
        status = parse_status_json(invalid_bytes)
        
        self.assertIsNone(status)


class TestProtocolConstants(unittest.TestCase):
    """Tests for protocol delimiters."""
    
    def test_delimiters_are_bytes(self):
        """Test that all protocol delimiters are bytes."""
        self.assertIsInstance(ESC_STATUS_REQUEST, bytes)
        self.assertIsInstance(ESC_STATUS_START, bytes)
        self.assertIsInstance(ESC_STATUS_END, bytes)
    
    def test_delimiters_unique(self):
        """Test that protocol delimiters are unique."""
        sequences = [ESC_STATUS_REQUEST, ESC_STATUS_START, ESC_STATUS_END]
        self.assertEqual(len(sequences), len(set(sequences)))
    
    def test_status_request_format(self):
        """Test status request format."""
        self.assertEqual(ESC_STATUS_REQUEST, b'@@@[STATUS]@@@')
    
    def test_status_response_format(self):
        """Test status response delimiter format."""
        self.assertEqual(ESC_STATUS_START, b'\xFF\x34[STATUS_RESPONSE]')
        self.assertEqual(ESC_STATUS_END, b'\xFF\x34')


if __name__ == '__main__':
    unittest.main()

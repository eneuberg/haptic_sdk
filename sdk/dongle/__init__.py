"""Dongle layer for haptic glove USB CDC Bluetooth dongle.

This module provides:
- Low-level USB CDC connection management (DongleConnection) - Raw byte stream
- Status observation from byte stream (StatusMonitor)
- Dongle status message parsing (DongleStatus)
- Device discovery utilities (find_single_dongle, find_dongles)
"""

from .connection import DongleConnection
from .status import DongleStatus, ESC_STATUS_REQUEST, ESC_STATUS_START, ESC_STATUS_END
from .status_monitor import StatusMonitor
from .manager import Dongle
from .buffer import StreamBuffer
from .dongle_finder import (
    DongleInfo,
    DongleNotFoundError,
    MultipleDonglesError,
    find_dongles,
    find_single_dongle,
    is_matching_dongle,
)

__all__ = [
    # Connection
    'DongleConnection',
    
    # Status
    'DongleStatus',
    'StatusMonitor',
    'ESC_STATUS_REQUEST',
    'ESC_STATUS_RESPONSE',
    'ESC_DATA',
    
    # Finder
    'DongleInfo',
    'DongleNotFoundError',
    'MultipleDonglesError',
    'find_dongles',
    'find_single_dongle',
    'is_matching_dongle',
]

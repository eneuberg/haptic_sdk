from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from serial.tools import list_ports

from .errors import DongleNotFoundError, MultipleDonglesError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DongleInfo:
    """
    Representation of one USB CDC ACM dongle as seen by pyserial.

    Attributes:
        port: Port name to open with pyserial (e.g. 'COM3', '/dev/ttyACM0').
        vid: USB Vendor ID (integer) or None if unknown.
        pid: USB Product ID (integer) or None if unknown.
        manufacturer: USB manufacturer string, if available.
        product: USB product string, if available.
        serial_number: USB serial string, if available.
        hwid: Raw hardware ID string from pyserial (for debugging).
    """
    port: str
    vid: Optional[int]
    pid: Optional[int]
    manufacturer: Optional[str]
    product: Optional[str]
    serial_number: Optional[str]
    hwid: str

    @property
    def device_id(self) -> str:
        """
        OS-agnostic identifier for the dongle.

        By default, prefer the USB serial_number (stable across OS);
        fall back to hwid if serial is missing.
        """
        if self.serial_number:
            return self.serial_number
        return self.hwid


def _port_to_info(port) -> DongleInfo:
    """Convert pyserial's ListPortInfo to DongleInfo."""
    return DongleInfo(
        port=port.device,
        vid=port.vid,
        pid=port.pid,
        manufacturer=port.manufacturer,
        product=port.product,
        serial_number=port.serial_number,
        hwid=port.hwid,
    )


def is_matching_dongle(
    info: DongleInfo,
    *,
    expected_vid: Optional[int] = None,
    expected_pid: Optional[int] = None,
    product_substring: Optional[str] = None,
    serial_prefix: Optional[str] = None,
) -> bool:
    """
    Decide whether a given DongleInfo describes our dongle.

    This is the predicate you can tweak later without changing callers.
    All checks are AND-combined; if a criterion is None, it is ignored.

    Args:
        expected_vid: Match this VID (e.g. 0x1915 for Nordic), or None.
        expected_pid: Match this PID, or None.
        product_substring: Case-insensitive substring expected in product string.
        serial_prefix: Expected prefix of the serial number.

    Returns:
        True if the device matches all specified criteria.
    """
    if expected_vid is not None and info.vid != expected_vid:
        return False

    if expected_pid is not None and info.pid != expected_pid:
        return False

    if product_substring is not None:
        if not info.product:
            return False
        if product_substring.lower() not in info.product.lower():
            return False

    if serial_prefix is not None:
        if not info.serial_number:
            return False
        if not info.serial_number.startswith(serial_prefix):
            return False

    return True


def is_dongle_available(
    port: Optional[str] = None,
    expected_vid: int = 0x5FFE,
    expected_pid: int = 0x1000,
    product_substring: str = "Haptic Glove Dongle"
) -> bool:
    """Check if dongle is available for connection.
    
    Checks if the dongle is physically present and recognized by the OS.
    
    Args:
        port: Specific port to check (e.g. '/dev/ttyUSB0'). 
              If None, checks for any matching dongle.
        expected_vid: VID to look for if port is None.
        expected_pid: PID to look for if port is None.
        product_substring: Product string to look for if port is None.
              
    Returns:
        True if dongle is found/available.
    """
    if port:
        return any(p.device == port for p in list_ports.comports())
        
    try:
        from . import find_single_dongle # Import here to avoid circular import if any
        find_single_dongle(
            expected_vid=expected_vid,
            expected_pid=expected_pid,
            product_substring=product_substring
        )
        return True
    except (DongleNotFoundError, Exception):
        return False



def find_dongles(
    *,
    matcher: Optional[Callable[[DongleInfo], bool]] = None,
    expected_vid: Optional[int] = None,
    expected_pid: Optional[int] = None,
    product_substring: Optional[str] = None,
    serial_prefix: Optional[str] = None,
) -> List[DongleInfo]:
    """
    Find all dongles connected to this machine.

    You can either pass a custom `matcher(info) -> bool` or use the
    built-in criteria (expected_vid / expected_pid / product_substring / serial_prefix).

    Returns:
        List of DongleInfo objects.
    """
    ports = list_ports.comports()
    results: List[DongleInfo] = []

    for port in ports:
        info = _port_to_info(port)
        if matcher is not None:
            if matcher(info):
                results.append(info)
        else:
            if is_matching_dongle(
                info,
                expected_vid=expected_vid,
                expected_pid=expected_pid,
                product_substring=product_substring,
                serial_prefix=serial_prefix,
            ):
                results.append(info)

    return results


def find_single_dongle(
    *,
    matcher: Optional[Callable[[DongleInfo], bool]] = None,
    expected_vid: Optional[int] = None,
    expected_pid: Optional[int] = None,
    product_substring: Optional[str] = None,
    serial_prefix: Optional[str] = None,
) -> DongleInfo:
    """
    Find exactly one dongle.

    Behaviour:
        - 0 matches  -> DongleNotFoundError
        - 1 match    -> return it
        - >1 matches -> log error and raise MultipleDonglesError

    This is the function you typically call before opening with pyserial.
    """
    matches = find_dongles(
        matcher=matcher,
        expected_vid=expected_vid,
        expected_pid=expected_pid,
        product_substring=product_substring,
        serial_prefix=serial_prefix,
    )

    if not matches:
        raise DongleNotFoundError("No matching dongle found")

    if len(matches) > 1:
        # Log detailed error, but do not pick one implicitly.
        logger.error(
            "Multiple matching dongles found; refusing to choose automatically. "
            "Devices: %s",
            matches,
        )
        # Keep it extensible: caller can inspect e.devices later.
        raise MultipleDonglesError(
            f"Multiple matching dongles found ({len(matches)} devices)",
            devices=matches,
        )

    return matches[0]

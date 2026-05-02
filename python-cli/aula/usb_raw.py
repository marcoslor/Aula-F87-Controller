"""
Raw libusb control transfer — bypasses pyusb's auto interface claiming.

On macOS, pyusb's ctrl_transfer() auto-claims the interface via
libusb_claim_interface(), which requires detaching the kernel HID driver,
which kills keyboard input. But SET_REPORT control transfers go to
endpoint 0 (the default control pipe) and DON'T need interface claiming.

This module calls libusb_control_transfer() directly through ctypes,
skipping the claim step entirely. The kernel HID driver stays attached
and the keyboard continues to function normally during animations.
"""

import ctypes
import ctypes.util
import os
import sys
import time

# libusb constants
_LIBUSB_SUCCESS = 0
_LIBUSB_ERROR_ACCESS = -3
_LIBUSB_ERROR_NO_DEVICE = -4
_LIBUSB_ERROR_NOT_FOUND = -5
_LIBUSB_ERROR_PIPE = -9

# Locate libusb
_LIBUSB_PATHS = [
    "/opt/homebrew/lib/libusb-1.0.dylib",
    "/usr/local/lib/libusb-1.0.dylib",
    "/usr/lib/libusb-1.0.so",
    "/usr/lib/x86_64-linux-gnu/libusb-1.0.so",
]


def _find_libusb():
    # Try ctypes.util first
    path = ctypes.util.find_library("usb-1.0")
    if path:
        return ctypes.CDLL(path)
    for p in _LIBUSB_PATHS:
        if os.path.exists(p):
            return ctypes.CDLL(p)
    raise RuntimeError("libusb-1.0 not found. Install: brew install libusb")


_lib = None


def _get_lib():
    global _lib
    if _lib is None:
        _lib = _find_libusb()
    return _lib


class _LibusbDeviceDescriptor(ctypes.Structure):
    _fields_ = [
        ("bLength", ctypes.c_uint8),
        ("bDescriptorType", ctypes.c_uint8),
        ("bcdUSB", ctypes.c_uint16),
        ("bDeviceClass", ctypes.c_uint8),
        ("bDeviceSubClass", ctypes.c_uint8),
        ("bDeviceProtocol", ctypes.c_uint8),
        ("bMaxPacketSize0", ctypes.c_uint8),
        ("idVendor", ctypes.c_uint16),
        ("idProduct", ctypes.c_uint16),
        ("bcdDevice", ctypes.c_uint16),
        ("iManufacturer", ctypes.c_uint8),
        ("iProduct", ctypes.c_uint8),
        ("iSerialNumber", ctypes.c_uint8),
        ("bNumConfigurations", ctypes.c_uint8),
    ]


class RawUSBDevice:
    """Direct libusb device handle for control transfers without claiming."""

    def __init__(self):
        self._ctx = None
        self._handle = None
        self._vid = 0
        self._pid = 0
        self._last_present_ping = 0.0

    def open(self, vid, pid):
        lib = _get_lib()

        # libusb_init
        ctx_p = ctypes.c_void_p()
        rc = lib.libusb_init(ctypes.byref(ctx_p))
        if rc != _LIBUSB_SUCCESS:
            raise RuntimeError(f"libusb_init failed: {rc}")
        self._ctx = ctx_p

        # libusb_open_device_with_vid_pid
        lib.libusb_open_device_with_vid_pid.restype = ctypes.c_void_p
        handle = lib.libusb_open_device_with_vid_pid(ctx_p, vid, pid)
        if not handle:
            lib.libusb_exit(ctx_p)
            self._ctx = None
            return False
        self._handle = ctypes.c_void_p(handle)
        self._vid = vid
        self._pid = pid
        self._last_present_ping = time.monotonic()
        return True

    def close(self):
        if self._handle:
            lib = _get_lib()
            lib.libusb_close(self._handle)
            self._handle = None
        if self._ctx:
            lib = _get_lib()
            lib.libusb_exit(self._ctx)
            self._ctx = None

    def check_present_periodic(self, min_interval_s=0.25):
        """Cheap liveness probe — at most once per ``min_interval_s``.

        Reduces the chance of submitting transfers right after unplug.
        Does not eliminate kernel races on disconnect.
        """
        if not self._handle:
            return False
        now = time.monotonic()
        if (now - self._last_present_ping) < min_interval_s:
            return True
        ok = self._ping_still_attached()
        self._last_present_ping = now
        return ok

    def _ping_still_attached(self):
        lib = _get_lib()
        lib.libusb_get_device.argtypes = [ctypes.c_void_p]
        lib.libusb_get_device.restype = ctypes.c_void_p
        lib.libusb_get_device_descriptor.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(_LibusbDeviceDescriptor),
        ]
        lib.libusb_get_device_descriptor.restype = ctypes.c_int

        dev = lib.libusb_get_device(self._handle)
        if not dev:
            return False
        desc = _LibusbDeviceDescriptor()
        rc = lib.libusb_get_device_descriptor(dev, ctypes.byref(desc))
        if rc == _LIBUSB_ERROR_NO_DEVICE:
            return False
        return rc == _LIBUSB_SUCCESS

    def ctrl_transfer(self, bm_request_type, b_request, w_value, w_index,
                      data, timeout_ms=1000):
        """Send a control transfer WITHOUT claiming any interface."""
        if not self._handle:
            raise RuntimeError("device not open")
        if not self.check_present_periodic():
            raise RuntimeError("USB device disconnected")
        lib = _get_lib()
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        rc = lib.libusb_control_transfer(
            self._handle,
            ctypes.c_uint8(bm_request_type),
            ctypes.c_uint8(b_request),
            ctypes.c_uint16(w_value),
            ctypes.c_uint16(w_index),
            buf,
            ctypes.c_uint16(len(data)),
            ctypes.c_uint(timeout_ms),
        )
        if rc < 0:
            errors = {
                _LIBUSB_ERROR_ACCESS: "access denied (need sudo)",
                _LIBUSB_ERROR_NO_DEVICE: "device disconnected",
                _LIBUSB_ERROR_NOT_FOUND: "device not found",
                _LIBUSB_ERROR_PIPE: "pipe error (device rejected transfer)",
            }
            msg = errors.get(rc, f"libusb error {rc}")
            raise RuntimeError(f"ctrl_transfer failed: {msg}")
        return rc

    @property
    def connected(self):
        return self._handle is not None

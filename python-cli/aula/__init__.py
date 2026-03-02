"""AULA F87 Keyboard Controller package."""

import ctypes
import os
import platform

# On macOS, patch ctypes to find libhidapi from Homebrew without DYLD_LIBRARY_PATH.
# Must run BEFORE any import of the 'hid' module.
if platform.system() == "Darwin":
    # Prefer Apple Silicon path (/opt/homebrew), fall back to Intel (/usr/local).
    _hidapi_path = next(
        (p for p in (
            "/opt/homebrew/lib/libhidapi.dylib",
            "/usr/local/lib/libhidapi.dylib",
        ) if os.path.exists(p)),
        None,
    )
    if _hidapi_path:
        _hidapi_names = {
            "libhidapi.dylib",
            "libhidapi-iohidmanager.so",
            "libhidapi-iohidmanager.so.0",
        }
        _orig_load_library = ctypes.cdll.LoadLibrary

        def _patched_load_library(name):
            if name in _hidapi_names:
                return ctypes.CDLL(_hidapi_path)
            return _orig_load_library(name)

        ctypes.cdll.LoadLibrary = _patched_load_library

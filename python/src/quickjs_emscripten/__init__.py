"""Python bindings for quickjs-emscripten (Phase 0 scaffold)."""

from ._api import (
    QuickJSHandle,
    QuickJSContext,
    QuickJSModule,
    QuickJSPythonBindingsNotReadyError,
    QuickJSResult,
    QuickJSRuntime,
    QuickJSUnwrapError,
    get_quickjs,
)
from ._ctypes_ffi import CtypesQuickJSFFI, load_ctypes_ffi
from ._generated_ffi import QuickJSFFIProtocol, QuickJSSyncFFIProtocol

__all__ = [
    "CtypesQuickJSFFI",
    "QuickJSHandle",
    "QuickJSContext",
    "QuickJSFFIProtocol",
    "QuickJSModule",
    "QuickJSPythonBindingsNotReadyError",
    "QuickJSResult",
    "QuickJSRuntime",
    "QuickJSSyncFFIProtocol",
    "QuickJSUnwrapError",
    "get_quickjs",
    "load_ctypes_ffi",
]

__version__ = "0.0.0"

"""ctypes-backed loader for the generated QuickJS FFI protocol."""

from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Any, get_type_hints

from ._generated_ffi import QuickJSFFIProtocol


def _to_ctype(annotation: Any) -> Any:
    if annotation is int:
        # Pointers and tagged integer values currently map to Python int in the
        # protocol, so we use pointer-width signed integers.
        return ctypes.c_ssize_t
    if annotation is bool:
        return ctypes.c_bool
    if annotation is float:
        return ctypes.c_double
    if annotation is str:
        return ctypes.c_char_p
    if annotation is type(None):
        return None
    raise TypeError(f"Unsupported annotation for ctypes mapping: {annotation!r}")


class CtypesQuickJSFFI:
    """Runtime implementation of :class:`QuickJSFFIProtocol` using ctypes."""

    DEBUG: bool

    def __init__(self, library_path: str | Path):
        self._library_path = str(library_path)
        self._lib = ctypes.CDLL(self._library_path)
        self._bind_functions()
        self.DEBUG = bool(self.QTS_BuildIsDebug()) if hasattr(self, "QTS_BuildIsDebug") else False

    def _bind_functions(self) -> None:
        for attr_name, attr_value in QuickJSFFIProtocol.__dict__.items():
            if not attr_name.startswith("QTS_"):
                continue
            if not callable(attr_value):
                continue

            c_fn = getattr(self._lib, attr_name)
            hints = get_type_hints(attr_value)
            parameter_names = [
                name for name in attr_value.__code__.co_varnames[: attr_value.__code__.co_argcount]
            ][1:]  # drop self
            c_fn.argtypes = [_to_ctype(hints[name]) for name in parameter_names]
            c_fn.restype = _to_ctype(hints.get("return", type(None)))
            setattr(self, attr_name, c_fn)


def load_ctypes_ffi(library_path: str | Path) -> QuickJSFFIProtocol:
    """Load a shared library implementing QTS_* symbols."""

    return CtypesQuickJSFFI(library_path)

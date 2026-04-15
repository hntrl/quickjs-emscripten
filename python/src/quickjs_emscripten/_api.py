"""Minimal sync API surface for quickjs-emscripten Python bindings."""

from __future__ import annotations

import ctypes
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._ctypes_ffi import load_ctypes_ffi
from ._generated_ffi import QuickJSFFIProtocol


class QuickJSPythonBindingsNotReadyError(NotImplementedError):
    """Raised when a required runtime binding detail is unavailable."""


class QuickJSUnwrapError(RuntimeError):
    """Raised when `unwrap_result` is called on an error result."""

    def __init__(self, cause: Any):
        super().__init__(str(cause))
        self.cause = cause


@dataclass(slots=True)
class QuickJSResult:
    """Result type used by calls that can fail with a VM exception."""

    value: QuickJSHandle | None = None
    error: QuickJSHandle | None = None


class QuickJSHandle:
    """Handle to a `JSValue*` in a specific QuickJS context."""

    def __init__(self, context: QuickJSContext, pointer: int):
        self._context = context
        self._pointer = int(pointer)
        self._alive = True

    @property
    def pointer(self) -> int:
        self._assert_alive()
        return self._pointer

    @property
    def alive(self) -> bool:
        return self._alive

    def dispose(self) -> None:
        if not self._alive:
            return
        self._context._ffi.QTS_FreeValuePointer(self._context._ctx, self._pointer)
        self._alive = False

    def consume(self, fn):
        self._assert_alive()
        try:
            return fn(self)
        finally:
            self.dispose()

    def _assert_alive(self) -> None:
        if not self._alive:
            raise RuntimeError("QuickJSHandle is disposed")

    def __enter__(self) -> QuickJSHandle:
        self._assert_alive()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.dispose()


class QuickJSRuntime:
    """Wraps a `JSRuntime*`."""

    def __init__(self, ffi: QuickJSFFIProtocol, rt: int):
        self._ffi = ffi
        self._rt = int(rt)
        self._alive = True

    @property
    def alive(self) -> bool:
        return self._alive

    def new_context(self, *, intrinsics: int = 0, add_helpers: bool = True) -> QuickJSContext:
        self._assert_alive()
        ctx = self._ffi.QTS_NewContext(self._rt, intrinsics)
        if not ctx:
            raise RuntimeError("QTS_NewContext returned null")
        context = QuickJSContext(self._ffi, self, int(ctx))
        if add_helpers:
            context.add_std_helpers()
        return context

    def set_memory_limit(self, limit_bytes: int) -> None:
        self._assert_alive()
        self._ffi.QTS_RuntimeSetMemoryLimit(self._rt, int(limit_bytes))

    def set_max_stack_size(self, stack_size_bytes: int) -> None:
        self._assert_alive()
        self._ffi.QTS_RuntimeSetMaxStackSize(self._rt, int(stack_size_bytes))

    def dispose(self) -> None:
        if not self._alive:
            return
        self._ffi.QTS_FreeRuntime(self._rt)
        self._alive = False

    def _assert_alive(self) -> None:
        if not self._alive:
            raise RuntimeError("QuickJSRuntime is disposed")

    def __enter__(self) -> QuickJSRuntime:
        self._assert_alive()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.dispose()


class QuickJSContext:
    """Wraps a `JSContext*`."""

    def __init__(self, ffi: QuickJSFFIProtocol, runtime: QuickJSRuntime, ctx: int):
        self._ffi = ffi
        self._runtime = runtime
        self._ctx = int(ctx)
        self._alive = True

    @property
    def alive(self) -> bool:
        return self._alive

    def eval_code(
        self,
        code: str,
        filename: str = "eval.js",
        *,
        detect_module: bool = True,
        eval_flags: int = 0,
    ) -> QuickJSResult:
        self._assert_alive()
        code_bytes = code.encode("utf-8")
        code_buffer = ctypes.create_string_buffer(code_bytes + b"\0")
        result_ptr = self._ffi.QTS_Eval(
            self._ctx,
            ctypes.addressof(code_buffer),
            len(code_bytes),
            filename.encode("utf-8"),
            1 if detect_module else 0,
            int(eval_flags),
        )
        error_ptr = self._ffi.QTS_ResolveException(self._ctx, result_ptr)
        if error_ptr:
            self._ffi.QTS_FreeValuePointer(self._ctx, result_ptr)
            return QuickJSResult(error=QuickJSHandle(self, int(error_ptr)))
        return QuickJSResult(value=QuickJSHandle(self, int(result_ptr)))

    def add_std_helpers(self) -> None:
        self._assert_alive()
        self._ffi.QTS_AddStdHelpers(self._ctx)

    def unwrap_result(self, result: QuickJSResult) -> QuickJSHandle:
        if result.error is not None:
            cause = self.dump(result.error)
            result.error.dispose()
            raise QuickJSUnwrapError(cause)
        if result.value is None:
            raise QuickJSUnwrapError("Result had neither value nor error")
        return result.value

    def get_number(self, handle: QuickJSHandle) -> float:
        self._assert_alive()
        return float(self._ffi.QTS_GetFloat64(self._ctx, handle.pointer))

    def get_string(self, handle: QuickJSHandle) -> str:
        self._assert_alive()
        c_string_ptr = self._ffi.QTS_GetString(self._ctx, handle.pointer)
        if not c_string_ptr:
            return ""
        try:
            return ctypes.string_at(c_string_ptr).decode("utf-8")
        finally:
            self._ffi.QTS_FreeCString(self._ctx, c_string_ptr)

    def dump(self, handle: QuickJSHandle) -> Any:
        self._assert_alive()
        c_string_ptr = self._ffi.QTS_Dump(self._ctx, handle.pointer)
        if not c_string_ptr:
            return None
        try:
            text = ctypes.string_at(c_string_ptr).decode("utf-8")
        finally:
            self._ffi.QTS_FreeCString(self._ctx, c_string_ptr)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if text == "undefined":
                return None
            return text

    def new_number(self, value: float) -> QuickJSHandle:
        self._assert_alive()
        ptr = self._ffi.QTS_NewFloat64(self._ctx, float(value))
        return QuickJSHandle(self, int(ptr))

    def dispose(self) -> None:
        if not self._alive:
            return
        self._ffi.QTS_FreeContext(self._ctx)
        self._alive = False

    def _assert_alive(self) -> None:
        if not self._alive:
            raise RuntimeError("QuickJSContext is disposed")

    def __enter__(self) -> QuickJSContext:
        self._assert_alive()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.dispose()


class QuickJSModule:
    """Entry point for creating runtimes and contexts from a bound FFI."""

    def __init__(self, ffi: QuickJSFFIProtocol):
        self._ffi = ffi

    def new_runtime(self) -> QuickJSRuntime:
        rt = self._ffi.QTS_NewRuntime()
        if not rt:
            raise RuntimeError("QTS_NewRuntime returned null")
        return QuickJSRuntime(self._ffi, int(rt))

    def new_context(self, *, intrinsics: int = 0, add_helpers: bool = True) -> QuickJSContext:
        runtime = self.new_runtime()
        try:
            return runtime.new_context(intrinsics=intrinsics, add_helpers=add_helpers)
        except Exception:
            runtime.dispose()
            raise

    def eval_code(self, code: str, filename: str = "eval.js") -> Any:
        with self.new_context() as context:
            result = context.eval_code(code, filename)
            value = context.unwrap_result(result)
            return value.consume(context.dump)


def get_quickjs(
    *,
    ffi: QuickJSFFIProtocol | None = None,
    library_path: str | Path | None = None,
) -> QuickJSModule:
    """Construct a module from a provided FFI object or a shared library path."""

    if ffi is None:
        if library_path is None:
            raise QuickJSPythonBindingsNotReadyError(
                "Pass `library_path=...` (for ctypes) or `ffi=...` to get_quickjs(). "
                "Automatic variant loading is not implemented yet."
            )
        ffi = load_ctypes_ffi(library_path)
    return QuickJSModule(ffi)

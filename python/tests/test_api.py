from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quickjs_emscripten import (  # noqa: E402
    QuickJSPythonBindingsNotReadyError,
    QuickJSUnwrapError,
    get_quickjs,
)


class FakeFFI:
    DEBUG = False

    def __init__(self) -> None:
        self.next_ptr = 100
        self._strings = []
        self.freed_values = []
        self.freed_contexts = []
        self.freed_runtimes = []

    def _ptr(self) -> int:
        self.next_ptr += 1
        return self.next_ptr

    def _c_string(self, text: str) -> int:
        buf = ctypes.create_string_buffer(text.encode("utf-8"))
        self._strings.append(buf)
        return ctypes.addressof(buf)

    def QTS_BuildIsDebug(self) -> int:
        return 0

    def QTS_NewRuntime(self) -> int:
        return self._ptr()

    def QTS_FreeRuntime(self, rt: int) -> None:
        self.freed_runtimes.append(rt)

    def QTS_NewContext(self, rt: int, intrinsics: int) -> int:
        _ = intrinsics
        if rt == 0:
            return 0
        return self._ptr()

    def QTS_AddStdHelpers(self, ctx: int) -> None:
        _ = ctx

    def QTS_FreeContext(self, ctx: int) -> None:
        self.freed_contexts.append(ctx)

    def QTS_Eval(
        self,
        ctx: int,
        js_code: int,
        js_code_length: int,
        filename: bytes,
        detectModule: int,
        evalFlags: int,
    ) -> int:
        _ = (ctx, js_code, js_code_length, filename, detectModule, evalFlags)
        return self._ptr()

    def QTS_ResolveException(self, ctx: int, maybe_exception: int) -> int:
        _ = (ctx, maybe_exception)
        return 0

    def QTS_FreeValuePointer(self, ctx: int, value: int) -> None:
        _ = ctx
        self.freed_values.append(value)

    def QTS_Dump(self, ctx: int, obj: int) -> int:
        _ = (ctx, obj)
        return self._c_string('{"ok":true}')

    def QTS_FreeCString(self, ctx: int, s: int) -> None:
        _ = (ctx, s)

    def QTS_GetFloat64(self, ctx: int, value: int) -> float:
        _ = (ctx, value)
        return 42.0

    def QTS_GetString(self, ctx: int, value: int) -> int:
        _ = (ctx, value)
        return self._c_string("hello")

    def QTS_NewFloat64(self, ctx: int, num: float) -> int:
        _ = (ctx, num)
        return self._ptr()


class TestApi(unittest.TestCase):
    def test_get_quickjs_requires_loader(self) -> None:
        with self.assertRaises(QuickJSPythonBindingsNotReadyError):
            get_quickjs()

    def test_eval_code_roundtrip(self) -> None:
        ffi = FakeFFI()
        module = get_quickjs(ffi=ffi)
        result = module.eval_code("1 + 1")
        self.assertEqual(result, {"ok": True})

    def test_unwrap_raises_on_error(self) -> None:
        class ErrorFFI(FakeFFI):
            def QTS_ResolveException(self, ctx: int, maybe_exception: int) -> int:
                _ = (ctx, maybe_exception)
                return self._ptr()

        ffi = ErrorFFI()
        module = get_quickjs(ffi=ffi)
        with module.new_context() as context:
            result = context.eval_code("throw new Error('x')")
            with self.assertRaises(QuickJSUnwrapError):
                context.unwrap_result(result)

    def test_handle_dispose_calls_ffi_free(self) -> None:
        ffi = FakeFFI()
        module = get_quickjs(ffi=ffi)
        with module.new_context() as context:
            handle = context.new_number(7)
            ptr = handle.pointer
            handle.dispose()
            self.assertIn(ptr, ffi.freed_values)


if __name__ == "__main__":
    unittest.main()

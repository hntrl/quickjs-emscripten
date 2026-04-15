# quickjs-emscripten (Python)

This directory contains the Python bindings scaffold for quickjs-emscripten.

Current status:

- package/build wiring is in place;
- low-level `QTS_*` protocol is generated from `c/interface.c`;
- initial `ctypes` FFI loader can bind a shared library implementing `QTS_*`;
- sync runtime/context primitives are partially implemented
  (`new_runtime`, `new_context`, `eval_code`, `unwrap_result`, `dump`, number/string helpers);
- initial ctypes loader exists via `quickjs_emscripten.load_ctypes_ffi(...)`.

Regenerate the protocol from `c/interface.c`:

```bash
cd python
make generate-ffi
```

Build and smoke-test a native shared library (`QTS_*` symbols):

```bash
cd python
make smoke-native
```

Run local unit tests:

```bash
python3 -m unittest discover -s python/tests -p "test_*.py"
```

The implementation plan and acceptance criteria live in:

- `doc/python-bindings.md`

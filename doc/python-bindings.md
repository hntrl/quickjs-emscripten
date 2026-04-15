# Python Bindings Design for quickjs-emscripten

Status: proposal

Implemented so far (initial scaffold milestones):

- `python/` package structure with wheel/sdist build wiring.
- CI workflow for Python package build/import checks.
- Generated low-level sync FFI protocol from `c/interface.c` (`QTS_*` surface).
- Initial `ctypes` FFI loader and partial sync module/runtime/context API.

## Goal

Add Python bindings that reuse the existing `QTS_*` C interface and expose a Python API that maps closely to the current JS API (`QuickJSWASMModule` / `QuickJSRuntime` / `QuickJSContext`), while minimizing C changes.

## Constraints

- Prefer reusing existing C wrapper functions in `c/interface.c` (`QTS_*`) instead of adding new VM primitives.
- Keep behavior consistent with the JS API where possible (handles, explicit disposal, result/error unions, module loader semantics).
- Avoid large C refactors; isolate any C changes to callback plumbing.
- Preserve support for both bellard/quickjs and quickjs-ng (same current compatibility model).

## Current Architecture (Relevant Seams)

1. C boundary is already centralized.
   - `c/interface.c` exports `QTS_*` functions for all VM operations.
   - This is generated into typed TS FFI via `scripts/generate.ts`.

2. JS API is a wrapper over low-level FFI.
   - `quickjs-emscripten-core` owns lifetimes, scopes, runtime/context abstractions, and error mapping.
   - Variant packages provide platform-specific FFI/module loaders.

3. Callback path is currently Emscripten-specific.
   - C -> host callbacks (`callFunction`, interrupt, module loading) are wired through `EM_JS`.
   - This is the one place where Python cannot directly reuse behavior today.

## Proposed Architecture

Implement a new Python package group that mirrors the JS layering:

1. Low-level Python FFI package (`quickjs_ffi_types_py` + generated bindings)
   - Generate Python function signatures from `QTS_*` declarations in `c/interface.c`.
   - Keep the generator source-of-truth the same as TS (`scripts/generate.ts` input model), with a Python output target.
   - Expose near-1:1 wrappers for all exported C functions.

2. Python core package (`quickjs_emscripten_core_py`)
   - `QuickJSModule`, `QuickJSRuntime`, `QuickJSContext`, `QuickJSHandle`, `Lifetime`, `Scope`.
   - Behavior aligned with TS core:
     - explicit handle disposal,
     - owned/borrowed pointer handling,
     - `SuccessOrFail` style results for eval/call/execute pending jobs,
     - error unwrap logic into Python exceptions.

3. Python top-level package (`quickjs_emscripten_py`)
   - User-facing entrypoints similar to JS:
     - `get_quickjs()`
     - `new_runtime()`
     - `new_context()`
   - Expose sync-first API in phase 1, asyncify later.

## Minimal C Changes

### Why changes are needed

Currently, callback mechanisms rely on `EM_JS`, which assumes a JS host object (`Module.callbacks`). A Python host cannot provide these callbacks through that path.

### Proposed change

Add a small host-callback registration shim in `c/interface.c`:

- New setter API to register function pointers for:
  - host function invocation (`qts_host_call_function` equivalent),
  - interrupt callback,
  - module source loader,
  - module normalizer,
  - host-ref free finalizer callback.
- `#ifdef __EMSCRIPTEN__` path remains as-is for current JS behavior.
- non-Emscripten path calls registered function pointers.

This isolates Python-specific host integration without changing the existing `QTS_*` execution primitives.

## Build and Packaging

### Native target for Python

Add native shared-library builds for Python consumption:

- Build `c/interface.c` + vendored QuickJS as a shared lib (`.so`/`.dylib`/`.pyd`).
- Reuse existing compatibility flags (`QTS_USE_QUICKJS_NG` optional variant).
- No Emscripten dependency for Python runtime path.

### Python packaging

- New `python/` workspace with:
  - `pyproject.toml`
  - wheel build backend (recommended: `scikit-build-core` + CMake, or `setuptools` with extension module).
- Ship compiled extension and pure-python wrapper layer.

## API Surface (Python)

Phase 1 target API:

```python
from quickjs_emscripten import get_quickjs

qjs = get_quickjs()
ctx = qjs.new_context()
try:
    result = ctx.eval_code("1 + 1")
    value = ctx.unwrap_result(result)
    print(ctx.get_number(value))
    value.dispose()
finally:
    ctx.dispose()
```

Core parity targets:

- module-level: `eval_code`, `new_runtime`, `new_context`
- runtime-level:
  - `set_memory_limit`, `set_max_stack_size`, `execute_pending_jobs`
  - `set_interrupt_handler` / `remove_interrupt_handler`
  - `set_module_loader` / `remove_module_loader`
- context-level:
  - value creation (`new_number`, `new_string`, `new_object`, `new_function`, etc.)
  - property ops (`get_prop`, `set_prop`, `define_prop`, `get_own_property_names`)
  - execution (`eval_code`, `call_function`, `call_method`)
  - conversion helpers (`dump`, `get_number`, `get_string`, `get_bigint`, etc.)

## Memory and Lifetime Model

Mirror TS model directly:

- every `JSValue*` exposed to Python is wrapped in `QuickJSHandle`;
- handles are explicitly disposable (`dispose()`), plus context-manager support (`__enter__/__exit__`);
- runtime/context disposal should detect leaked handles in debug builds, consistent with current behavior.

## Asyncify Strategy

Phase 1: no asyncify support in Python binding.

- Focus on sync variant parity first.
- Asyncify APIs can be added once callback shim and sync host-callback flow are stable.
- Asyncify-specific constraints (single in-flight async action/module) should be preserved if implemented.

## Compatibility Matrix

Phase 1 required:

- CPython 3.10+
- macOS (arm64/x86_64), Linux x86_64
- bellard/quickjs library target

Phase 2:

- quickjs-ng variant
- Windows builds
- asyncify support

## Phased Implementation Plan

### Phase 0: design and scaffolding

- Add `doc/python-bindings.md` (this document).
- Create `python/` package skeleton and CI job scaffolding (build-only).
- Choose initial packaging stack:
  - current scaffold uses `setuptools` + `python -m build` for wheel/sdist wiring;
  - reevaluate `scikit-build-core` vs setuptools extension build when native C extension work begins.

Exit criteria:

- CI can build a wheel artifact on at least one platform.

### Phase 1: core sync runtime (no host callbacks)

- Generate and expose low-level Python wrappers for `QTS_*`.
- Implement Python `QuickJSModule`, `QuickJSRuntime`, `QuickJSContext` wrappers.
- Support eval/property/value APIs and pending job execution.
- Port a subset of existing JS tests to Python parity tests.

Exit criteria:

- Python can evaluate code, manipulate values, and enforce memory/stack limits.
- No callback-dependent features required yet (`new_function`, module loader, interrupt can be stubbed or unsupported).

### Phase 2: callback shim + callback-backed APIs

- Add C callback registration shim for non-Emscripten host.
- Implement Python host callback bridge:
  - `new_function` host callbacks,
  - interrupt handlers,
  - module loader/normalizer.
- Add parity tests for callbacks and module loading.

Exit criteria:

- Python callback features match current JS semantics for sync runtime.

### Phase 3: packaging hardening and distribution

- Build wheels for target OS/arch matrix.
- Add README usage docs and API reference generation.
- Add leak and lifecycle stress tests in CI.

Exit criteria:

- Publishable Python package with tested binaries and stable API docs.

### Phase 4: asyncify and advanced parity

- Add asyncify-compatible FFI and Python async APIs.
- Validate async module loading and async host callbacks.

Exit criteria:

- Asyncified Python API feature-complete with documented constraints.

## Acceptance Criteria

1. Functional parity for sync core APIs:
   - create runtime/context, eval JS, call functions, set/get props, inspect/dump values.
2. Lifecycle safety:
   - handles enforce use-after-dispose checks,
   - runtime/context disposal is deterministic,
   - debug/leak checks pass in CI.
3. Callback parity (phase 2+):
   - Python host functions callable from guest JS,
   - interrupt handler terminates infinite loops,
   - module loader and normalizer work for ES modules.
4. Build/distribution:
   - wheel artifacts for declared support matrix,
   - package import/test works in clean virtualenv.

## Risks and Mitigations

- Risk: lifetime bugs or double-frees in Python wrapper layer.
  - Mitigation: preserve explicit ownership model from TS (`Lifetime`, `Scope`) rather than hiding it.

- Risk: callback ABI drift between C and generated wrappers.
  - Mitigation: keep `c/interface.c` declarations as single source and generate Python + TS bindings from the same parser path.

- Risk: scope creep from asyncify early.
  - Mitigation: strict sync-first milestone; asyncify explicitly phase 4.

## Open Questions

1. Should Python API prioritize strict TS parity naming, or Pythonic aliases first (`eval_code` vs `evalCode`)?
2. Should `quickjs-ng` be first-class in phase 1, or deferred to phase 2?
3. Which packaging toolchain is preferred for maintainers (`scikit-build-core` vs setuptools + custom build)?
4. Should leaked handles raise immediately at runtime/context `dispose()`, or only in debug builds?

## Non-goals (Initial Work)

- Browser/Pyodide integration.
- Replacing existing JS package architecture.
- Making GC fully automatic for QuickJS handles (explicit disposal remains canonical).

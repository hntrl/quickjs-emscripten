#!/usr/bin/env python3
"""Smoke test native library loading + eval via quickjs_emscripten API."""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path


def shared_lib_extension() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return ".dylib"
    if system == "linux":
        return ".so"
    if system == "windows":
        return ".dll"
    raise RuntimeError(f"Unsupported platform: {platform.system()}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--library",
        type=Path,
        default=repo_root / "python" / "build" / "native" / (
            "libquickjs_emscripten" + shared_lib_extension()
        ),
        help="Path to native quickjs-emscripten shared library",
    )
    args = parser.parse_args()
    library = args.library if args.library.is_absolute() else repo_root / args.library

    sys.path.insert(0, str(repo_root / "python" / "src"))
    import quickjs_emscripten as q

    module = q.get_quickjs(library_path=library)
    value = module.eval_code("1 + 1")
    if value != 2:
        raise RuntimeError(f"Expected eval result 2, got {value!r}")

    console_result = module.eval_code("console.log(1 + 1)")
    if console_result not in {"undefined", None}:
        raise RuntimeError(
            f"Expected console.log return to be undefined/None, got {console_result!r}"
        )

    context = module.new_context()
    try:
        number_handle = context.new_number(7)
        try:
            number = context.get_number(number_handle)
            if number != 7:
                raise RuntimeError(f"Expected get_number(new_number(7)) == 7, got {number!r}")
        finally:
            number_handle.dispose()
    finally:
        context.dispose()

    print(f"Native smoke OK: {library}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

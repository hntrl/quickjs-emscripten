#!/usr/bin/env python3
"""Build a native shared library exposing quickjs-emscripten QTS_* symbols."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
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


def link_mode_flag() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "-dynamiclib"
    if system in {"linux", "windows"}:
        return "-shared"
    raise RuntimeError(f"Unsupported platform: {platform.system()}")


def platform_libs() -> list[str]:
    system = platform.system().lower()
    if system == "darwin":
        return ["-lm", "-lpthread"]
    if system == "linux":
        return ["-lm", "-ldl", "-lpthread"]
    if system == "windows":
        return []
    raise RuntimeError(f"Unsupported platform: {platform.system()}")


def build_native_lib(output: Path, cc: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    quickjs_root = repo_root / "vendor" / "quickjs"
    quickjs_version = (quickjs_root / "VERSION").read_text(encoding="utf-8").strip()

    sources = [
        repo_root / "c" / "interface.c",
        quickjs_root / "quickjs.c",
        quickjs_root / "dtoa.c",
        quickjs_root / "libregexp.c",
        quickjs_root / "libunicode.c",
        quickjs_root / "cutils.c",
        quickjs_root / "quickjs-libc.c",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        cc,
        "-O2",
        "-fPIC",
        "-fwrapv",
        "-D_GNU_SOURCE",
        f'-DCONFIG_VERSION="{quickjs_version}"',
        link_mode_flag(),
        *(str(src) for src in sources),
        "-o",
        str(output),
        *platform_libs(),
    ]

    print("Building native library:")
    print(" ", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(repo_root))
    print(f"Built: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output shared-library path. Defaults to python/build/native/libquickjs_emscripten.<ext>",
    )
    parser.add_argument(
        "--cc",
        default=os.environ.get("CC", "cc"),
        help="C compiler executable (default: $CC or cc)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    output = args.output
    if output is None:
        output = repo_root / "python" / "build" / "native" / (
            "libquickjs_emscripten" + shared_lib_extension()
        )
    else:
        if not output.is_absolute():
            output = repo_root / output

    build_native_lib(output=output, cc=args.cc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

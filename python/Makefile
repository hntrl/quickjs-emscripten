.PHONY: generate-ffi build-native smoke-native

generate-ffi:
	python3 scripts/generate_ffi_protocol.py

build-native:
	python3 scripts/build_native_lib.py

smoke-native: build-native
	python3 scripts/smoke_native_eval.py

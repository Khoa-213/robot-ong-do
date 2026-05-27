import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = PROJECT_ROOT / "fairino-python-sdk" / "windows"
LIB_PATH = SDK_ROOT / "libfairino"


def setup_fairino_sdk_path() -> tuple[Path, Path]:
    """Prepare sys.path and DLL search path for the Fairino Windows SDK."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    print("[SDK] Project root:", PROJECT_ROOT)
    print("[SDK] SDK root:", SDK_ROOT)
    print("[SDK] DLL path:", LIB_PATH)

    if not SDK_ROOT.exists():
        raise FileNotFoundError(f"Fairino SDK root not found: {SDK_ROOT}")

    sdk_root_text = str(SDK_ROOT)
    if sdk_root_text not in sys.path:
        sys.path.append(sdk_root_text)
        print("[SDK] Added SDK_ROOT to sys.path")
    else:
        print("[SDK] SDK_ROOT already in sys.path")

    if LIB_PATH.exists():
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(LIB_PATH))
            print("[SDK] Added LIB_PATH to DLL search path")
        else:
            print("[SDK] os.add_dll_directory is not available on this Python")
    else:
        print("[SDK] LIB_PATH does not exist, skipping DLL path setup")

    return SDK_ROOT, LIB_PATH

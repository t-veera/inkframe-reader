"""
PlatformIO pre-build script: expose GxEPD2_BW::_buffer as protected.

GxEPD2_BW declares _buffer private, but InkFrame's shim subclasses it via
GxEPD2_BW_INKFRAME to redirect EInkDisplay::frameBuffer to GxEPD2's own
internal page buffer — so CrossPoint draws directly into the buffer that
display(false) sends to the panel, with no writeImage copy step.

The patch is idempotent:
  * marker present   -> already patched, skip
  * original present -> apply patch
  * neither          -> GxEPD2 source diverged, abort the build
"""

Import("env")  # noqa: F821 (SCons-injected global)
import os
import sys


def _emit(stream, msg):
    try:
        buf = getattr(stream, "buffer", None)
        if buf is not None:
            buf.write(msg.encode("utf-8", "replace"))
            buf.flush()
        else:
            stream.write(msg)
    except Exception:
        pass


ORIGINAL = "  private:\n    uint8_t _buffer[(GxEPD2_Type::WIDTH / 8) * page_height];\n    bool _using_partial_mode"
PATCHED  = "  protected:\n    uint8_t _buffer[(GxEPD2_Type::WIDTH / 8) * page_height];\n  private:\n    bool _using_partial_mode"
MARKER   = "  protected:\n    uint8_t _buffer"

lib_dir = os.path.join(
    env.subst("$PROJECT_LIBDEPS_DIR"),  # noqa: F821
    env.subst("$PIOENV"),               # noqa: F821
    "GxEPD2",
    "src",
    "GxEPD2_BW.h",
)

if not os.path.isfile(lib_dir):
    _emit(sys.stderr, f"patch_gxepd2: GxEPD2_BW.h not found at {lib_dir} — skipping\n")
else:
    text = open(lib_dir, "r", encoding="utf-8").read()
    if MARKER in text:
        _emit(sys.stdout, "patch_gxepd2: GxEPD2_BW.h already patched\n")
    elif ORIGINAL in text:
        text = text.replace(ORIGINAL, PATCHED, 1)
        open(lib_dir, "w", encoding="utf-8").write(text)
        _emit(sys.stdout, "patch_gxepd2: GxEPD2_BW.h patched (_buffer -> protected)\n")
    else:
        _emit(sys.stderr, "patch_gxepd2: GxEPD2_BW.h source diverged — cannot apply patch\n")
        env.Exit(1)  # noqa: F821

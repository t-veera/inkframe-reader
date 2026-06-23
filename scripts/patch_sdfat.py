"""
PlatformIO pre-build script: apply InkFrame's SdFat patches.

SdFat is pulled as a managed dependency into `.pio/libdeps/<env>/SdFat`, which
is regenerated on a clean build -- so edits there do not survive. This script
re-applies our fixes on every build via idempotent string replacement (SdFat is
a registry package with no `.git`, so `git apply` is not an option).

Why these patches exist (InkFrame SD card, slow no-name SDHC card):
  1. SD command/read/write timeouts of 300/300/600 ms are too short for this
     card -- CMD58 (OCR read) timed out, which in turn left the card detected as
     byte-addressed SD2 instead of block-addressed SDHC, so every read past
     sector 0 returned zeros and the filesystem never mounted.
  2. Even with the longer timeout the OCR top byte is occasionally misread; we
     retry CMD58 until OCR bit31 (card-ready) is set before checking the CCS
     (SDHC) bit.

Each patch is idempotent:
  * marker already present  -> already patched, skip
  * original text present   -> apply replacement
  * neither present         -> SdFat source diverged, abort the build
"""

Import("env")  # noqa: F821 (SCons-injected global)
import os
import sys


def _emit(stream, msg):
    # Best-effort status output. PlatformIO's SCons runner wraps stdout/stderr in
    # a stream whose text codec is cp1252 on Windows and raised UnicodeEncodeError
    # on writes; this output is purely informational, so never let it abort the
    # build. Prefer the raw byte buffer, fall back to text, swallow anything else.
    try:
        buf = getattr(stream, "buffer", None)
        if buf is not None:
            buf.write(msg.encode("utf-8", "replace"))
            buf.flush()
        else:
            stream.write(msg)
    except Exception:
        pass


# (relative path under SdFat/, marker that proves it's patched, original, patched)
PATCHES = [
    (
        os.path.join("src", "SdCard", "SdCardInfo.h"),
        "const uint16_t SD_CMD_TIMEOUT = 2000;",
        "const uint16_t SD_CMD_TIMEOUT = 300;",
        "const uint16_t SD_CMD_TIMEOUT = 2000;",
    ),
    (
        os.path.join("src", "SdCard", "SdCardInfo.h"),
        "const uint16_t SD_READ_TIMEOUT = 2000;",
        "const uint16_t SD_READ_TIMEOUT = 300;",
        "const uint16_t SD_READ_TIMEOUT = 2000;",
    ),
    (
        os.path.join("src", "SdCard", "SdCardInfo.h"),
        "const uint16_t SD_WRITE_TIMEOUT = 2000;",
        "const uint16_t SD_WRITE_TIMEOUT = 600;",
        "const uint16_t SD_WRITE_TIMEOUT = 2000;",
    ),
    (
        os.path.join("src", "SdCard", "SdSpiCard", "SdSpiCard.cpp"),
        "INKFRAME: on slow cards the OCR top byte",
        # original
        """  // if SD2 read OCR register to check for SDHC card
  if (cardType == SD_CARD_TYPE_SD2) {
    if (cardCommand(CMD58, 0)) {
      sdError(SD_CARD_ERROR_CMD58);
      goto fail;
    }
    if ((spiReceive() & 0XC0) == 0XC0) {
      cardType = SD_CARD_TYPE_SDHC;
    }
    // Discard rest of ocr - contains allowed voltage range.
    for (uint8_t i = 0; i < 3; i++) {
      spiReceive();
    }
  }""",
        # patched
        """  // if SD2 read OCR register to check for SDHC card
  if (cardType == SD_CARD_TYPE_SD2) {
    // INKFRAME: on slow cards the OCR top byte can be misread, leaving an SDHC
    // card detected as byte-addressed SD2 (reads past sector 0 then return
    // garbage/zeros). After ACMD41 the card is powered up, so OCR bit31 (ready)
    // must be 1 -- retry CMD58 until we get a sane OCR, then check CCS (bit30).
    uint8_t ocr0 = 0;
    for (uint8_t tries = 0; tries < 8; tries++) {
      if (cardCommand(CMD58, 0)) {
        sdError(SD_CARD_ERROR_CMD58);
        goto fail;
      }
      ocr0 = spiReceive();
      // Discard rest of ocr - contains allowed voltage range.
      for (uint8_t i = 0; i < 3; i++) {
        spiReceive();
      }
      if (ocr0 & 0X80) {
        break;  // bit31 set => valid OCR read
      }
      spiStop();
      delay(2);
    }
    if ((ocr0 & 0XC0) == 0XC0) {
      cardType = SD_CARD_TYPE_SDHC;
    }
  }""",
    ),
]


def patch_sdfat(env):
    libdeps_dir = os.path.join(env["PROJECT_DIR"], ".pio", "libdeps")
    if not os.path.isdir(libdeps_dir):
        return
    for env_dir in os.listdir(libdeps_dir):
        sdfat_dir = os.path.join(libdeps_dir, env_dir, "SdFat")
        if not os.path.isdir(sdfat_dir):
            continue
        for rel_path, marker, original, patched in PATCHES:
            _apply_one(sdfat_dir, rel_path, marker, original, patched)


def _apply_one(sdfat_dir, rel_path, marker, original, patched):
    # Binary I/O throughout: the SdFat sources and our replacement text are
    # plain ASCII, and bytes mode avoids Windows' cp1252 console/file codec
    # (which raised UnicodeEncodeError under the PlatformIO pre-build runner).
    path = os.path.join(sdfat_dir, rel_path)
    if not os.path.isfile(path):
        _emit(sys.stderr, "ERROR: SdFat file missing, cannot patch: %s\n" % path)
        raise SystemExit(1)
    with open(path, "rb") as f:
        content = f.read()
    if marker.encode("ascii") in content:
        return  # already patched
    orig_b = original.encode("ascii")
    if orig_b not in content:
        _emit(
            sys.stderr,
            "ERROR: SdFat patch target not found in %s (source diverged); "
            "review scripts/patch_sdfat.py\n" % rel_path,
        )
        raise SystemExit(1)
    content = content.replace(orig_b, patched.encode("ascii"))
    with open(path, "wb") as f:
        f.write(content)
    _emit(sys.stdout, "Applied SdFat patch: %s\n" % rel_path)


patch_sdfat(env)  # noqa: F821

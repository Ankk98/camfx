#!/usr/bin/env bash
set -euo pipefail

NODE_PATH="${1:-v4l2:/dev/video4}"
OUT="${2:-./_pipewire_test_frame.png}"
WIDTH="${WIDTH:-640}"
HEIGHT="${HEIGHT:-480}"
FRAMERATE="${FRAMERATE:-30}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-15}"
RESET_KEEP_FORMAT="${RESET_KEEP_FORMAT:-0}"
PIPEWIRE_FORMAT="${PIPEWIRE_FORMAT:-YUY2}"
WAIT_FOR_CAPTURE_STATE="${WAIT_FOR_CAPTURE_STATE:-1}"

echo "[test] PipeWire V4L2 loopback test"
echo "[test] node_path: ${NODE_PATH}"
echo "[test] out:        ${OUT}"
echo "[test] caps hint:  ${WIDTH}x${HEIGHT}@${FRAMERATE}"

if [[ "${EUID}" -eq 0 && "${ALLOW_ROOT:-0}" != "1" ]]; then
  echo "[warn] Running as root."
  echo "[warn] PipeWire is per-user (your $XDG_RUNTIME_DIR), so running with sudo may hide PipeWire nodes."
  echo "[warn] Re-run without sudo, or set ALLOW_ROOT=1 to bypass this check."
  exit 10
fi

if ! command -v pw-cli >/dev/null 2>&1; then
  echo "[error] pw-cli not found in PATH" >&2
  exit 127
fi

if ! command -v gst-launch-1.0 >/dev/null 2>&1; then
  echo "[error] gst-launch-1.0 not found in PATH" >&2
  exit 127
fi

if ! pw-cli ls Node 2>/dev/null | rg -q "object\\.path = \"${NODE_PATH//\//\\/}\""; then
  echo "[error] PipeWire node with object.path='${NODE_PATH}' not found" >&2
  pw-cli ls Node 2>/dev/null | rg -n "object\\.path" | sed -n '1,30p' || true
  exit 2
fi

if [[ "${RESET_KEEP_FORMAT}" == "1" ]]; then
  if command -v v4l2-ctl >/dev/null 2>&1; then
    # Unlock format so PipeWire can negotiate.
    # 'keep_format=1' will lock the currently negotiated format forever until set back to 0.
    v4l2-ctl -c keep_format=0 -d "${NODE_PATH#v4l2:/}" >/dev/null 2>&1 || true
    echo "[test] keep_format unlocked (set to 0)"
    # Show current negotiated capture format (best-effort)
    v4l2-ctl --get-fmt-video -d "${NODE_PATH#v4l2:/}" 2>/dev/null | sed -n '1,20p' || true
  else
    echo "[warn] v4l2-ctl not found; skipping keep_format reset"
  fi
fi

if [[ "${WAIT_FOR_CAPTURE_STATE}" == "1" ]]; then
  if command -v v4l2-ctl >/dev/null 2>&1; then
    DEVNODE="${NODE_PATH#v4l2:}"
    VIDEO_NR="${DEVNODE##/dev/video}"
    SYS_STATE="/sys/class/video4linux/video${VIDEO_NR}/state"
    # Only wait when sysfs exists; otherwise just run gst-launch.
    if [[ -e "${SYS_STATE}" ]]; then
      echo "[test] waiting for ${SYS_STATE} == capture ..."
      SECS_LEFT="${TIMEOUT_SECONDS}"
      while [[ "${SECS_LEFT}" -gt 0 ]]; do
        STATE="$(cat "${SYS_STATE}" 2>/dev/null || true)"
        if [[ "${STATE}" == "capture" ]]; then
          echo "[test] loopback is in capture state"
          break
        fi
        sleep 0.25
        SECS_LEFT=$((SECS_LEFT - 1))
      done
    fi
  fi
fi

rm -f "${OUT}" >/dev/null 2>&1 || true

# Optional: verify that /dev/video4 can be read as video via ffmpeg
# (helps distinguish “loopback has frames” vs “PipeWire negotiation fails”).
VERIFY_V4L2_READ="${VERIFY_V4L2_READ:-1}"
V4L2_INPUT_FORMAT="${V4L2_INPUT_FORMAT:-yuv420p}"
if [[ "${VERIFY_V4L2_READ}" == "1" ]]; then
  if command -v ffmpeg >/dev/null 2>&1; then
    echo "[test] verifying /dev/video4 produces non-black frames..."
    DEVNODE="${NODE_PATH#v4l2:/}"
    TMP_JPG="./_v4l2_read_verify.jpg"
    rm -f "${TMP_JPG}" >/dev/null 2>&1 || true
    # Best-effort: v4l2loopback frequently uses YU12 for planar 4:2:0.
    timeout "${TIMEOUT_SECONDS}s" ffmpeg -hide_banner -loglevel error \
      -f v4l2 -video_size "${WIDTH}x${HEIGHT}" -framerate "${FRAMERATE}/1" \
      -input_format "${V4L2_INPUT_FORMAT}" -i "${DEVNODE}" -frames:v 1 -f image2 -q:v 2 "${TMP_JPG}" -y >/dev/null 2>&1 || true

    if [[ -s "${TMP_JPG}" ]]; then
      python3 - <<'PY' "${TMP_JPG}"
import sys
from PIL import Image
import numpy as np
path = sys.argv[1]
img = Image.open(path).convert("RGB")
a = np.asarray(img)
mn = int(a.min())
mx = int(a.max())
mean = float(a.mean())
print(f"[ok] v4l2 read stats: mean={mean:.3f} min={mn} max={mx}")
if mx <= 5 and mean <= 5:
  raise SystemExit(5)
PY
    else
      echo "[warn] v4l2 read verify: frame capture failed (or produced empty file)."
    fi
  else
    echo "[warn] ffmpeg not found; skipping v4l2 read verify."
  fi
fi

set +e
GSTREAMER_LOG="$(timeout "${TIMEOUT_SECONDS}s" gst-launch-1.0 -e -q \
  pipewiresrc path="${NODE_PATH}" num-buffers=1 do-timestamp=false \
  ! video/x-raw,format="${PIPEWIRE_FORMAT}",width="${WIDTH}",height="${HEIGHT}",framerate="${FRAMERATE}/1" \
  ! videoconvert ! video/x-raw,format=RGB ! pngenc \
  ! filesink location="${OUT}" 2>&1)"
RC=$?
set -e

if [[ $RC -ne 0 ]]; then
  echo "[fail] gst-launch returned non-zero exit code: ${RC}"
  echo "[fail] gst output (tail):"
  echo "${GSTREAMER_LOG}" | tail -n 40
  if echo "${GSTREAMER_LOG}" | rg -q 'Device or resource busy|VIDIOC_S_FMT'; then
    echo "[hint] This usually means another process already has /dev/video4 open (e.g. camfx/ffmpeg)."
    echo "[hint] For an end-to-end negotiation test, you likely need to stop the writer first."
    echo "[hint] Try: pkill -f \"ffmpeg.*v4l2.*\\/dev\\/video4\" (or stop camfx), then re-run."
  fi
  exit 3
fi

if [[ ! -s "${OUT}" ]]; then
  echo "[fail] Frame file was not written (empty or missing): ${OUT}" >&2
  exit 4
fi

python3 - "$OUT" <<'PY'
import sys
from PIL import Image
import numpy as np

path = sys.argv[1]
img = Image.open(path).convert("RGB")
a = np.asarray(img)
mean = a.mean()
mn = a.min()
mx = a.max()

# Very rough "black frame" heuristic: everything near 0.
is_black = (mx <= 5 and mean <= 5)

print(f"[ok] frame stats: mean={mean:.3f} min={mn} max={mx}")
print(f"[ok] black_frame: {is_black}")
if is_black:
  raise SystemExit(5)
PY

echo "[ok] PipeWire pipewiresrc negotiation succeeded and frame looks non-black."


#!/bin/bash
# Voice-Pro launcher for macOS (Apple Silicon)
# Uses uv + .venv instead of Miniconda. See docs/installation-macos.md.

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements-voice-mac.txt"
MARKER="$VENV_DIR/.voice-pro-installed"

echo "========================================================================="
echo "  Voice-Pro for macOS (uv + MPS)"
echo "========================================================================="

# 1. uv check
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed."
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 2. brew deps check (informational — install with: brew install ffmpeg openfst pkg-config)
for tool in ffmpeg git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "WARNING: '$tool' not found in PATH. Run: brew install $tool"
    fi
done

# 3. Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python 3.10 virtual environment in $VENV_DIR ..."
    uv venv -p 3.10 "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 4. Install requirements (skip if marker present and requirements unchanged)
if [ ! -f "$MARKER" ] || [ "$REQUIREMENTS" -nt "$MARKER" ]; then
    echo "Installing dependencies (this is a one-time step)..."
    # pip is needed inside the venv because Kokoro shells out to pip to
    # download the spaCy en_core_web_sm model on first run.
    uv pip install pip
    # PyTorch 2.5.1 mac arm64 build with native MPS support.
    uv pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1
    uv pip install -r "$REQUIREMENTS"
    touch "$MARKER"
    echo "Dependencies installed."
else
    echo "Dependencies up to date."
fi

# 5. macOS-specific runtime env
# - Allow MPS to fall back to CPU for ops that aren't natively supported.
#   (Some ops like Demucs's high-channel conv1d still raise instead of
#   falling back, but this catches many other cases like vocos's istft.)
export PYTORCH_ENABLE_MPS_FALLBACK=1

# 6. Launch
echo "Launching Voice-Pro on http://localhost:7860 ..."
echo "(Press Ctrl-C to stop.)"
exec python start-voice.py

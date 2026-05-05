# Voice-Pro on macOS (Apple Silicon)

This guide installs Voice-Pro on macOS without conda, using `uv` for Python
environment management. Tested on macOS 25.3 (Darwin) / Apple Silicon
(M-series), Python 3.10, PyTorch 2.5.1 with MPS acceleration.

> **Status:** Phase 1+2+3+4 verified. F5-TTS / E2-TTS voice cloning works
> with MPS GPU. Whisper / Faster-Whisper / WhisperX / Whisper-Timestamped /
> Edge-TTS / Kokoro / Demucs / yt-dlp / translation all work. CosyVoice
> works once `pynini` and `WeTextProcessing` are installed (see Optional:
> CosyVoice support).
>
> **For YouTube dubbing, see [`tools/yt-dub`](../tools/yt-dub/README.md)** —
> a focused CLI built on top of this venv that turns any YouTube URL into
> a translated dubbed mp4 in one command, without going through Voice-Pro's
> Gradio UI.

## Prerequisites

```bash
# Homebrew packages
brew install ffmpeg git cmake openfst pkg-config

# uv (Python package + venv manager) — install once
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Xcode Command Line Tools (`xcode-select --install`) is also required for
building any C extensions.

## Install

```bash
# 1. Clone the macos-support branch
git clone -b macos-support https://github.com/<your-fork>/voice-pro.git
cd voice-pro

# 2. Create a Python 3.10 venv (uv auto-downloads CPython 3.10 if needed)
uv venv -p 3.10 .venv
source .venv/bin/activate

# 3. Install pip into the venv (Kokoro internally calls pip via subprocess
#    to download the spaCy en_core_web_sm model on first run)
uv pip install pip

# 4. Install PyTorch 2.5.1 (mac arm64 wheel, ships with MPS backend)
uv pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1

# 5. Install voice-pro requirements (macOS-patched)
uv pip install -r requirements-voice-mac.txt
```

That's it — no conda, no Miniconda, no CUDA toolkit.

## Run

```bash
source .venv/bin/activate
python start-voice.py
```

Open <http://localhost:7860> in your browser.

First boot downloads ~470 MB of models to `~/.cache/huggingface`
(demucs, edge-tts samples, kokoro samples, celebrities30s) — the
~9 GB CosyVoice2-0.5B model is deferred to level 1 and not downloaded
unless you explicitly request it.

## Verify the install (optional)

```bash
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'MPS available: {torch.backends.mps.is_available()}')
print(f'MPS built: {torch.backends.mps.is_built()}')
"
# Expected: MPS available: True, MPS built: True
```

## Performance notes

Tested on M-series Mac, tiny test audio (~4s English):

| Component       | Device | Time    | Notes |
|-----------------|--------|---------|-------|
| OpenAI Whisper  | CPU    | 0.35s   | tiny model |
| Faster-Whisper  | CPU    | 0.91s   | int8 quant; ctranslate2 has no MPS support |
| WhisperX        | CPU    | 0.45s   | uses faster-whisper backend |
| Whisper-Timest. | CPU    | 0.48s   | word-level timestamps work |
| Edge-TTS        | HTTP   | 2.17s   | network API, no local model |
| Kokoro          | CPU    | 3.89s   | 3.5s output |
| Demucs (4-stem) | CPU    | 4.5s    | 5.85s input; MPS unsupported (see below) |
| F5-TTS clone    | MPS    | 11s     | 2.6s output |
| E2-TTS clone    | MPS    | 30s     | 0.94s output |
| Translation     | HTTP   | 1.7s    | deep-translator (Google) |
| **Full pipeline (ASR + translate + TTS)** | mixed | **6.78s** | en→zh dubbing |

## Recommended: yt-dub CLI for YouTube dubbing

If your goal is "translate and dub a YouTube video" (the most common
single use-case), skip the Gradio UI and use the focused CLI shipped at
[`tools/yt-dub`](../tools/yt-dub/README.md):

```bash
source .venv/bin/activate
pip install -e tools/yt-dub
yt-dub "https://www.youtube.com/watch?v=..."
```

Pipeline: yt-dlp + ffmpeg → faster-whisper ASR → translate (Google /
Claude / GPT) → edge-tts async parallel → ffmpeg assemble. Includes
`atempo` time-compression so dubbed segments stay aligned with the
original timeline (no overlapping audio). Output goes to
`~/Movies/yt-dub/<video-id>/`.

End-to-end on a 25-minute video: ~9 minutes with Google translate,
~3-4 minutes with `--translator claude`. See `yt-dub --help` for all
options including voice picker (`--list-voices`), source/target
languages, ASR model, and original-audio mixing.

## Optional: CosyVoice support

CosyVoice's Chinese/English text normalization needs either Alibaba's
`ttsfrd` (no arm64 wheel) or `WeTextProcessing` (which depends on
`pynini`). The trick on macOS Apple Silicon:

```bash
source .venv/bin/activate

# pynini needs to build from source against Homebrew's openfst.
# Versions ≤ 2.1.6 are NOT compatible with openfst 1.8.4. Use 2.1.7+.
export CPPFLAGS="-I/opt/homebrew/include $CPPFLAGS"
export LDFLAGS="-L/opt/homebrew/lib $LDFLAGS"
uv pip install --no-build-isolation pynini==2.1.7

# WeTextProcessing pins an older pynini, so install with --no-deps to keep
# our newer one.
uv pip install --no-deps WeTextProcessing
uv pip install importlib_resources

# Verify
python -c "from tn.chinese.normalizer import Normalizer as Z; from tn.english.normalizer import Normalizer as E; \
  print(Z().normalize('今天是2026年5月4日，温度22度')); print(E().normalize('It costs \$100 and takes 5 hours'))"
```

CosyVoice2-0.5B model (~9 GB) is deferred from level 0 to level 1 in
`abus_hf_files-voice.json` — it does not download automatically on first
boot. To opt in:

```bash
python -c "from app.abus_hf import AbusHuggingFace; \
  AbusHuggingFace.initialize('voice'); \
  AbusHuggingFace.hf_download_models(file_type='cosyvoice', level=1)"
```

Note: F5-TTS and E2-TTS already cover zero-shot voice cloning with native
MPS acceleration and are recommended for most users; CosyVoice is mainly
worth installing if you need streaming TTS or instructed-style control.

## Known Limitations on macOS

### 1. Demucs runs on CPU, not MPS

PyTorch's MPS backend rejects 1-D conv layers with output channels > 65536,
which Demucs hits internally. `PYTORCH_ENABLE_MPS_FALLBACK=1` does not fix
this case. Pass `--device cpu` (or set `device='cpu'` in voice-pro's
Demucs settings). On M-series Macs, CPU separation is fast enough for
typical clips.

### 2. WhisperX / Faster-Whisper run on CPU

These use `ctranslate2` under the hood, which has no MPS support. They
auto-fall back to CPU on Macs without CUDA. The original voice-pro code
already handles this correctly via `torch.cuda.is_available()`.

### 3. CosyVoice2-0.5B (~9 GB) deferred to level 1

`app/abus_hf_files-voice.json` ships with `CosyVoice2-0.5B.zip` at
`level: 1` (was `level: 0`). The Voice-Pro UI boots without it because
only the small `celebrities30s.zip` (~16 MB) is referenced at startup.
If you want CosyVoice anyway (and you've solved limitation #1), bump
the level back to 0 or download manually.

## Troubleshooting

**`No module named 'pkg_resources'` from pyworld at import.**
The macOS requirements file pins `setuptools<70` which keeps the legacy
`pkg_resources` shim. If you upgraded setuptools manually, downgrade:
`uv pip install 'setuptools<70'`.

**`Failed to build openai-whisper==20240930` during install.**
This is an old sdist that uses `pkg_resources` in its setup.py. The
macOS requirements bumps it to `>=20250625`. Use `requirements-voice-mac.txt`,
not `requirements-voice-cpu.txt`.

**Kokoro fails downloading `en_core_web_sm`.**
Kokoro shells out to `pip` to install the spaCy English model. Since `uv
venv` doesn't include `pip` by default, run `uv pip install pip` once.

**`ImportError: No module named 'tn'` when invoking CosyVoice.**
You haven't installed `pynini` + `WeTextProcessing` yet. The
`cosyvoice/cli/frontend.py` macOS patch lets the module *import* without
them, but actually *running* CosyVoice still needs the text normalizer.
See "Optional: CosyVoice support" above.

**`fatal error: 'fst/util.h' file not found` building pynini.**
You forgot `export CPPFLAGS="-I/opt/homebrew/include"` (and the matching
LDFLAGS). The Homebrew openfst headers aren't on the default search path.

**`'CompileInternal' function not viable` building pynini 2.1.5/2.1.6.**
Those versions are incompatible with Homebrew's openfst 1.8.4. Use
`pynini==2.1.7` or newer.

**Gradio UI starts but Whisper transcription is slow.**
On Apple Silicon, OpenAI Whisper can in principle use MPS, but
`whisper.load_model(..., device='mps')` causes correctness issues at
the time of writing. Stick with `device='cpu'` (the default voice-pro
auto-selection does this when CUDA is unavailable).

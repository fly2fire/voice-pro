# yt-dub

A focused CLI for "YouTube URL → translated dubbed mp4". Built on top of the
voice-pro Python venv (faster-whisper / edge-tts / deep-translator / yt-dlp /
ffmpeg). Designed for macOS Apple Silicon — runs CPU/MPS transparently, no
CUDA.

## Why a CLI instead of voice-pro's Gradio UI?

voice-pro's web UI is a kitchen sink of every TTS / ASR / RVC / dubbing
feature, with dozens of parameters and tabs. For the single use-case "translate
and dub a YouTube video," it's overkill and error-prone. `yt-dub` does
exactly one thing, well, in one command.

## Install

You already have everything if you ran voice-pro's `start-mac.sh` once. From
the voice-pro repo root:

```bash
source .venv/bin/activate
pip install -e tools/yt-dub
```

`yt-dub` is now on your PATH. Or run it without installing:

```bash
python -m yt_dub.cli --help
```

## Usage

```bash
# Default: en → zh-CN dub, Google translate, Xiaoxiao voice
yt-dub https://www.youtube.com/watch?v=r6sGWTCMz2k

# Pure dub vs mix with original audio
yt-dub <url> --mix-bg 0       # default — replace audio entirely
yt-dub <url> --mix-bg 25      # keep original at 25% as ambience

# Translator backends
yt-dub <url> --translator google           # default, free
yt-dub <url> --translator claude           # uses ANTHROPIC_API_KEY (best quality)
yt-dub <url> --translator gpt              # uses OPENAI_API_KEY
yt-dub <url> --translator none             # skip translation (dub same lang)

# Pick a different voice (run --list-voices first)
yt-dub <url> --voice zh-CN-YunjianNeural   # 男声 / male

# Resume from where it left off (default behavior; --no-resume to force)
yt-dub <url> --no-resume

# Custom output / workdir
yt-dub <url> -o ~/dubbed.mp4 --workdir /tmp/yt-dub-test/

# Adjust speech rate (Chinese is denser than English; bump up if it overflows)
yt-dub <url> --rate "+20%"

# Harder Whisper model for tricky audio
yt-dub <url> --asr small      # or medium / large-v3

# Different language
yt-dub <url> -s en -t ja-JP --voice ja-JP-NanamiNeural

# Direct PROXY / cookies override
yt-dub <url> --proxy http://localhost:7890 --cookies-from-browser chrome
```

```bash
# List voices
yt-dub --list-voices --voice-lang zh-CN
yt-dub --list-voices --voice-lang ja-JP --voice-gender Male
```

## Output layout

Default workdir is `~/Movies/yt-dub/<video-id>/`:

```
<video-id>/
├── source.mp4              # downloaded video
├── source.wav              # extracted audio (16kHz mono)
├── subs.src.srt            # original-language subtitles (from ASR)
├── subs.dst.srt            # translated subtitles
├── tts_segments/           # per-segment TTS mp3 files
├── dubbed.wav              # full-length dubbed track
├── meta.json               # config + timings
└── <video-id>.dubbed.mp4   # final output (mp4 with soft-sub track)
```

## Pipeline

```
yt-dub <url>
  │
  ├── 1) Download (yt-dlp + ffmpeg extract audio)
  ├── 2) ASR     (faster-whisper, CPU int8, VAD-filtered)
  ├── 3) Translate  (google / claude / gpt / none)
  ├── 4) TTS     (edge-tts, async parallel, default 8 concurrent)
  └── 5) Mux     (ffmpeg: assemble timed audio + soft subs)
```

## Performance

On M-series Mac (no CUDA):

| 25-min video | Component       | Time   |
|--------------|-----------------|--------|
|              | Download        | ~30s   |
|              | ASR (base)      | ~90s   |
|              | Translate (google) | ~5min |
|              | Translate (claude) | ~30s |
|              | TTS (edge, 8 par) | ~2min |
|              | Mux             | ~30s   |
|              | **Total**       | **~5–10 min** |

Use `--translator claude` for best translation quality and 10× speedup over
Google's per-segment HTTP API.

## Troubleshooting

**`Sign in to confirm you're not a bot`** during download
→ open YouTube in your browser, log in. yt-dub reads cookies via
  `--cookies-from-browser firefox` (default). Try `--cookies-from-browser
  chrome` if Firefox isn't logged in.

**Subtitles not visible in QuickTime**
→ The mp4 has a soft subtitle track. In QuickTime: View → Subtitles → 中文字幕.
  Or open with IINA / VLC (auto-displays). To burn subtitles into the
  picture, you need ffmpeg compiled with `--enable-libass` (Homebrew's
  default ffmpeg currently lacks it; install via the
  `homebrew-ffmpeg/ffmpeg` tap).

**Whisper says "language=en" but audio is Chinese**
→ Pass `-s zh` explicitly. Whisper's auto-detect is unreliable for short
  audio.

**Chinese TTS overflows segment boundaries**
→ Bump `--rate "+25%"`. Edge-TTS supports up to about +50%.

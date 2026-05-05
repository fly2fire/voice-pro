---
name: yt-dub
description: Translate and dub a YouTube video into another language as a single mp4. Use when the user wants to "翻译这个 YouTube 视频", "给这个视频配中文", "看英文教程的中文版", "dub a YouTube video", "translate and voice-over", "make a Chinese version of this video" — anything that maps a YouTube URL to a translated dubbed video. Skip Voice-Pro's Gradio UI; the CLI does the same end-to-end pipeline (yt-dlp → faster-whisper → translator → edge-tts → ffmpeg) in one command, with proper time-alignment so dubbed audio doesn't overlap.
---

# yt-dub: YouTube → translated dubbed mp4

A focused CLI built on top of the voice-pro Python venv. One command takes
a YouTube URL and produces a dubbed mp4 with embedded subtitles.

Source: `tools/yt-dub` in the voice-pro repo (macos-support branch).
Below `<voice-pro>` refers to wherever the user cloned the repo.

## Pipeline

```
URL → yt-dlp + ffmpeg (download)
    → faster-whisper (ASR with VAD, CPU int8)
    → translator (google / claude / gpt / none)
    → edge-tts (async parallel synthesis)
    → atempo time-compression (so dubbed segments fit their slots)
    → ffmpeg (assemble timed audio + soft-sub mux)
```

## Prerequisites

The CLI lives in the voice-pro venv. To use it:

```bash
cd <voice-pro>
source .venv/bin/activate
# install once
pip install -e tools/yt-dub
# `yt-dub` is now on PATH
```

YouTube downloads need: an HTTP proxy if the user is in mainland China
(default `http://localhost:7890`), and browser cookies (default
`firefox`). The CLI auto-detects `$HTTPS_PROXY` and `$HTTP_PROXY`.

## Default behaviour

```bash
yt-dub "https://www.youtube.com/watch?v=..."
```

Outputs to `~/Movies/yt-dub/<video-id>/<video-id>.dubbed.mp4`. Default
config: en → zh-CN, Whisper `base`, Google translator, voice
`zh-CN-XiaoxiaoNeural` (晓晓 / female), TTS rate `+15%`, mp4 with soft
subtitle track.

The workdir keeps every intermediate file; rerunning the same URL
resumes from where it left off (skip with `--no-resume`).

## Common patterns

| Goal | Flags |
|---|---|
| Best translation quality | `--translator claude` (needs `ANTHROPIC_API_KEY`) |
| Best ASR accuracy | `--asr small` or `--asr large-v3` (slower) |
| Male voice | `--voice zh-CN-YunjianNeural` |
| Different target language | `-t ja-JP --voice ja-JP-NanamiNeural` |
| Keep original audio as ambience | `--mix-bg 25` (25% volume mixed under dub) |
| Custom output path | `-o ~/dubbed.mp4` |
| Force re-run all steps | `--no-resume` |
| Browse voices | `yt-dub --list-voices --voice-lang zh-CN` |

## When the user asks for "best quality"

Default to:

```bash
yt-dub "<url>" --asr small --translator claude --voice <pick-by-gender>
```

Pick the voice by the speaker's gender in the source video:
- Male source: `zh-CN-YunjianNeural` (新闻播报感强) or `zh-CN-YunxiNeural` (年轻男声)
- Female source: `zh-CN-XiaoxiaoNeural` (default) or `zh-CN-XiaoyiNeural`
- Documentary / 中性: `zh-CN-YunyangNeural`

If the user has no `ANTHROPIC_API_KEY` set, fall back to `--translator gpt`
(needs `OPENAI_API_KEY`) or stay with `--translator google` (free but 5-10×
slower and lower quality on technical terms).

## When the user asks for speed

```bash
yt-dub "<url>" --asr tiny --translator google
```

`tiny` model is ~17× realtime, total pipeline for a 25-min video drops to
~5 min (most of which is Google translate's per-segment HTTP delay).

## Performance reference (M-series Mac, 25-min video)

| Component | Time | Note |
|---|---|---|
| Download | ~30s | depends on proxy bandwidth |
| ASR (tiny) | ~80s | base ≈ 90s, small ≈ 3min, large-v3 ≈ 8min |
| Translate (Google) | ~6min | per-segment HTTP, dominates total time |
| Translate (Claude) | ~30s | LLM batch, 10× faster than Google |
| TTS (Edge, 8 parallel) | ~85s | barely scales with video length |
| atempo fit | ~30s | runs only on segments that overflow |
| Mux | ~15s | ffmpeg `-c:v copy`, no re-encode |

## Known good combos

```bash
# Quick preview — see what the video says, throwaway quality
yt-dub "<url>" --asr tiny --translator google

# Production-grade — what you'd publish
yt-dub "<url>" --asr small --translator claude --voice zh-CN-YunjianNeural --mix-bg 20

# Documentary / educational — male voice, retain ambience
yt-dub "<url>" --voice zh-CN-YunyangNeural --mix-bg 30 --translator claude

# Tutorial / demo — clean dub, no original audio bleed
yt-dub "<url>" --voice zh-CN-YunxiNeural --translator claude --mix-bg 0
```

## Time alignment

Chinese TTS is typically 30-80% longer than English source. Without
correction, segment N's audio overlaps N+1, clipping trailing content.

The pipeline's mux phase (`fit_segments_to_slots`) detects each TTS mp3
that exceeds its SRT slot and applies `ffmpeg atempo=R` (R = actual/slot,
capped at 1.8 to keep speech intelligible). About 40-50% of segments
typically need this for English→Chinese dubs.

If the user reports "it sounds rushed in places" → that's atempo working;
suggest `--rate "+25%"` to make the raw TTS shorter so fewer segments
need compression.

If the user reports "audio still overlaps / words are cut off" → some
segments are extreme (>1.8× slot, atempo cap). Either:
1. Use a more concise translator (`--translator claude` produces tighter
   output than Google's literal style)
2. Bump TTS rate further: `--rate "+30%"`

## Output layout

```
~/Movies/yt-dub/<video-id>/
├── source.mp4                # downloaded video
├── source.wav                # extracted audio (16kHz mono)
├── subs.src.srt              # original-language subtitles (from ASR)
├── subs.dst.srt              # translated subtitles
├── tts_segments/             # per-segment TTS mp3 (raw, untouched)
├── tts_segments_fit/         # per-segment TTS mp3 (after atempo fit)
├── dubbed.wav                # full-length dubbed track
├── meta.json                 # config + per-step timings
└── <video-id>.dubbed.mp4     # final output (mp4 with soft-sub track)
```

## Troubleshooting

**`Sign in to confirm you're not a bot`**
The user's Firefox isn't logged into YouTube. Either log in first, or
pass `--cookies-from-browser chrome` (or `safari` / `edge` / `brave`).
yt-dlp's `--cookies-from-browser safari` requires Full Disk Access on
macOS — usually easier to use Firefox or Chrome.

**`No such command '<URL>'`**
The user typed `yt-dub <URL>` with `?v=...` unquoted; zsh expanded the
`?`. Wrap the URL in quotes.

**Subtitles invisible in QuickTime**
The mp4 has a soft subtitle track but QuickTime doesn't auto-display it.
Tell the user: View → Subtitles → 中文字幕. Or open with IINA or VLC,
which auto-display.

**Whisper detected wrong language**
Pass `-s <lang>` explicitly. Whisper's auto-detect is unreliable on
short audio.

**Translator fails with rate-limit / 429**
For Google: just retry, the segments that failed get marked and the next
run resumes from them. For Claude/GPT: check API key validity and quota.

## Voice catalog quick reference (zh-CN)

```
zh-CN-XiaoxiaoNeural   Female  晓晓   default, friendly female
zh-CN-XiaoyiNeural     Female  晓伊   gentler female
zh-CN-YunjianNeural    Male    云健   news-anchor style
zh-CN-YunxiNeural      Male    云希   younger male
zh-CN-YunxiaNeural     Male    云夏   neutral male
zh-CN-YunyangNeural    Male    云扬   documentary narration
```

For other locales: `yt-dub --list-voices --voice-lang ja-JP` etc.

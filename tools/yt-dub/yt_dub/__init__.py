"""yt-dub: YouTube → translated dubbed video CLI.

Pipeline: download → ASR → translate → TTS → assemble → mux.
Designed for macOS Apple Silicon (uses faster-whisper CPU + edge-tts + ffmpeg).
"""
__version__ = "0.1.0"

"""Faster-Whisper transcription with VAD."""
from __future__ import annotations

from pathlib import Path

from ..utils import Segment


def transcribe(
    audio_path: Path,
    *,
    model_name: str = "base",
    language: str | None = None,
    beam_size: int = 5,
    compute_type: str = "int8",
    vad: bool = True,
) -> tuple[list[Segment], dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    kwargs: dict = dict(beam_size=beam_size)
    if language:
        kwargs["language"] = language
    if vad:
        kwargs["vad_filter"] = True
        kwargs["vad_parameters"] = dict(min_silence_duration_ms=500)
    raw_segments, info = model.transcribe(str(audio_path), **kwargs)
    segs: list[Segment] = []
    for i, seg in enumerate(raw_segments, 1):
        text = seg.text.strip()
        if not text:
            continue
        segs.append(Segment(idx=i, start=seg.start, end=seg.end, text=text))
    meta = {
        "language": info.language,
        "language_probability": float(info.language_probability),
        "duration": float(info.duration),
    }
    return segs, meta

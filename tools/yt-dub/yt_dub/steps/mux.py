"""Assemble TTS segments into a full audio track + mux with video."""
from __future__ import annotations

from pathlib import Path

from ..utils import Segment, run


def _ffprobe_duration(path: Path) -> float:
    res = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
    )
    try:
        return float((res.stdout or "0").strip())
    except ValueError:
        return 0.0


def assemble_audio(
    segs: list[Segment],
    seg_dir: Path,
    out_audio: Path,
    *,
    total_duration: float,
    sample_rate: int = 24000,
    batch: int = 40,
    on_progress=None,
) -> Path:
    """Build a full-length silent track and overlay each TTS segment at its start time."""
    work = out_audio.parent
    base = work / "_audio_base.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate={sample_rate}",
            "-t",
            f"{total_duration + 5:.2f}",
            str(base),
        ]
    )
    valid = [s for s in segs if (seg_dir / f"{s.idx:05d}.mp3").stat().st_size > 0]
    cur = base
    n_batches = (len(valid) + batch - 1) // batch
    for i, batch_start in enumerate(range(0, len(valid), batch)):
        chunk = valid[batch_start : batch_start + batch]
        out = work / f"_audio_mix_{batch_start:05d}.wav"
        cmd: list[str] = ["ffmpeg", "-y", "-i", str(cur)]
        for seg in chunk:
            cmd += ["-i", str(seg_dir / f"{seg.idx:05d}.mp3")]
        parts: list[str] = []
        for j, seg in enumerate(chunk):
            ms = int(seg.start * 1000)
            parts.append(f"[{j+1}:a]adelay={ms}|{ms}[d{j}]")
        mix_inputs = "[0:a]" + "".join(f"[d{j}]" for j in range(len(chunk)))
        parts.append(
            f"{mix_inputs}amix=inputs={len(chunk)+1}:duration=first:dropout_transition=0:normalize=0[out]"
        )
        cmd += [
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[out]",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            str(out),
        ]
        run(cmd)
        cur = out
        if on_progress:
            on_progress(i + 1, n_batches)
    # Move final to out_audio
    run(["cp", str(cur), str(out_audio)])
    return out_audio


def mux_dubbed(
    video: Path,
    dubbed_audio: Path,
    subs_zh: Path,
    out: Path,
    *,
    keep_bg_pct: int = 0,
) -> Path:
    """Mux video + (optionally mixed) audio + soft subtitle track into mp4.

    keep_bg_pct=0 -> pure dubbed audio.
    keep_bg_pct=25 -> dubbed at 100% + original at 25% mixed in.
    """
    cmd: list[str] = ["ffmpeg", "-y", "-i", str(video), "-i", str(dubbed_audio), "-i", str(subs_zh)]
    if keep_bg_pct > 0:
        bg_vol = keep_bg_pct / 100.0
        cmd += [
            "-filter_complex",
            f"[0:a]volume={bg_vol}[bg];[1:a]volume=1.0[fg];[bg][fg]amix=inputs=2:duration=first[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
        ]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += [
        "-map",
        "2:s",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        "language=chi",
        "-metadata:s:s:0",
        "title=中文字幕",
        "-shortest",
        str(out),
    ]
    run(cmd)
    return out

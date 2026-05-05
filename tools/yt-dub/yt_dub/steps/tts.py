"""Edge-TTS based parallel synthesis."""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

from ..utils import Segment


async def _synth_one(seg: Segment, voice: str, rate: str, out_dir: Path, sem: asyncio.Semaphore) -> tuple[int, bool]:
    out = out_dir / f"{seg.idx:05d}.mp3"
    if out.exists() and out.stat().st_size > 0:
        return seg.idx, True
    async with sem:
        try:
            com = edge_tts.Communicate(seg.text, voice, rate=rate)
            await com.save(str(out))
            return seg.idx, True
        except Exception:
            return seg.idx, False


async def synth_all_async(
    segs: list[Segment], voice: str, rate: str, out_dir: Path, concurrency: int, on_progress=None
) -> dict[int, bool]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    tasks = [_synth_one(s, voice, rate, out_dir, sem) for s in segs]
    results: dict[int, bool] = {}
    done = 0
    fail = 0
    for fut in asyncio.as_completed(tasks):
        idx, ok = await fut
        results[idx] = ok
        done += 1
        if not ok:
            fail += 1
        if on_progress:
            on_progress(done, len(segs), fail=fail)
    return results


def synth_all(segs: list[Segment], voice: str, rate: str, out_dir: Path, concurrency: int = 8, on_progress=None) -> dict[int, bool]:
    return asyncio.run(synth_all_async(segs, voice, rate, out_dir, concurrency, on_progress))


def list_voices() -> list[dict]:
    """Return a list of available Edge-TTS voices."""
    return asyncio.run(edge_tts.list_voices())

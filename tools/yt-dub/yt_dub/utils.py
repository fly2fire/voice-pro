"""Shared helpers."""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Segment:
    idx: int
    start: float  # seconds
    end: float    # seconds
    text: str

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


def fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s % 1) * 1000):03d}"


def parse_srt(path: Path) -> list[Segment]:
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\n+", text.strip())
    out: list[Segment] = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            idx = int(lines[0])
        except ValueError:
            continue
        m = re.match(
            r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1]
        )
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        body = " ".join(line for line in lines[2:] if line.strip())
        if not body:
            continue
        out.append(Segment(idx=idx, start=start, end=end, text=body))
    return out


def write_srt(segs: Iterable[Segment], path: Path) -> None:
    parts: list[str] = []
    for seg in segs:
        parts.append(
            f"{seg.idx}\n{fmt_srt_time(seg.start)} --> {fmt_srt_time(seg.end)}\n"
            f"{seg.text.strip()}\n"
        )
    path.write_text("\n".join(parts), encoding="utf-8")


def run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess. Raises on failure unless check=False."""
    res = subprocess.run(cmd, capture_output=capture, text=True)
    if check and res.returncode != 0:
        sys.stderr.write(f"Command failed: {' '.join(cmd[:6])}{'...' if len(cmd) > 6 else ''}\n")
        if res.stderr:
            sys.stderr.write(res.stderr[-2000:] + "\n")
        raise SystemExit(res.returncode)
    return res


def need(tool: str) -> None:
    """Ensure a binary is on PATH or exit."""
    from shutil import which

    if not which(tool):
        sys.stderr.write(f"Error: '{tool}' not found on PATH. Install it first.\n")
        raise SystemExit(2)


def video_id_from_url(url: str) -> str:
    """Extract YouTube video ID from a URL or return the URL hash."""
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    import hashlib

    return hashlib.md5(url.encode()).hexdigest()[:11]

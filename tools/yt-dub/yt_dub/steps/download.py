"""Download video + audio from YouTube using yt-dlp."""
from __future__ import annotations

from pathlib import Path

from ..utils import run


def download_video(
    url: str,
    out_dir: Path,
    proxy: str | None,
    cookies_browser: str | None,
    use_ejs: bool = True,
    max_height: int = 720,
) -> tuple[Path, Path]:
    """Download video (mp4) + extracted audio (wav). Skips if files already exist."""
    out_dir.mkdir(parents=True, exist_ok=True)
    video = out_dir / "source.mp4"
    audio = out_dir / "source.wav"

    args: list[str] = ["yt-dlp", "--no-update"]
    if proxy:
        args += ["--proxy", proxy]
    if cookies_browser:
        args += ["--cookies-from-browser", cookies_browser]
    if use_ejs:
        args += ["--remote-components", "ejs:github"]

    if not video.exists():
        run(
            args
            + [
                "-f",
                f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]",
                "--merge-output-format",
                "mp4",
                "-o",
                str(video),
                url,
            ]
        )
    if not audio.exists():
        run(["ffmpeg", "-y", "-i", str(video), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio)])
    return video, audio


def get_metadata(url: str, proxy: str | None, cookies_browser: str | None, use_ejs: bool = True) -> dict:
    """Fetch title/duration/uploader without downloading."""
    args: list[str] = ["yt-dlp", "--no-update", "--skip-download", "--print", "%(title)s|||%(duration_string)s|||%(uploader)s"]
    if proxy:
        args += ["--proxy", proxy]
    if cookies_browser:
        args += ["--cookies-from-browser", cookies_browser]
    if use_ejs:
        args += ["--remote-components", "ejs:github"]
    args.append(url)
    res = run(args, check=True)
    line = (res.stdout or "").strip().splitlines()[-1] if res.stdout else ""
    parts = line.split("|||")
    return {
        "title": parts[0] if len(parts) > 0 else "",
        "duration": parts[1] if len(parts) > 1 else "",
        "uploader": parts[2] if len(parts) > 2 else "",
    }

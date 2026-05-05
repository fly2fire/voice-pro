"""yt-dub CLI entry."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .pipeline import Config, run_pipeline
from .steps import tts as tts_step
from .utils import need, video_id_from_url

app = typer.Typer(
    add_completion=False,
    rich_markup_mode="rich",
    help="YouTube → translated dubbed video. macOS-friendly. See README for details.",
    no_args_is_help=True,
)
console = Console()


def _default_workdir(video_id: str) -> Path:
    return Path.home() / "Movies" / "yt-dub" / video_id


@app.command()
def dub(
    url: str = typer.Argument(..., help="YouTube URL."),
    lang_from: str = typer.Option("en", "--lang-from", "-s", help="Source language code (Whisper)."),
    lang_to: str = typer.Option("zh-CN", "--lang-to", "-t", help="Target language code."),
    voice: str = typer.Option("zh-CN-XiaoxiaoNeural", "--voice", "-V", help="Edge-TTS voice. Use --list-voices to see all."),
    asr_model: str = typer.Option("base", "--asr", help="Whisper model: tiny/base/small/medium/large-v3"),
    rate: str = typer.Option("+15%", "--rate", help="TTS rate adjustment (e.g. +15%, -10%)."),
    mix_bg: int = typer.Option(0, "--mix-bg", min=0, max=100, help="Keep original audio at N%% volume mixed under dub. 0=pure dub."),
    translator: str = typer.Option("google", "--translator", help="google / claude / gpt / none"),
    workdir: Optional[Path] = typer.Option(None, "--workdir", help="Working directory (intermediate files). Default: ~/Movies/yt-dub/<video-id>/"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output mp4 path. Default: <workdir>/<video-id>.dubbed.mp4"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="HTTP proxy. Default: $HTTP_PROXY or $HTTPS_PROXY."),
    cookies_browser: Optional[str] = typer.Option("firefox", "--cookies-from-browser", help="Browser to read cookies from. Default: firefox. Pass empty to disable."),
    concurrency: int = typer.Option(8, "--concurrency", "-j", help="TTS parallelism."),
    no_resume: bool = typer.Option(False, "--no-resume", help="Force re-run all steps, don't reuse intermediate files."),
):
    """Run the full dubbing pipeline."""
    need("yt-dlp")
    need("ffmpeg")
    need("ffprobe")

    vid = video_id_from_url(url)
    wd = workdir or _default_workdir(vid)
    out = output or (wd / f"{vid}.dubbed.mp4")
    if cookies_browser == "":
        cookies_browser = None
    if proxy is None:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None

    cfg = Config(
        url=url,
        workdir=wd,
        out_path=out,
        lang_from=lang_from,
        lang_to=lang_to,
        voice=voice,
        asr_model=asr_model,
        rate=rate,
        mix_bg=mix_bg,
        translator=translator,
        proxy=proxy,
        cookies_browser=cookies_browser,
        concurrency=concurrency,
        resume=not no_resume,
    )
    console.print(f"[dim]video_id: {vid}")
    console.print(f"[dim]workdir:  {wd}")
    console.print(f"[dim]output:   {out}")
    console.print(f"[dim]proxy:    {proxy or '(none)'}")
    console.print()
    run_pipeline(cfg)


@app.command("list-voices")
def list_voices(
    lang: Optional[str] = typer.Option(None, "--lang", help="Filter by language code, e.g. zh-CN, ja-JP, en-US"),
    gender: Optional[str] = typer.Option(None, "--gender", help="Male or Female"),
):
    """List Edge-TTS voices."""
    voices = tts_step.list_voices()
    if lang:
        voices = [v for v in voices if v.get("Locale", "").lower().startswith(lang.lower())]
    if gender:
        voices = [v for v in voices if v.get("Gender", "").lower() == gender.lower()]
    table = Table(show_header=True, header_style="bold")
    table.add_column("ShortName")
    table.add_column("Gender")
    table.add_column("Locale")
    table.add_column("Friendly")
    for v in voices:
        table.add_row(
            v.get("ShortName", ""),
            v.get("Gender", ""),
            v.get("Locale", ""),
            v.get("FriendlyName", "").replace("Microsoft ", "").replace(" Online (Natural) - ", " / "),
        )
    console.print(f"[dim]{len(voices)} voices")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

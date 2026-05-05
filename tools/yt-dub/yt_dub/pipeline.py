"""Top-level pipeline: orchestrates download → ASR → translate → TTS → mux."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .steps import asr, download, mux, translate, tts
from .utils import Segment, parse_srt, video_id_from_url, write_srt

console = Console()


@dataclass
class Config:
    url: str
    workdir: Path
    out_path: Path
    lang_from: str = "en"
    lang_to: str = "zh-CN"
    voice: str = "zh-CN-XiaoxiaoNeural"
    asr_model: str = "base"
    rate: str = "+15%"
    mix_bg: int = 0
    translator: str = "google"
    proxy: str | None = None
    cookies_browser: str | None = "firefox"
    concurrency: int = 8
    resume: bool = True

    def to_meta(self) -> dict:
        d = asdict(self)
        d["workdir"] = str(self.workdir)
        d["out_path"] = str(self.out_path)
        return d


def run_pipeline(cfg: Config) -> Path:
    cfg.workdir.mkdir(parents=True, exist_ok=True)
    seg_dir = cfg.workdir / "tts_segments"
    en_srt = cfg.workdir / "subs.src.srt"
    zh_srt = cfg.workdir / "subs.dst.srt"
    dubbed_audio = cfg.workdir / "dubbed.wav"
    meta_file = cfg.workdir / "meta.json"

    t0_total = time.time()
    timings: dict[str, float] = {}

    # 1) Download
    console.rule("[bold cyan]1/5 Download")
    t0 = time.time()
    metadata = download.get_metadata(cfg.url, cfg.proxy, cfg.cookies_browser)
    console.print(f"  Title:    {metadata.get('title')}")
    console.print(f"  Duration: {metadata.get('duration')}")
    console.print(f"  Uploader: {metadata.get('uploader')}")
    video, audio = download.download_video(cfg.url, cfg.workdir, cfg.proxy, cfg.cookies_browser)
    timings["download"] = time.time() - t0
    console.print(f"  ✓ video={video.name}, audio={audio.name}  [{timings['download']:.1f}s]")

    # 2) ASR
    console.rule("[bold cyan]2/5 ASR")
    t0 = time.time()
    if cfg.resume and en_srt.exists():
        segs_src = parse_srt(en_srt)
        console.print(f"  ↺ resume from {en_srt.name} ({len(segs_src)} segments)")
    else:
        with console.status("[bold]Transcribing with Faster-Whisper..."):
            segs_src, asr_meta = asr.transcribe(audio, model_name=cfg.asr_model, language=cfg.lang_from)
        write_srt(segs_src, en_srt)
        console.print(f"  ✓ {len(segs_src)} segments, language={asr_meta['language']} (prob {asr_meta['language_probability']:.2f})")
    timings["asr"] = time.time() - t0
    console.print(f"  [{timings['asr']:.1f}s]")

    # 3) Translate
    console.rule(f"[bold cyan]3/5 Translate ({cfg.translator})")
    t0 = time.time()
    if cfg.resume and zh_srt.exists():
        segs_dst = parse_srt(zh_srt)
        console.print(f"  ↺ resume from {zh_srt.name} ({len(segs_dst)} segments)")
    elif cfg.translator == "none":
        segs_dst = segs_src
        write_srt(segs_dst, zh_srt)
        console.print(f"  · skipped (translator=none)")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as prog:
            task = prog.add_task(f"  Translating", total=len(segs_src))
            fail_count = [0]

            def cb(done, total, fail=0):
                fail_count[0] = fail
                prog.update(task, completed=done, description=f"  Translating (fails={fail})")

            segs_dst = translate.translate_segments(
                segs_src, backend=cfg.translator, src=cfg.lang_from, dst=cfg.lang_to, on_progress=cb
            )
        write_srt(segs_dst, zh_srt)
        console.print(f"  ✓ {len(segs_dst)} segments translated, {fail_count[0]} fallbacks")
    timings["translate"] = time.time() - t0
    console.print(f"  [{timings['translate']:.1f}s]")

    # 4) TTS
    console.rule(f"[bold cyan]4/5 TTS ({cfg.voice})")
    t0 = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("  Synthesizing", total=len(segs_dst))

        def cb(done, total, fail=0):
            prog.update(task, completed=done, description=f"  Synthesizing (fails={fail})")

        results = tts.synth_all(segs_dst, cfg.voice, cfg.rate, seg_dir, cfg.concurrency, on_progress=cb)
    n_ok = sum(1 for v in results.values() if v)
    n_fail = sum(1 for v in results.values() if not v)
    console.print(f"  ✓ {n_ok} segments OK, {n_fail} failed")
    timings["tts"] = time.time() - t0
    console.print(f"  [{timings['tts']:.1f}s]")

    # 5) Mux
    console.rule("[bold cyan]5/5 Assemble + Mux")
    t0 = time.time()
    total_duration = max(s.end for s in segs_dst)
    with console.status("[bold]Assembling dubbed audio track..."):
        mux.assemble_audio(segs_dst, seg_dir, dubbed_audio, total_duration=total_duration)
    console.print(f"  ✓ dubbed audio: {dubbed_audio.name}")
    with console.status("[bold]Muxing video + audio + subtitles..."):
        mux.mux_dubbed(video, dubbed_audio, zh_srt, cfg.out_path, keep_bg_pct=cfg.mix_bg)
    timings["mux"] = time.time() - t0
    console.print(f"  ✓ {cfg.out_path}  [{timings['mux']:.1f}s]")

    # Save meta
    meta_file.write_text(
        json.dumps(
            {**cfg.to_meta(), "timings": timings, "metadata": metadata, "total_seconds": time.time() - t0_total},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    console.rule("[bold green]Done")
    console.print(f"[bold green]Total: {time.time() - t0_total:.1f}s")
    console.print(f"[bold]Output: {cfg.out_path}")
    return cfg.out_path

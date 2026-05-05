"""Translation backends: google / claude / gpt / none."""
from __future__ import annotations

import os
import time
from typing import Iterable

from ..utils import Segment


def translate_segments(
    segs: list[Segment],
    *,
    backend: str,
    src: str,
    dst: str,
    on_progress=None,
) -> list[Segment]:
    if backend == "none":
        return segs
    if backend == "google":
        return _google(segs, src, dst, on_progress)
    if backend == "claude":
        return _claude(segs, src, dst, on_progress)
    if backend == "gpt":
        return _gpt(segs, src, dst, on_progress)
    raise ValueError(f"Unknown translator backend: {backend}")


def _google(segs: list[Segment], src: str, dst: str, on_progress) -> list[Segment]:
    from deep_translator import GoogleTranslator
    from deep_translator.exceptions import TranslationNotFound

    translator = GoogleTranslator(source=src, target=dst)
    out: list[Segment] = []
    fail = 0
    for i, seg in enumerate(segs):
        try:
            zh = translator.translate(seg.text) or seg.text
        except (TranslationNotFound, Exception):
            zh = seg.text
            fail += 1
        out.append(Segment(idx=seg.idx, start=seg.start, end=seg.end, text=zh))
        if on_progress:
            on_progress(i + 1, len(segs), fail=fail)
    return out


def _llm_chunked(
    segs: list[Segment],
    src: str,
    dst: str,
    on_progress,
    *,
    api_call,
    chunk_size: int = 30,
) -> list[Segment]:
    """Translate segments in chunks using a function `api_call(prompt) -> str`."""
    out: list[Segment] = []
    n = len(segs)
    for chunk_start in range(0, n, chunk_size):
        chunk = segs[chunk_start : chunk_start + chunk_size]
        # 构造编号文本 + 让 LLM 返回相同编号的翻译
        body = "\n".join(f"[{s.idx}] {s.text}" for s in chunk)
        prompt = (
            f"You are translating subtitles for a YouTube video from {src} to {dst}.\n"
            "Translate each numbered line. Keep the [N] prefix exactly. Return only the translated lines.\n"
            "Preserve technical terms accurately. Do not add commentary.\n\n"
            f"{body}\n"
        )
        reply = api_call(prompt)
        # 解析 [N] xxx 行
        result: dict[int, str] = {}
        for line in reply.splitlines():
            line = line.strip()
            m = line.find("]")
            if line.startswith("[") and m > 1:
                try:
                    idx = int(line[1:m])
                    result[idx] = line[m + 1 :].strip()
                except ValueError:
                    pass
        for s in chunk:
            translated = result.get(s.idx, s.text)
            out.append(Segment(idx=s.idx, start=s.start, end=s.end, text=translated))
        if on_progress:
            on_progress(min(chunk_start + chunk_size, n), n)
    return out


def _claude(segs: list[Segment], src: str, dst: str, on_progress) -> list[Segment]:
    import anthropic

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY
    model = os.environ.get("YT_DUB_CLAUDE_MODEL", "claude-sonnet-4-6")

    def call(prompt: str) -> str:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if hasattr(b, "text"))

    return _llm_chunked(segs, src, dst, on_progress, api_call=call)


def _gpt(segs: list[Segment], src: str, dst: str, on_progress) -> list[Segment]:
    import openai

    client = openai.OpenAI()  # OPENAI_API_KEY
    model = os.environ.get("YT_DUB_GPT_MODEL", "gpt-4o-mini")

    def call(prompt: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    return _llm_chunked(segs, src, dst, on_progress, api_call=call)

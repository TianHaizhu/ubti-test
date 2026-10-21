from __future__ import annotations
import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable

APP_DIR = Path.home() / ".ai_koubo_agent"
WORK_DIR = APP_DIR / "work"
WORK_DIR.mkdir(parents=True, exist_ok=True)

def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("FFmpeg 组件不可用，请重新安装依赖。") from exc

def download_media(source: str, progress: Callable[[str], None] | None = None) -> Path:
    source = source.strip().strip('"')
    if not source:
        raise ValueError("请先输入本地文件路径或可访问的视频 URL。")
    p = Path(source).expanduser()
    if p.is_file():
        return p.resolve()
    if not re.match(r"^https?://", source, re.I):
        raise FileNotFoundError("找不到本地文件；如果输入网址，请使用 http 或 https 开头的 URL。")
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("缺少 yt-dlp 依赖，请重新运行 setup.bat。") from exc
    target = WORK_DIR / "source.%(ext)s"
    opts = {"outtmpl": str(target), "format": "best[ext=mp4]/best", "noplaylist": True, "quiet": True}
    if progress:
        progress("正在获取视频；部分平台链接可能受登录、地区或平台规则限制。")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([source])
    found = sorted(WORK_DIR.glob("source.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    found = [f for f in found if f.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not found:
        raise RuntimeError("未找到下载后的视频文件。此网址可能无法直接下载，请导入有权使用的本地视频。")
    return found[0]

def transcribe_audio(media_path: str, model_size: str = "base", progress: Callable[[str], None] | None = None) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("缺少 faster-whisper 依赖，请重新运行 setup.bat。首次使用还会下载识别模型。") from exc
    if progress:
        progress("正在识别口播内容；首次运行可能需要下载模型。")
    device = "cuda" if os.environ.get("AI_KOUBO_WHISPER_CUDA") == "1" else "cpu"
    compute = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute)
    segments, _ = model.transcribe(media_path, language="zh", vad_filter=True)
    return "".join(seg.text.strip() + "\n" for seg in segments).strip()

def rewrite_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise ValueError("请先提供需要改写的文案。")
    endpoint = os.environ.get("AI_KOUBO_API_BASE", "").strip().rstrip("/")
    key = os.environ.get("AI_KOUBO_API_KEY", "").strip()
    model = os.environ.get("AI_KOUBO_MODEL", "").strip()
    if not endpoint or not key or not model:
        raise RuntimeError("尚未配置 AI 改写服务。请设置 AI_KOUBO_API_BASE、AI_KOUBO_API_KEY、AI_KOUBO_MODEL；也可以先手动编辑文案。")
    url = endpoint if endpoint.endswith("/chat/completions") else endpoint + "/chat/completions"
    body = {"model": model, "temperature": 0.7, "messages": [
        {"role": "system", "content": "你是中文短视频口播文案编辑。保留事实，不编造数据，不抄袭独特表达。输出自然、口语化、适合朗读的改写稿，只输出正文。"},
        {"role": "user", "content": text}
    ]}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        raise RuntimeError("AI 改写请求失败，请检查 API 地址、模型名称、密钥和网络。详情：" + str(exc)) from exc

def synthesize_speech(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural", progress: Callable[[str], None] | None = None) -> Path:
    if not text.strip():
        raise ValueError("文案为空，无法生成配音。")
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError("缺少 edge-tts 依赖，请重新运行 setup.bat。") from exc
    if progress:
        progress("正在连接在线中文语音服务生成配音。")
    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
    asyncio.run(_run())
    return Path(output_path)

def write_srt(text: str, output_path: str, seconds_per_line: float = 3.2) -> Path:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = [text.strip()] if text.strip() else []
    def stamp(seconds: float) -> str:
        ms = max(0, int(seconds * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, milli = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"
    parts = []
    for i, line in enumerate(lines, 1):
        start = (i - 1) * seconds_per_line
        parts.append(f"{i}\n{stamp(start)} --> {stamp(start + seconds_per_line)}\n{line}\n")
    path = Path(output_path)
    path.write_text("\n".join(parts), encoding="utf-8-sig")
    return path

def render_video(background_path: str, audio_path: str, srt_path: str, output_path: str, progress: Callable[[str], None] | None = None) -> Path:
    bg = Path(background_path)
    audio = Path(audio_path)
    if not bg.is_file() or not audio.is_file():
        raise FileNotFoundError("背景视频或配音文件不存在。")
    ffmpeg = _ffmpeg()
    if progress:
        progress("正在合成 MP4；字幕会作为可开关字幕轨道写入。")
    cmd = [ffmpeg, "-y", "-stream_loop", "-1", "-i", str(bg), "-i", str(audio),
           "-i", str(srt_path), "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text", "-shortest",
           "-movflags", "+faststart", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if result.returncode:
        raise RuntimeError("MP4 合成失败：" + (result.stderr[-1800:] or "FFmpeg 返回错误"))
    return Path(output_path)

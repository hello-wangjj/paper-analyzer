#!/usr/bin/env python3
"""
Podcast Markdown -> Audio Generator (Dual Backend)

支持两种 TTS 后端：
  --backend edge : Microsoft Edge TTS（免费，MP3 输出）
  --backend mimo : MiMo V2.5 TTS（自然有感情，WAV 输出，需要 MIMO_API_KEY）

Usage:
    # edge-tts（默认，免费无需 key）
    python generate_audio.py <input.md> <output.mp3> --backend edge

    # MiMo TTS（需要 API key）
    export MIMO_API_KEY="your-key"
    python generate_audio.py <input.md> <output.wav> --backend mimo

    # 可选参数
    --male-voice / --female-voice   自定义音色
    --male-name / --female-name     指定脚本中男女角色名字
    --no-tags                       禁用自动音频标签（MiMo only）
"""

import argparse
import base64
import os
import re
import struct
import sys
import time
import wave
from abc import ABC, abstractmethod
from pathlib import Path


# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ══════════════════════════════════════════════════════════
# 共享工具函数
# ══════════════════════════════════════════════════════════

def parse_dialogue(md_text: str, male_name: str = None, female_name: str = None) -> list[dict]:
    """
    从播客 Markdown 解析对话列表。

    每条: {"speaker": "名字", "text": "文本"}
    特殊: {"speaker": "pause", "text": ""} 表示段落停顿

    支持格式: **Name**：text 或 **Name**: text
    """
    lines = md_text.split("\n")
    dialogue = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith(">") or stripped.startswith("---") or stripped.startswith("|"):
            continue
        if stripped.startswith("🎵"):
            dialogue.append({"speaker": "pause", "text": ""})
            continue

        # Match **Name**：text
        m = re.match(r"^\*\*(.+?)\*\*[：:]\s*(.+)$", stripped)
        if m:
            speaker = m.group(1)
            text = m.group(2).strip()

            # 清理 Markdown 格式
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
            text = re.sub(r"\*(.+?)\*", r"\1", text)         # italic
            text = re.sub(r"`(.+?)`", r"\1", text)            # inline code
            text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)   # links
            text = text.replace("——", "，")
            text = text.replace("—", "，")

            if text.strip():
                dialogue.append({"speaker": speaker, "text": text.strip()})

    return dialogue


def pick_voice(speaker: str, male_name: str, female_name: str,
               male_voice: str, female_voice: str) -> str:
    """根据说话者名字选择声音。"""
    if male_name and speaker == male_name:
        return male_voice
    if female_name and speaker == female_name:
        return female_voice
    # 启发式：名字包含常见女性字 → 女声
    female_hints = ["雪", "花", "美", "丽", "晓", "红", "姐", "妹", "she", "her"]
    if any(h in speaker for h in female_hints):
        return female_voice
    return male_voice


def is_female_speaker(speaker: str, male_name: str, female_name: str) -> bool:
    """判断说话者是否为女性角色。"""
    if female_name and speaker == female_name:
        return True
    if male_name and speaker == male_name:
        return False
    female_hints = ["雪", "花", "美", "丽", "晓", "红", "姐", "妹"]
    return any(h in speaker for h in female_hints)


# ══════════════════════════════════════════════════════════
# MiMo 风格控制（仅 MiMo 后端使用）
# ══════════════════════════════════════════════════════════

MIMO_MALE_STYLE_TEMPLATE = (
    "你是一位技术扎实的男性工程师，正在和朋友讲解{topic}。"
    "语速适中偏慢，声音沉稳有力，讲解清晰有条理，善用类比。"
    "偶尔带着自信和热情，像在分享自己热爱的知识。"
    "自然对话，不要像念稿子。"
)

MIMO_FEMALE_STYLE_TEMPLATE = (
    "你是一位活泼好学的女性新人，正在向工程师朋友请教{topic}。"
    "语速稍快，声音清亮有活力，充满好奇心。"
    "提问时带着思考，理解时表达惊喜和恍然大悟。"
    "自然亲切，像在和朋友聊天，偶尔用'嗯''哦''对'等语气词。"
)

TAG_PATTERNS = [
    (r"[！!]{2,}|太.{0,4}了|好棒|好嘞|完美|满分", "(兴奋)"),
    (r"等等|等等我|我有个疑问|能再说一遍吗|等一下", "(疑惑)"),
    (r"哦！|原来如此|恍然大悟|明白了|完全正确|精辟|对！", "(恍然大悟)"),
    (r"哈哈|笑", "(轻笑)"),
    (r"这就有意思了|有意思|有趣", "(若有所思)"),
    (r"不对|等等，这不是|这里面有问题", "(质疑)"),
]


def add_audio_tags(text: str) -> str:
    """根据文本内容自动添加 MiMo 音频标签。"""
    for pattern, tag in TAG_PATTERNS:
        if re.search(pattern, text):
            return f"{tag}{text}"
    return text


# ══════════════════════════════════════════════════════════
# TTS 引擎抽象基类
# ══════════════════════════════════════════════════════════

class TTSEngine(ABC):
    """TTS 后端抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称。"""

    @property
    @abstractmethod
    def default_male_voice(self) -> str:
        """默认男声。"""

    @property
    @abstractmethod
    def default_female_voice(self) -> str:
        """默认女声。"""

    @abstractmethod
    def generate_segment(self, text: str, voice: str, output_path: str,
                         speaker: str = "", male_name: str = "",
                         female_name: str = "", use_tags: bool = True) -> bool:
        """生成单个音频片段。"""

    @abstractmethod
    def concatenate(self, segment_files: list, output_path: str) -> None:
        """拼接所有音频片段。"""

    @abstractmethod
    def rate_limit_delay(self) -> float:
        """每次请求后的限流延迟（秒）。"""


# ══════════════════════════════════════════════════════════
# Edge TTS 引擎
# ══════════════════════════════════════════════════════════

class EdgeTTSEngine(TTSEngine):
    """Microsoft Edge TTS 后端（免费，MP3 输出）。"""

    def __init__(self):
        try:
            import edge_tts  # noqa: F401
            self._edge_tts = edge_tts
        except ImportError:
            print("错误: edge-tts 未安装。请运行: uv add edge-tts")
            sys.exit(1)

    @property
    def name(self) -> str:
        return "Edge TTS"

    @property
    def default_male_voice(self) -> str:
        return "zh-CN-YunjianNeural"

    @property
    def default_female_voice(self) -> str:
        return "zh-CN-XiaoxiaoNeural"

    def rate_limit_delay(self) -> float:
        return 0.3

    def generate_segment(self, text: str, voice: str, output_path: str,
                         speaker: str = "", male_name: str = "",
                         female_name: str = "", use_tags: bool = True) -> bool:
        text = text[:2000]
        for attempt in range(3):
            try:
                communicate = self._edge_tts.Communicate(text, voice)
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(communicate.save(output_path))
                loop.close()
                return True
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    print(f"    重试 ({attempt+1}/3)，等待 {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"    失败: {e}")
                    return False

    def concatenate(self, segment_files: list, output_path: str) -> None:
        """二进制拼接 MP3 文件。"""
        # MP3 静音帧（~0.5s）
        silence_frame = bytes([
            0xFF, 0xFB, 0x90, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ])

        with open(output_path, "wb") as outf:
            for item in segment_files:
                if item["type"] == "pause":
                    for _ in range(20):
                        outf.write(silence_frame)
                    continue
                fpath = item.get("path")
                if fpath and Path(fpath).exists():
                    with open(fpath, "rb") as f:
                        outf.write(f.read())


# ══════════════════════════════════════════════════════════
# MiMo TTS 引擎
# ══════════════════════════════════════════════════════════

class MimoTTSEngine(TTSEngine):
    """MiMo V2.5 TTS 后端（自然有感情，WAV 输出）。需要 MIMO_API_KEY。"""

    def __init__(self, topic: str = "技术知识"):
        api_key = os.environ.get("MIMO_API_KEY", "").strip()
        if not api_key:
            print("错误: MIMO_API_KEY 环境变量未设置！")
            print("  PowerShell: $env:MIMO_API_KEY=\"your-key\"")
            print("  Bash:       export MIMO_API_KEY=\"your-key\"")
            sys.exit(1)
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key, base_url="https://api.xiaomimimo.com/v1")
        except ImportError:
            print("错误: openai 未安装。请运行: uv add openai")
            sys.exit(1)
        self._male_style = MIMO_MALE_STYLE_TEMPLATE.format(topic=topic)
        self._female_style = MIMO_FEMALE_STYLE_TEMPLATE.format(topic=topic)

    @property
    def name(self) -> str:
        return "MiMo TTS"

    @property
    def default_male_voice(self) -> str:
        return "白桦"

    @property
    def default_female_voice(self) -> str:
        return "冰糖"

    def rate_limit_delay(self) -> float:
        return 0.5

    def generate_segment(self, text: str, voice: str, output_path: str,
                         speaker: str = "", male_name: str = "",
                         female_name: str = "", use_tags: bool = True) -> bool:
        text = text[:2000]

        # 选择风格指令
        if is_female_speaker(speaker, male_name, female_name):
            style = self._female_style
        else:
            style = self._male_style

        # 添加音频标签
        tagged_text = add_audio_tags(text) if use_tags else text

        for attempt in range(3):
            try:
                completion = self._client.chat.completions.create(
                    model="mimo-v2.5-tts",
                    messages=[
                        {"role": "user", "content": style},
                        {"role": "assistant", "content": tagged_text}
                    ],
                    audio={"format": "wav", "voice": voice}
                )
                audio_bytes = base64.b64decode(completion.choices[0].message.audio.data)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                return True
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 5
                    print(f"    重试 ({attempt+1}/3)，等待 {wait}s... 原因: {e}")
                    time.sleep(wait)
                else:
                    print(f"    失败: {e}")
                    return False

    def concatenate(self, segment_files: list, output_path: str) -> None:
        """用 wave 模块拼接 WAV 文件。"""
        # 找到第一个 WAV 文件获取参数
        params = None
        for item in segment_files:
            if item["type"] == "audio" and item.get("path"):
                try:
                    with wave.open(str(item["path"]), 'r') as wf:
                        params = wf.getparams()
                    break
                except Exception:
                    continue

        if params is None:
            # 没有有效音频，生成空文件
            print("    警告: 没有有效音频片段")
            return

        with wave.open(output_path, 'w') as outf:
            outf.setparams(params)
            for item in segment_files:
                if item["type"] == "pause":
                    # 0.8 秒静音
                    n_samples = int(params.framerate * 0.8)
                    silence = struct.pack('<' + 'h' * n_samples, *([0] * n_samples))
                    outf.writeframes(silence)
                    continue
                fpath = item.get("path")
                if fpath and Path(fpath).exists():
                    try:
                        with wave.open(str(fpath), 'r') as wf:
                            if (wf.getnchannels() == params.nchannels and
                                wf.getsampwidth() == params.sampwidth and
                                wf.getframerate() == params.framerate):
                                outf.writeframes(wf.readframes(wf.getnframes()))
                            else:
                                print(f"    警告: 跳过格式不一致的文件 {fpath}")
                    except Exception as e:
                        print(f"    警告: 跳过损坏的文件 {fpath}: {e}")


# ══════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="播客音频生成器 — 支持 Edge TTS 和 MiMo TTS 双后端"
    )
    parser.add_argument("input", help="输入播客 Markdown 文件")
    parser.add_argument("output", help="输出音频文件（edge→MP3, mimo→WAV）")
    parser.add_argument("--backend", choices=["edge", "mimo"], default="edge",
                        help="TTS 后端（默认: edge）")
    parser.add_argument("--male-voice", default=None, help="男声 TTS 音色名")
    parser.add_argument("--female-voice", default=None, help="女声 TTS 音色名")
    parser.add_argument("--male-name", default=None, help="脚本中男性角色名字")
    parser.add_argument("--female-name", default=None, help="脚本中女性角色名字")
    parser.add_argument("--no-tags", action="store_true", help="禁用自动音频标签（MiMo only）")
    parser.add_argument("--topic", default="技术知识", help="文档主题，用于调整 MiMo 风格 prompt（默认: 技术知识）")

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"错误: 找不到输入文件: {args.input}")
        sys.exit(1)

    # ── 初始化引擎 ──
    if args.backend == "edge":
        engine = EdgeTTSEngine()
    else:
        engine = MimoTTSEngine(topic=args.topic)

    # 应用默认音色
    male_voice = args.male_voice or engine.default_male_voice
    female_voice = args.female_voice or engine.default_female_voice

    # ── 解析 Markdown ──
    md_text = Path(args.input).read_text(encoding="utf-8")
    dialogue = parse_dialogue(md_text, args.male_name, args.female_name)

    segments = [d for d in dialogue if d["speaker"] != "pause"]
    speakers = sorted(set(d["speaker"] for d in segments))
    print(f"引擎: {engine.name}")
    print(f"解析: {len(segments)} 个对话片段")
    print(f"角色: {', '.join(speakers)}")
    print(f"男声: {male_voice}，女声: {female_voice}")
    print()

    # ── 临时目录 ──
    tmp_dir = Path(args.output).parent / "_podcast_tmp"
    tmp_dir.mkdir(exist_ok=True)

    # ── 逐段生成 ──
    print(f"开始生成音频 ({engine.name})...")
    segment_files = []  # 按顺序: {"type": "audio"|"pause", "path": ...}
    success = 0
    fail = 0
    total = len(segments)

    for i, item in enumerate(dialogue):
        if item["speaker"] == "pause":
            segment_files.append({"type": "pause"})
            continue

        voice = pick_voice(item["speaker"], args.male_name, args.female_name,
                          male_voice, female_voice)
        fname = tmp_dir / f"seg_{i:04d}_{item['speaker']}.mp3" if args.backend == "edge" \
                else tmp_dir / f"seg_{i:04d}_{item['speaker']}.wav"

        count = success + fail + 1
        pct = count / total * 100
        print(f"  [{count}/{total} {pct:.0f}%] {item['speaker']}: {item['text'][:50]}...")

        ok = engine.generate_segment(
            item["text"], voice, str(fname),
            speaker=item["speaker"],
            male_name=args.male_name or "",
            female_name=args.female_name or "",
            use_tags=not args.no_tags
        )

        if ok:
            segment_files.append({"type": "audio", "path": fname})
            success += 1
        else:
            fail += 1

        time.sleep(engine.rate_limit_delay())

    print(f"\n生成完毕: {success} 成功, {fail} 失败")

    # ── 拼接 ──
    print("\n拼接音频片段...")
    engine.concatenate(segment_files, args.output)

    size_mb = os.path.getsize(args.output) / 1024 / 1024
    print(f"\n输出: {args.output}")
    print(f"大小: {size_mb:.1f} MB")

    # ── 清理 ──
    print("\n清理临时文件...")
    for item in segment_files:
        fpath = item.get("path")
        if fpath and Path(fpath).exists():
            Path(fpath).unlink()
    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    print("\n完成!")


if __name__ == "__main__":
    main()

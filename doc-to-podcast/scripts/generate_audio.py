#!/usr/bin/env python3
"""
Podcast Markdown -> Audio Generator
Uses edge-tts (free Microsoft Edge TTS) to generate dual-voice podcast audio.

Usage:
    python generate_audio.py <input_podcast.md> <output.mp3> [--male-voice VOICE] [--female-voice VOICE]

Defaults:
    Male:   zh-CN-YunjianNeural (云健)
    Female: zh-CN-XiaoxiaoNeural (晓晓)
"""

import asyncio
import argparse
import re
import os
import sys
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("Error: edge-tts not installed. Run: uv add edge-tts  or  pip install edge-tts")
    sys.exit(1)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_MALE_VOICE = "zh-CN-YunjianNeural"
DEFAULT_FEMALE_VOICE = "zh-CN-XiaoxiaoNeural"
# If the podcast uses different speaker names, map them here
SPEAKER_GENDER_MAP = {}  # e.g. {"Tom": "male", "Jerry": "female"}


def parse_dialogue(md_text: str, male_name: str = None, female_name: str = None) -> list[dict]:
    """
    Parse podcast Markdown into a list of dialogue segments.

    Each item: {"speaker": "<name>", "text": "<text>"}
    Special: {"speaker": "pause"} for section breaks

    Supports format: **Name**：text  or  **Name**: text
    """
    lines = md_text.split("\n")
    dialogue = []
    in_code_block = False

    # Auto-detect speaker names from first few dialogue lines if not provided
    speakers = set()
    for line in lines[:50]:
        m = re.match(r"^\*\*(.+?)\*\*[：:]", line.strip())
        if m:
            speakers.add(m.group(1))
            if len(speakers) >= 2:
                break

    speaker_list = sorted(speakers)
    if len(speaker_list) >= 2 and not male_name and not female_name:
        # Heuristic: first detected speaker = male, second = female
        # User can override via --male-name / --female-name
        pass

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped:
            continue

        # Skip non-dialogue lines
        if stripped.startswith("#") or stripped.startswith(">") or stripped.startswith("---") or stripped.startswith("|"):
            continue

        # Section breaks (music notes, dividers)
        if stripped.startswith("🎵") or stripped == "---":
            dialogue.append({"speaker": "pause", "text": ""})
            continue

        # Match **Name**：text
        m = re.match(r"^\*\*(.+?)\*\*[：:]\s*(.+)$", stripped)
        if m:
            speaker = m.group(1)
            text = m.group(2).strip()

            # Clean Markdown formatting for TTS readability
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
    """Determine which voice to use for a given speaker name."""
    # Check explicit mapping first
    if speaker in SPEAKER_GENDER_MAP:
        return male_voice if SPEAKER_GENDER_MAP[speaker] == "male" else female_voice
    # Check explicit names
    if male_name and speaker == male_name:
        return male_voice
    if female_name and speaker == female_name:
        return female_voice
    # Default heuristic: if name contains common female characters
    female_hints = ["雪", "花", "美", "丽", "晓", "红", "姐", "妹", "she", "her",
                    "Alice", "Bob", "女"]
    if any(h in speaker for h in female_hints):
        return female_voice
    return male_voice


async def generate_segment(text: str, voice: str, output_path: str, max_retries: int = 3) -> bool:
    """Generate a single audio segment with retry logic."""
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 3
                print(f"    Retry ({attempt+1}/{max_retries}), waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"    FAILED: {e}")
                return False


async def generate_all(dialogue: list[dict], output_mp3: str,
                       male_name: str, female_name: str,
                       male_voice: str, female_voice: str):
    """Generate all audio segments and concatenate into final MP3."""

    segments = [(i, d) for i, d in enumerate(dialogue)
                if d["speaker"] != "pause" and d.get("text", "").strip()]
    total = len(segments)
    print(f"\nGenerating {total} audio segments...")
    print(f"  Male voice: {male_voice}")
    print(f"  Female voice: {female_voice}")

    tmp_dir = Path(output_mp3).parent / "_podcast_tmp"
    tmp_dir.mkdir(exist_ok=True)
    segment_files = {}  # index -> filepath
    success = 0
    fail = 0

    for count, (i, item) in enumerate(segments, 1):
        voice = pick_voice(item["speaker"], male_name, female_name, male_voice, female_voice)
        fname = tmp_dir / f"seg_{i:04d}_{item['speaker']}.mp3"

        # Truncate very long text (edge-tts limit ~5000 chars)
        text = item["text"][:2000]

        print(f"  [{count}/{total}] {item['speaker']}: {text[:50]}...")

        ok = await generate_segment(text, voice, str(fname))
        if ok:
            segment_files[i] = fname
            success += 1
        else:
            fail += 1

        # Rate limit: avoid 503 from server
        await asyncio.sleep(0.3)

    print(f"\nGeneration complete: {success} success, {fail} failed")

    # Concatenate
    print("\nConcatenating segments...")
    with open(output_mp3, "wb") as outf:
        for i, item in enumerate(dialogue):
            if item["speaker"] == "pause":
                # Write silence gap (~0.5s)
                silence_frame = bytes([
                    0xFF, 0xFB, 0x90, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                ])
                for _ in range(20):  # ~0.5s silence
                    outf.write(silence_frame)
                continue

            if i in segment_files:
                fname = segment_files[i]
                if fname.exists():
                    with open(fname, "rb") as f:
                        outf.write(f.read())

    size_mb = os.path.getsize(output_mp3) / 1024 / 1024
    print(f"\nOutput: {output_mp3}")
    print(f"Size:   {size_mb:.1f} MB")

    # Cleanup temp files
    print("\nCleaning up temp files...")
    for fname in segment_files.values():
        if fname.exists():
            fname.unlink()
    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    print("\nDone!")
    return success, fail


def main():
    parser = argparse.ArgumentParser(description="Generate podcast audio from Markdown dialogue script")
    parser.add_argument("input", help="Input podcast Markdown file")
    parser.add_argument("output", help="Output MP3 file path")
    parser.add_argument("--male-voice", default=DEFAULT_MALE_VOICE, help="Male TTS voice name")
    parser.add_argument("--female-voice", default=DEFAULT_FEMALE_VOICE, help="Female TTS voice name")
    parser.add_argument("--male-name", default=None, help="Male speaker name in the script")
    parser.add_argument("--female-name", default=None, help="Female speaker name in the script")

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    md_text = Path(args.input).read_text(encoding="utf-8")
    dialogue = parse_dialogue(md_text, args.male_name, args.female_name)

    segments = [d for d in dialogue if d["speaker"] != "pause"]
    speakers = sorted(set(d["speaker"] for d in segments))
    print(f"Parsed: {len(segments)} dialogue segments")
    print(f"Speakers detected: {', '.join(speakers)}")

    asyncio.run(generate_all(
        dialogue, args.output,
        args.male_name, args.female_name,
        args.male_voice, args.female_voice
    ))


if __name__ == "__main__":
    main()

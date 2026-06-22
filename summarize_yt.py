#!/usr/bin/env python3
"""YouTube video summarizer — fetches transcript, cleans it, sends to Claude Code CLI."""

import sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")
import os
import re
import glob
import shutil
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs, urlencode


def clean_youtube_url(url):
    """Strip playlist/radio params, keep only the video ID."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if "v" in params:
        clean_query = urlencode({"v": params["v"][0]})
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{clean_query}"
    return url


def get_video_title(url):
    result = subprocess.run(
        ["yt-dlp", "--print", "title", "--skip-download", "--no-warnings", url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def list_available_subs(url):
    """Query yt-dlp for available subs without downloading anything. Returns (manual, auto) lang sets."""
    result = subprocess.run(
        ["yt-dlp", "--list-subs", "--skip-download", "--no-warnings", url],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr

    manual_langs = set()
    auto_langs = set()
    section = None

    for line in output.splitlines():
        if "Available subtitles" in line:
            section = "manual"
            continue
        if "Available automatic captions" in line:
            section = "auto"
            continue
        if section and line and not line.startswith("Language") and not line.startswith("-"):
            lang_code = line.split()[0] if line.split() else ""
            if lang_code:
                if section == "manual":
                    manual_langs.add(lang_code)
                else:
                    auto_langs.add(lang_code)

    return manual_langs, auto_langs


def download_subtitles(url, temp_dir):
    """List available subs first, then download the best match."""
    import time

    preferred = ["en", "uk", "ru", "en-orig", "uk-orig", "ru-orig"]

    print("  Checking available subtitles...")
    manual_langs, auto_langs = list_available_subs(url)

    # Build ordered list of (flag, lang) to try
    candidates = []
    for lang in preferred:
        if lang in manual_langs:
            candidates.append(("--write-sub", lang))
        if lang in auto_langs:
            candidates.append(("--write-auto-sub", lang))

    if not candidates:
        return None

    for flag, lang in candidates:
        print(f"  Downloading {lang} subtitles...")
        result = subprocess.run(
            [
                "yt-dlp", flag,
                "--sub-lang", lang,
                "--skip-download",
                "--sub-format", "vtt",
                "--no-warnings",
                "-o", os.path.join(temp_dir, "subs"),
                url,
            ],
            capture_output=True, text=True,
        )

        vtt_files = glob.glob(os.path.join(temp_dir, "*.vtt"))
        if vtt_files:
            return vtt_files[0]

        # Rate-limited — wait before trying next language
        if "429" in (result.stderr + result.stdout):
            print("  Rate-limited, waiting 5s before next attempt...")
            time.sleep(5)

    return None


def clean_vtt(vtt_text):
    """Strip VTT metadata, timestamps, tags, and deduplicate sliding-window captions."""
    lines = vtt_text.splitlines()

    # Skip WEBVTT header block (everything before first blank line after header)
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("WEBVTT"):
            start = i + 1
            continue
        if start > 0 and line.strip() == "":
            start = i + 1
            break

    timestamp_re = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
    tag_re = re.compile(r"<[^>]+>")
    position_re = re.compile(r"(align|position|size|line|vertical)\s*:\s*\S+")

    text_lines = []
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        if timestamp_re.match(line):
            continue
        # Skip cue identifiers (numeric or contain -->)
        if line.isdigit():
            continue
        # Remove positioning metadata that sometimes appears on its own line
        cleaned = position_re.sub("", line).strip()
        if not cleaned:
            continue
        # Strip HTML/VTT tags
        cleaned = tag_re.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            text_lines.append(cleaned)

    # Sliding-window deduplication:
    # Auto-subs show 2 lines at a time, advancing by 1 line each cue.
    # Result: every line appears twice (or more). Also, a later line may
    # be a superset of an earlier line (same start, more words appended).
    deduped = []
    for line in text_lines:
        if not deduped:
            deduped.append(line)
            continue
        prev = deduped[-1]
        # Exact duplicate
        if line == prev:
            continue
        # Current line is a longer version of previous (sliding window append)
        if line.startswith(prev):
            deduped[-1] = line
            continue
        # Previous line is a longer version of current (shouldn't happen often, but guard)
        if prev.startswith(line):
            continue
        deduped.append(line)

    # Second pass: remove lines that are fully contained as a suffix of the previous line
    # (handles the reverse sliding-window overlap)
    final = []
    for line in deduped:
        if final and final[-1].endswith(line):
            continue
        if final and line.endswith(final[-1]):
            final[-1] = line
            continue
        final.append(line)

    text = " ".join(final)
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def sanitize_filename(name, max_length=100):
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    sanitized = sanitized.strip(". ")
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip(". ")
    return sanitized


def send_to_claude(video_title, transcript):
    prompt = (
        f'Here is a transcript of a YouTube video titled "{video_title}".\n\n'
        "The transcript may be in English, Ukrainian, or Russian. "
        "Regardless of the original language, always write the summary in English.\n\n"
        "Give key most important points as bullet list that conveys most important "
        "information. Short sentences.\n\n"
        "---\n"
        f"{transcript}"
    )

    # Write prompt to a temp file to avoid CLI length limits and encoding issues
    prompt_file = os.path.join(tempfile.gettempdir(), "ytsum_prompt.txt")
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        env = {**os.environ, "PYTHONUTF8": "1"}
        result = subprocess.run(
            ["claude", "-p"],
            stdin=open(prompt_file, "r", encoding="utf-8"),
            capture_output=True, text=True,
            encoding="utf-8",
            env=env,
        )
        if result.returncode != 0:
            print(f"Error: Claude CLI failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

        return result.stdout.strip()
    finally:
        if os.path.exists(prompt_file):
            os.unlink(prompt_file)


def copy_to_clipboard(text):
    try:
        import platform
        cmd = ["pbcopy"] if platform.system() == "Darwin" else ["clip"]
        subprocess.run(cmd, input=text, text=True, check=True)
    except Exception:
        pass  # Non-critical


def save_summary(video_title, summary):
    output_dir = Path.home() / "Documents" / "yt-summaries"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(video_title) + ".md"
    filepath = output_dir / filename

    filepath.write_text(
        f"# {video_title}\n\n{summary}\n",
        encoding="utf-8",
    )
    return filepath


def check_prerequisites():
    if shutil.which("yt-dlp") is None:
        print("Error: yt-dlp not found. Install it: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)
    if shutil.which("claude") is None:
        print(
            "Error: Claude Code CLI not found.\n"
            "Install it and log in with your Pro/Max subscription.",
            file=sys.stderr,
        )
        sys.exit(1)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python summarize_yt.py <youtube_url>", file=sys.stderr)
        sys.exit(1)

    url = unquote(sys.argv[1].strip())
    # Strip trailing slashes/whitespace that protocol handlers sometimes add
    url = url.rstrip("/")
    url = clean_youtube_url(url)

    check_prerequisites()

    print(f"Fetching video info...")
    video_title = get_video_title(url)
    if not video_title:
        video_title = "Unknown Video"
    print(f"Title: {video_title}")

    temp_dir = tempfile.mkdtemp(prefix="ytsum_")
    try:
        print("Downloading subtitles...")
        vtt_path = download_subtitles(url, temp_dir)
        if not vtt_path:
            print("Error: No subtitles found for this video (tried English, Ukrainian, Russian).", file=sys.stderr)
            sys.exit(1)

        print("Cleaning transcript...")
        vtt_text = Path(vtt_path).read_text(encoding="utf-8")
        transcript = clean_vtt(vtt_text)

        raw_size = len(vtt_text)
        clean_size = len(transcript)
        ratio = (1 - clean_size / raw_size) * 100 if raw_size else 0
        print(f"Transcript: {raw_size:,} chars raw -> {clean_size:,} chars clean ({ratio:.0f}% reduction)")

        print("Sending to Claude...")
        summary = send_to_claude(video_title, transcript)

        print("\n" + "=" * 60)
        print(summary)
        print("=" * 60 + "\n")

        copy_to_clipboard(summary)
        filepath = save_summary(video_title, summary)
        print(f"[OK] Summary saved to {filepath} and copied to clipboard")

        os.startfile(filepath)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

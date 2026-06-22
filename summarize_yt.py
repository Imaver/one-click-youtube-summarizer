#!/usr/bin/env python3
"""YouTube video summarizer — fetches transcript, cleans it, sends to Claude Code CLI."""

import sys
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
sys.stderr.reconfigure(encoding="utf-8")
import os
import re
import glob
import logging
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs, urlencode

log = logging.getLogger("ytsum")


def setup_logging(log_path):
    """Log to both console and file."""
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(ch)


def get_output_dir(video_title):
    """Create per-video folder inside ~/Documents/yt-summaries/."""
    base = Path.home() / "Documents" / "yt-summaries"
    folder_name = sanitize_filename(video_title)
    video_dir = base / folder_name
    video_dir.mkdir(parents=True, exist_ok=True)
    return video_dir


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
    log.debug("yt-dlp --list-subs output:\n%s", output)

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

    log.info("  Checking available subtitles...")
    manual_langs, auto_langs = list_available_subs(url)

    matched_manual = [l for l in preferred if l in manual_langs]
    matched_auto = [l for l in preferred if l in auto_langs]

    if matched_manual:
        log.info("  Manual subs available: %s", ", ".join(matched_manual))
    if matched_auto:
        log.info("  Auto-generated subs available: %s", ", ".join(matched_auto))
    if not matched_manual and not matched_auto:
        log.info("  No matching subtitles found (checked: %s)", ", ".join(preferred))
        return None

    # Build ordered list of (flag, lang) to try
    candidates = []
    for lang in preferred:
        if lang in manual_langs:
            candidates.append(("--write-sub", lang, "manual"))
        if lang in auto_langs:
            candidates.append(("--write-auto-sub", lang, "auto"))

    for i, (flag, lang, sub_type) in enumerate(candidates):
        log.info("  [%d/%d] Downloading %s (%s)...", i + 1, len(candidates), lang, sub_type)
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

        log.debug("yt-dlp stdout: %s", result.stdout.strip())
        log.debug("yt-dlp stderr: %s", result.stderr.strip())

        vtt_files = glob.glob(os.path.join(temp_dir, "*.vtt"))
        if vtt_files:
            log.info("  Got %s subtitles", lang)
            return vtt_files[0]

        error_output = (result.stderr + result.stdout).strip()
        if "429" in error_output:
            log.info("  Failed: YouTube rate limit (HTTP 429). Waiting 5s...")
            time.sleep(5)
        elif error_output:
            last_line = [l for l in error_output.splitlines() if l.strip()][-1]
            log.info("  Failed: %s", last_line)
        else:
            log.info("  Failed: no subtitle file written (unknown reason)")

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
        if line.isdigit():
            continue
        cleaned = position_re.sub("", line).strip()
        if not cleaned:
            continue
        cleaned = tag_re.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            text_lines.append(cleaned)

    deduped = []
    for line in text_lines:
        if not deduped:
            deduped.append(line)
            continue
        prev = deduped[-1]
        if line == prev:
            continue
        if line.startswith(prev):
            deduped[-1] = line
            continue
        if prev.startswith(line):
            continue
        deduped.append(line)

    final = []
    for line in deduped:
        if final and final[-1].endswith(line):
            continue
        if final and line.endswith(final[-1]):
            final[-1] = line
            continue
        final.append(line)

    text = " ".join(final)
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

    prompt_file = os.path.join(tempfile.gettempdir(), "ytsum_prompt.txt")
    try:
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        log.debug("Prompt written to %s (%d chars)", prompt_file, len(prompt))

        env = {**os.environ, "PYTHONUTF8": "1"}
        result = subprocess.run(
            ["claude", "-p"],
            stdin=open(prompt_file, "r", encoding="utf-8"),
            capture_output=True, text=True,
            encoding="utf-8",
            env=env,
        )
        if result.returncode != 0:
            log.error("Claude CLI failed (exit %d):\n%s", result.returncode, result.stderr)
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
        pass


def check_prerequisites():
    if shutil.which("yt-dlp") is None:
        log.error("yt-dlp not found. Install it: pip install yt-dlp")
        sys.exit(1)
    if shutil.which("claude") is None:
        log.error("Claude Code CLI not found. Install it and log in with your Pro/Max subscription.")
        sys.exit(1)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python summarize_yt.py <youtube_url>", file=sys.stderr)
        sys.exit(1)

    url = unquote(sys.argv[1].strip())
    url = url.rstrip("/")
    url = clean_youtube_url(url)

    check_prerequisites()

    log.info("URL: %s", url)
    log.info("Fetching video info...")
    video_title = get_video_title(url)
    if not video_title:
        video_title = "Unknown Video"
    log.info("Title: %s", video_title)

    # Set up per-video output folder and log file
    video_dir = get_output_dir(video_title)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = video_dir / f"log_{timestamp}.txt"
    setup_logging(log_path)
    log.debug("Video URL: %s", url)
    log.debug("Video title: %s", video_title)
    log.debug("Output folder: %s", video_dir)

    temp_dir = tempfile.mkdtemp(prefix="ytsum_")
    try:
        log.info("Downloading subtitles...")
        vtt_path = download_subtitles(url, temp_dir)
        if not vtt_path:
            log.error("No subtitles found for this video (tried English, Ukrainian, Russian).")
            sys.exit(1)

        log.info("Cleaning transcript...")
        vtt_text = Path(vtt_path).read_text(encoding="utf-8")
        transcript = clean_vtt(vtt_text)

        raw_size = len(vtt_text)
        clean_size = len(transcript)
        ratio = (1 - clean_size / raw_size) * 100 if raw_size else 0
        log.info("Transcript: %s chars raw -> %s chars clean (%d%% reduction)",
                 f"{raw_size:,}", f"{clean_size:,}", ratio)

        log.info("Sending to Claude (%s chars)... this may take a moment", f"{clean_size:,}")
        summary = send_to_claude(video_title, transcript)

        log.info("\n" + "=" * 60)
        log.info(summary)
        log.info("=" * 60)

        copy_to_clipboard(summary)

        # Save summary .md inside the video folder
        md_path = video_dir / "summary.md"
        md_path.write_text(f"# {video_title}\n\n{summary}\n", encoding="utf-8")
        log.info("[OK] Summary saved to %s and copied to clipboard", md_path)
        log.info("Log file: %s", log_path)

        os.startfile(md_path)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

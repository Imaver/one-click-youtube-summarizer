# YouTube Video Summarizer

One-click button on any YouTube video page that fetches the transcript, cleans it, and sends it to Claude Code CLI for a bullet-point summary.

Works with English, Ukrainian, and Russian videos. Summaries are always in English.

---

## What it does

1. You click **Summarize** on a YouTube video
2. A terminal window opens
3. It downloads the subtitles, cleans them up, and sends them to Claude
4. You get a bullet-point summary printed in the terminal, copied to your clipboard, and saved as a `.md` file

---

## Installation (Windows 11)

### Step 1: Install Python

Download and install Python 3.10+ from https://www.python.org/downloads/

During installation, **check "Add Python to PATH"**.

Verify it works:

```
python --version
```

### Step 2: Install yt-dlp

Open a terminal (PowerShell or Command Prompt) and run:

```
pip install yt-dlp
```

Verify:

```
yt-dlp --version
```

### Step 3: Install Claude Code CLI

Follow the official instructions at https://docs.anthropic.com/en/docs/claude-code/overview

After installing, run `claude` once in a terminal to log in with your Anthropic account (Pro or Max subscription required).

Verify the non-interactive mode works:

```
claude -p "say hello"
```

This should print a response and exit. If it hangs or errors, you may need to complete the login flow first by running `claude` interactively.

**Important:** If you have an `ANTHROPIC_API_KEY` environment variable set, Claude Code will use API tokens instead of your subscription. Remove it if you want to use subscription credits.

### Step 4: Download this project

Clone or download this project to a permanent folder. Example:

```
git clone <repo-url> D:\Projects\one-click-youtube-summarizer
```

Or download the ZIP and extract it. The folder can be anywhere, but **don't move it after setup** (the protocol handler points to the absolute path).

### Step 5: Register the protocol handler

Open a terminal in the project folder and run:

```
cd D:\Projects\one-click-youtube-summarizer
python setup.py
```

This registers the `ytsum://` custom protocol in your Windows registry (user-level, no admin needed). You should see:

```
ytsum:// protocol handler installed successfully.
```

### Step 6: Install the browser extension

1. Install the **Tampermonkey** extension in your browser:
   - [Chrome](https://chrome.google.com/webstore/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)
   - [Firefox](https://addons.mozilla.org/en-US/firefox/addon/tampermonkey/)
   - [Edge](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/iikmkjmpaadaobahmlepeloendndfphd)

2. Click the **Tampermonkey icon** in your browser toolbar, then click **Dashboard**

3. Go to the **Utilities** tab

4. Under **Import from file**, click **Choose file** and select:
   ```
   D:\Projects\one-click-youtube-summarizer\tampermonkey.user.js
   ```

5. Click **Install** when prompted

### Step 7: Test it

1. Go to any YouTube video
2. You should see a **Summarize** button in the video's action bar (near Like/Share)
3. Click it
4. Your browser will ask to allow the `ytsum://` protocol — choose **Always allow**
5. A terminal window opens, downloads subtitles, and prints the summary
6. The summary is also copied to your clipboard and saved to `C:\Users\<you>\Documents\yt-summaries\`

---

## Usage without the button

You can run the script directly from any terminal:

```
python summarize_yt.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

---

## Where summaries are saved

Summaries are Markdown files saved to:

```
C:\Users\<you>\Documents\yt-summaries\
```

Each file is named after the video title (e.g. `Rick Astley - Never Gonna Give You Up.md`).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Summarize button doesn't appear | Refresh the page. Check Tampermonkey is enabled for youtube.com |
| Nothing happens when clicking the button | Run `python setup.py` again. Check browser allows `ytsum://` protocol |
| "yt-dlp not found" | Run `pip install yt-dlp` |
| "No subtitles found" | The video has no subtitles in English, Ukrainian, or Russian |
| "Claude Code CLI not found" | Install Claude Code CLI and run `claude` to log in |
| Claude hangs or errors | Run `claude` interactively first to complete login. Make sure `claude -p "hello"` works |
| Uses API tokens instead of subscription | Remove the `ANTHROPIC_API_KEY` environment variable |
| Script hangs on "Fetching video info" | Update yt-dlp: `pip install -U yt-dlp` |

---

## Future ideas

Not implemented — just notes for possible enhancements:

- Language selection flag for subtitles beyond en/uk/ru
- Multiple output formats (bullets, prose, detailed)
- Custom prompt override
- Windows toast notification when summary is ready
- Whisper fallback when no subtitles exist (download audio + transcribe)

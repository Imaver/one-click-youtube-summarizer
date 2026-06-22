#!/usr/bin/env python3
"""Install the ytsum:// protocol handler on Windows (HKEY_CURRENT_USER, no admin needed)."""

import os
import sys
import tempfile
import subprocess

REG_TEMPLATE = r"""Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Classes\ytsum]
@="URL:YouTube Summarizer Protocol"
"URL Protocol"=""

[HKEY_CURRENT_USER\Software\Classes\ytsum\shell]

[HKEY_CURRENT_USER\Software\Classes\ytsum\shell\open]

[HKEY_CURRENT_USER\Software\Classes\ytsum\shell\open\command]
@="\"{bat_path}\" \"%1\""
"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bat_path = os.path.join(script_dir, "summarize_yt.bat")

    if not os.path.isfile(bat_path):
        print(f"Error: {bat_path} not found.", file=sys.stderr)
        sys.exit(1)

    # Registry files need double-escaped backslashes
    bat_path_escaped = bat_path.replace("\\", "\\\\")
    reg_content = REG_TEMPLATE.replace("{bat_path}", bat_path_escaped)

    # Write to a temp .reg file and import it
    fd, reg_path = tempfile.mkstemp(suffix=".reg", prefix="ytsum_")
    try:
        with os.fdopen(fd, "w", encoding="utf-16-le") as f:
            # .reg files need UTF-16 LE BOM for non-ASCII path support
            f.write("\ufeff")
            f.write(reg_content)

        result = subprocess.run(
            ["reg", "import", reg_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"Error importing registry:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)

        print("ytsum:// protocol handler installed successfully.")
        print(f"  Bat file: {bat_path}")
        print(f"\nYou can test it by opening ytsum://https://www.youtube.com/watch?v=dQw4w9WgXcQ in your browser.")
    finally:
        os.unlink(reg_path)


if __name__ == "__main__":
    main()

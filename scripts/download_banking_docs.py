"""
Download Banking PDFs from Google Drive
========================================

Downloads the banking test documents from the shared Google Drive folder
into ``data/banking_docs/`` for use with the KL seed script.

Requires: ``pip install gdown``

Usage::

    python scripts/download_banking_docs.py
"""

import os
import sys

try:
    import gdown
except ImportError:
    print("ERROR: gdown is required. Install with: pip install gdown")
    sys.exit(1)


# Google Drive folder ID
DRIVE_FOLDER_ID = "1NAcIZR0schABqWDwi6CMxPdIsaup4MKC"
DRIVE_URL = f"https://drive.google.com/drive/folders/{DRIVE_FOLDER_ID}"

# Local destination
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "banking_docs",
)


def main():
    print(f"Downloading banking docs from Google Drive...")
    print(f"  Source : {DRIVE_URL}")
    print(f"  Target : {OUTPUT_DIR}")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # gdown.download_folder downloads all files recursively
    gdown.download_folder(
        url=DRIVE_URL,
        output=OUTPUT_DIR,
        quiet=False,
        use_cookies=False,
    )

    # Count what we got
    total_files = 0
    total_folders = 0
    for root, dirs, files in os.walk(OUTPUT_DIR):
        total_folders += len(dirs)
        total_files += len(files)

    print()
    print(f"Download complete!")
    print(f"  Folders : {total_folders}")
    print(f"  Files   : {total_files}")
    print(f"  Location: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

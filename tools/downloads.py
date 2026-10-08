#!/usr/bin/env python3
"""How many times each download has been fetched, across every release.

GitHub counts every download of a release file. The installer fetches
`jobhunt-skills.tar.gz` and the site's buttons fetch the zips, so these are
the installs that did not come through a plugin marketplace - those clone the
repo, and GitHub only reports clones for the last fourteen days.

    python tools/downloads.py
"""

import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
import data  # noqa: E402
from build_archives import TARBALL  # noqa: E402

API = f"https://api.github.com/repos/{data.REPO}/releases"


def releases():
    """Every release, newest first, a page at a time."""
    page = 1
    while True:
        request = urllib.request.Request(
            f"{API}?per_page=100&page={page}",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "jobhunt-downloads"})
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        if not batch:
            return
        yield from batch
        page += 1


def totals(found):
    """Downloads per file name, summed over every release that carried it."""
    counted = Counter()
    for release in found:
        for asset in release.get("assets", []):
            counted[asset["name"]] += asset.get("download_count", 0)
    return counted


def main():
    counted = totals(releases())
    if not counted:
        print("No releases yet, so nothing has been counted.")
        return 0
    width = max(map(len, counted))
    for name, n in counted.most_common():
        print(f"{name:<{width}}  {n:>6}")
    installer = counted[TARBALL]
    zips = sum(n for name, n in counted.items() if name.endswith(".zip"))
    print(f"\nthrough the installer: {installer}")
    print(f"as zip downloads:      {zips}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

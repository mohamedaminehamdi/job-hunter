#!/usr/bin/env python3
"""Build the zip files the website hands out.

One per skill, plus one of everything. A person who does not want to run a
shell script downloads a folder and drops it in - that has to be a first-class
route, not a fallback, because it is the one that works when somebody's
corporate laptop will not run curl | sh.

    python tools/build_archives.py            write docs/download/
    python tools/build_archives.py --check    exit 1 if any is stale
    python tools/build_archives.py --release DIR
                                              the zips, plus the installer's
                                              tarball, for a GitHub release

The site and the installer download from the latest release rather than from
docs/ or the branch, because GitHub counts every download of a release file -
the only way to know how many people install this.
"""

import gzip
import hashlib
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "jobhunt" / "skills"
OUT = ROOT / "docs" / "download"

#: What `install.sh` fetches from a release. Its one top-level folder matches
#: the `job-hunter-*` the branch tarball unpacks to, so the installer reads
#: either the same way.
TARBALL = "jobhunt-skills.tar.gz"
PREFIX = "job-hunter-release"

#: Never shipped inside a skill.
JUNK = {"__pycache__", ".DS_Store", ".pytest_cache"}


def files_of(skill):
    """Every file in a skill, sorted, with the junk left out."""
    found = []
    for path in sorted(skill.rglob("*")):
        if not path.is_file():
            continue
        if any(part in JUNK for part in path.parts) or path.suffix == ".pyc":
            continue
        found.append(path)
    return found


def write_zip(target, entries):
    """A zip whose bytes depend only on its contents.

    Fixed timestamps and sorted entries, so rebuilding without changing a skill
    produces an identical file - otherwise every build shows up as a change and
    `--check` is worthless.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for arcname, path in entries:
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            # 0o755 on the scripts, 0o644 on everything else.
            executable = path.suffix == ".py"
            info.external_attr = (0o755 if executable else 0o644) << 16
            archive.writestr(info, path.read_bytes())
    return target


def build():
    made = {}
    everything = []

    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        entries = [(str(Path(skill.name) / f.relative_to(skill)), f)
                   for f in files_of(skill)]
        made[skill.name] = write_zip(OUT / f"{skill.name}.zip", entries)
        everything.extend(entries)

    made["jobhunt-all"] = write_zip(OUT / "jobhunt-all.zip", everything)
    return made


def write_tarball(target, prefix=PREFIX):
    """Every skill as a .tar.gz, laid out as the repo lays it out, under
    `prefix/`. Fixed times and sorted entries, like the zips."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as raw, \
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed, \
            tarfile.open(fileobj=packed, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
            for path in files_of(skill):
                info = tarfile.TarInfo(f"{prefix}/{path.relative_to(ROOT).as_posix()}")
                info.size = path.stat().st_size
                info.mtime = 315532800                      # 1980-01-01, as the zips
                info.mode = 0o755 if path.suffix == ".py" else 0o644
                with path.open("rb") as data:
                    tar.addfile(info, data)
    return target


def release(dest):
    """Everything a release carries: the zips the site hands out and the
    tarball the installer fetches."""
    dest.mkdir(parents=True, exist_ok=True)
    for path in build().values():
        shutil.copyfile(path, dest / path.name)
    write_tarball(dest / TARBALL)
    return sorted(p.name for p in dest.iterdir())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main(argv):
    if "--release" in argv:
        at = argv.index("--release") + 1
        if at >= len(argv):
            print("--release needs a directory", file=sys.stderr)
            return 2
        names = release(Path(argv[at]))
        print(f"wrote {len(names)} release files to {argv[at]}")
        return 0

    check = "--check" in argv
    before = {p.name: digest(p) for p in OUT.glob("*.zip")} if OUT.exists() else {}
    made = build()
    after = {p.name: digest(p) for p in made.values()}

    if check and before != after:
        changed = sorted(set(before) ^ set(after)) or \
            sorted(k for k in after if before.get(k) != after[k])
        print("download archives are out of date:", file=sys.stderr)
        for name in changed:
            print(f"  {name}", file=sys.stderr)
        print("\nRun: python tools/build_archives.py", file=sys.stderr)
        return 1

    manifest = {name: {"file": f"{name}.zip", "bytes": path.stat().st_size,
                       "sha256": digest(path)}
                for name, path in sorted(made.items())}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                       encoding="utf-8")
    total = sum(m["bytes"] for m in manifest.values())
    print(f"{'checked' if check else 'wrote'} {len(made)} archives, "
          f"{total // 1024} KB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

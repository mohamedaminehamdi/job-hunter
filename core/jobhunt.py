"""Everything the jobhunt skills need, in one file, with nothing to install.

This file is copied byte-identically into every skill that ships a script, so a
skill installed on its own still works. Do not "clean up" the duplication: skills
are installed one at a time and none may import from a sibling that might not be
there. `tools/sync.py` maintains the copies and a test fails if they drift.

Standard library only, and it must stay that way. It also has to run on the
Python people already have - macOS ships 3.9 - so: no StrEnum, no datetime.UTC,
no match statements, no PEP 604 unions outside annotations.

Layout, in dependency order:

    values      coercion, the YAML subset, small text helpers
    model       Profile, Job, and the documents built from them
    guard       is this sentence backed by the profile?
    fit         how well does this CV answer this posting?
    assemble    build a document the model cannot put an employer into
    render      markdown, HTML, and a PDF via the browser you already have
    workspace   where files live
"""

from __future__ import annotations

import dataclasses
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, fields, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = "1.0.0"
#: Bumped when a file written here stops being readable by an older skill.
#: Every file carries it, and reading a higher one is an error with a fix.
SCHEMA = 1

UTC = timezone.utc


def now() -> str:
    """Timestamp for an event, in the shape every file uses."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(UTC).date().isoformat()


# --- coercion ---------------------------------------------------------------
#
# Replaces pydantic. Nothing here raises: a profile or a posting arrives from a
# model or from someone's text editor, and the right answer to a malformed field
# is to salvage what parses and report the rest as an issue the user can read.

#: Models answer a string field with a dict about as often as with a sentence,
#: and losing the number is worse than reading it as prose.
def text(value):
    """Flatten whatever landed in a string field into a string."""
    if value is None or isinstance(value, bool):
        return "" if value is None else ("yes" if value else "no")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return ", ".join(f"{k}: {s}" for k, v in value.items() if (s := text(v)))
    if isinstance(value, (list, tuple)):
        return ", ".join(s for v in value if (s := text(v)))
    return str(value).strip()


_BULLET = re.compile(r"^\s*(?:[-*•–·]|\d+[.)])\s*")


def lines(value):
    """Flatten whatever landed in a list field into clean, bullet-free lines."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.splitlines() or [value]
    elif isinstance(value, dict):
        candidates = [text(v) for v in value.values()]
    elif isinstance(value, (list, tuple)):
        candidates = [text(v) for v in value]
    else:
        candidates = [text(value)]
    return [line for c in candidates if (line := _BULLET.sub("", c).strip())]


def build(cls, raw, **overrides):
    """Build a dataclass from loose data. Total: it never raises.

    Each class declares a SHAPE mapping field names to how they coerce - "text",
    "lines", or (list, SomeClass) - and may declare COERCE for the odd field that
    needs its own rule. Anything not mentioned is text.

    `overrides` win over `raw`, which is how facts we observed - a URL, the time
    we fetched it - beat what a model wrote about them.
    """
    if not isinstance(raw, dict):
        raw = {}
    shape = getattr(cls, "SHAPE", {})
    special = getattr(cls, "COERCE", {})
    known = {f.name for f in fields(cls)}
    values = {}

    for name in known:
        if name in overrides:
            given = overrides[name]
        elif name in raw:
            given = raw[name]
        else:
            continue
        kind = shape.get(name, "text")
        try:
            if name in special:
                values[name] = special[name](given)
            elif kind == "lines":
                values[name] = lines(given)
            elif isinstance(kind, tuple) and kind[0] is list:
                items = given if isinstance(given, (list, tuple)) else []
                values[name] = [build(kind[1], item) for item in items
                                if isinstance(item, dict)]
            elif kind == "raw":
                values[name] = given
            else:
                values[name] = text(given)
        except Exception:
            # One unusable field must never lose the record.
            continue
    return cls(**values)


def asdict(obj):
    """A dataclass as plain data, ready for JSON or YAML."""
    return dataclasses.asdict(obj)


# --- YAML, the part of it anyone writes by hand -----------------------------
#
# Hand-written rather than pyyaml, because the whole point of this repo is that
# there is nothing to install. The subset is small for a reason worth knowing:
# every field of every model stored as YAML here is a string or a list of
# strings. Not one int, float or bool. So the reader never guesses a type, and
# the worst parts of YAML - Norway, sexagesimals, 1.0 against "1.0" - cannot
# arise.
#
# It also reports the line. The old reader caught a parse error and returned an
# empty profile, so a typo on line 14 was reported as "a name is required".


class YamlError(ValueError):
    """A YAML file we could not read, and where."""

    def __init__(self, line, message):
        self.line = line
        super().__init__(f"line {line}: {message}")


_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w.-]*)\s*:(?:\s+(?P<value>.*))?$")


class _Literal(str):
    """Text from a | block. Already final, so `_unquote` must leave it alone -
    it is the one value whose leading and trailing whitespace is content."""
_ITEM = re.compile(r"^-(?:\s+(?P<value>.*))?$")


def _unquote(raw, number):
    if isinstance(raw, _Literal):
        return str(raw)
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        body = value[1:-1]
        if value[0] == '"':
            return body.replace('\\"', '"').replace("\\n", "\n")
        return body.replace("''", "'")          # YAML escapes ' inside '...' by doubling
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_unquote(p, number) for p in inner.split(",")]
    if value.startswith(("&", "*", "!", "{")):
        raise YamlError(number, f"{value[0]!r} is YAML this reader does not do. "
                                "Use plain keys, lists and quoted strings.")
    return value


def _strip_comment(raw):
    """Drop a trailing comment, leaving one inside quotes alone."""
    out, quote = [], ""
    for i, ch in enumerate(raw):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip(" \t\r")


def _block(collected, keep_newline):
    body = "\n".join(collected).rstrip("\n")
    return _Literal(body + "\n" if keep_newline and body else body)


def yaml_load(source):
    """Read the subset. Returns a dict. Raises YamlError with a line number."""
    rows = []
    pending = None          # (indent, key, [lines]) while inside a | block
    folding = None          # indent of the row a folded scalar belongs to
    for number, raw in enumerate(source.splitlines(), 1):
        if pending is not None:
            indent, key, collected, keep_newline = pending
            if not raw.strip(" \t\r") or (len(raw) - len(raw.lstrip(" \t"))) > indent:
                collected.append(raw[indent + 2:] if len(raw) > indent + 2 else "")
                continue
            rows.append((indent, key, _block(collected, keep_newline), number))
            pending = None
        line = _strip_comment(raw)
        if not line.strip(" \t\r"):
            # A blank line inside a folded scalar is a paragraph break, which
            # YAML folds to a newline rather than a space.
            if folding is not None and rows:
                last = rows[-1]
                rows[-1] = (last[0], last[1], last[2] + "\n", last[3])
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        body = line.strip(" \t\r")

        # Inside a folded plain scalar every deeper line belongs to it, colon or
        # not. "fleet: we partner on supply deals" is prose, not a key, and only
        # the indent says so. We never write folded scalars; pyyaml does, and
        # people have files it wrote.
        if folding is not None and indent > folding:
            last = rows[-1]
            joiner = "" if last[2].endswith("\n") else " "
            rows[-1] = (last[0], last[1], last[2] + joiner + body, last[3])
            continue
        folding = None

        if body == "---":
            continue
        if (item := _ITEM.match(body)) is not None:
            value = item.group("value")
            rows.append((indent, None, value, number))
            # "- key: value" opens a map, so the deeper lines under it are its
            # sibling keys. "- some text" is a scalar, so they are its folding.
            folding = indent if value and _KEY.match(value) is None else None
            continue
        if (pair := _KEY.match(body)) is not None:
            value = pair.group("value")
            if value is not None and value.strip() in ("|", "|-"):
                # "|" keeps one trailing newline, "|-" strips it. Getting this
                # wrong loses or invents a character at the end of a long text.
                pending = (indent, pair.group("key"), [], value.strip() == "|")
                continue
            rows.append((indent, pair.group("key"), value, number))
            folding = indent if value else None
            continue
        raise YamlError(number, f'expected "key: value" or "- item", got {body[:40]!r}')

    if pending is not None:
        indent, key, collected, keep_newline = pending
        rows.append((indent, key, _block(collected, keep_newline),
                     len(source.splitlines())))

    value, index = _read_block(rows, 0, rows[0][0] if rows else 0)
    return value if isinstance(value, dict) else {}


def _read_block(rows, index, indent):
    """One block at `indent`, as a dict or a list, and where it ended."""
    if index >= len(rows):
        return {}, index
    if rows[index][1] is None:
        out_list = []
        while index < len(rows) and rows[index][0] == indent and rows[index][1] is None:
            _, _, value, number = rows[index]
            index += 1
            if value is None or value == "":
                nested, index = _read_block(rows, index, rows[index][0]) \
                    if index < len(rows) and rows[index][0] > indent else ({}, index)
                out_list.append(nested)
            elif (pair := _KEY.match(value)) is not None:
                # "- key: value" opens a map whose first pair is on the dash line
                item = {pair.group("key"): _unquote(pair.group("value") or "", number)}
                child = indent + 2
                while index < len(rows) and rows[index][0] >= child \
                        and rows[index][1] is not None:
                    nested, index = _read_block(rows, index, rows[index][0])
                    item.update(nested if isinstance(nested, dict) else {})
                out_list.append(item)
            else:
                out_list.append(_unquote(value, number))
        return out_list, index

    out = {}
    while index < len(rows) and rows[index][0] == indent and rows[index][1] is not None:
        _, key, value, number = rows[index]
        index += 1
        if value is None or value == "":
            if index < len(rows) and rows[index][0] > indent:
                out[key], index = _read_block(rows, index, rows[index][0])
            elif index < len(rows) and rows[index][1] is None \
                    and rows[index][0] == indent:
                out[key], index = _read_block(rows, index, indent)
            else:
                out[key] = ""
        else:
            out[key] = _unquote(value, number)
    return out, index


_PLAIN = re.compile(r"^[A-Za-z0-9][\w .,;:/()+&'#@%-]*$")
#: Everything here is a string, but an unquoted 2026 or true or no would come
#: back from any other YAML reader as an int or a bool. Quote them on the way
#: out so the file means the same thing to everyone.
_LOOKS_TYPED = re.compile(
    r"^(?:[-+]?\d[\d,._]*(?:[eE][-+]?\d+)?|0[xob][0-9a-fA-F]+"
    r"|true|false|yes|no|on|off|null|~|\d{4}-\d\d-\d\d.*)$", re.IGNORECASE)


def _scalar(value):
    text_value = "" if value is None else str(value)
    if "\n" in text_value:
        return None                                   # caller writes a | block
    if (text_value == "" or not _PLAIN.match(text_value)
            or _LOOKS_TYPED.match(text_value) or text_value.endswith(" ")
            or ": " in text_value or text_value.endswith(":")):
        return '"' + text_value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text_value


def yaml_dump(data, indent=0):
    """Write the subset back, canonically: two spaces, one value per line.

    Never folds a long line. A folded achievement bullet is exactly the thing a
    person then edits wrongly.
    """
    pad = " " * indent
    out = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and value:
                out.append(f"{pad}{key}:")
                out.append(yaml_dump(value, indent + 2))
            elif isinstance(value, (list, tuple)):
                if not value:
                    out.append(f"{pad}{key}: []")
                else:
                    out.append(f"{pad}{key}:")
                    out.append(yaml_dump(list(value), indent))
            elif isinstance(value, dict):
                out.append(f"{pad}{key}: {{}}")
            else:
                written = _scalar(value)
                if written is None:
                    body = str(value)
                    out.append(f"{pad}{key}: " + ("|" if body.endswith("\n") else "|-"))
                    out += [f"{pad}  {line}" for line in body.rstrip("\n").splitlines()]
                else:
                    out.append(f"{pad}{key}: {written}")
    elif isinstance(data, (list, tuple)):
        for item in data:
            if isinstance(item, dict) and item:
                body = yaml_dump(item, indent + 2).splitlines()
                out.append(f"{pad}- {body[0].strip()}")
                out += body[1:]
            else:
                written = _scalar(item) or '""'
                out.append(f"{pad}- {written}")
    return "\n".join(out)

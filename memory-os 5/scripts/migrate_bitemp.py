#!/usr/bin/env python3
"""memory-os bi-temporal migration (2026-07-18, frontier upgrade).

Add `valid_from`, `valid_until`, `supersedes`, `supersession_reason` to entity
frontmatter. Infer `valid_from` from existing `last_verified` (the historical
floor). Leave `valid_until` null (means "still current"). Add `supersedes` /
`supersession_reason` only when the existing file already has a `superseded_by`
human-readable strikethrough — back-fill the typed pointer.

Run from workspace root:
    python3 memory/scripts/migrate_bitemp.py [--dry-run] [--verbose]
Or point at the vault explicitly:
    python3 /path/to/skill/scripts/migrate_bitemp.py --root=/path/to/memory [--dry-run] [--verbose]

Idempotent: re-running on an already-migrated vault is a no-op (skips files
that already declare `valid_from`).

Side-effects: writes files in place; never deletes; emits a brief changelog
line to memory/changelog.md.
"""

import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # memory/
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools", "personal"]
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, text[m.end():]


def serialize_frontmatter(fm):
    """Stable key order: type, aliases, salience, confidence, then transaction-time,
    then valid-time, then supersession, then anything else."""
    keys = [
        "type", "aliases", "salience", "confidence",
        "created_at", "verified_at", "last_verified",
        "valid_from", "valid_until",
        "supersedes", "superseded_by", "supersession_reason",
        "source_kind",
    ]
    out = ["---"]
    seen = set()
    for k in keys:
        if k in fm:
            out.append(f"{k}: {fm[k]}")
            seen.add(k)
    for k, v in fm.items():
        if k not in seen:
            out.append(f"{k}: {v}")
    out.append("---")
    return "\n".join(out) + "\n"


def upgrade_one(path, dry_run=False, verbose=False):
    text = open(path, encoding="utf-8").read()
    fm, body = parse_frontmatter(text)
    if fm is None:
        return "skip-no-frontmatter"

    # Skip if already migrated.
    if "valid_from" in fm:
        return "skip-already-migrated"

    changed = False
    additions = []

    # 1. valid_from ← last_verified (the historical floor).
    if "last_verified" in fm and "valid_from" not in fm:
        fm["valid_from"] = fm["last_verified"]
        additions.append(f"valid_from={fm['last_verified']}")
        changed = True

    # 2. verified_at ← last_verified (transaction time, explicit rename; same value).
    if "last_verified" in fm and "verified_at" not in fm:
        fm["verified_at"] = fm["last_verified"]
        additions.append(f"verified_at={fm['last_verified']}")
        changed = True

    # 3. valid_until: default to null (Eywa's ⊥ — "still current").
    if "valid_until" not in fm:
        fm["valid_until"] = "null"
        additions.append("valid_until=null (still current)")
        changed = True

    # 4. created_at ← file mtime if not present.
    if "created_at" not in fm:
        try:
            mtime = datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
            fm["created_at"] = mtime
            additions.append(f"created_at={mtime} (from mtime)")
            changed = True
        except Exception:
            pass

    # 5. Back-fill supersedes from any superseded_by.
    superseded_by = fm.get("superseded_by")
    if superseded_by and superseded_by not in ("null", "?", "") and "supersedes" not in fm:
        fm["supersedes"] = superseded_by
        additions.append(f"supersedes={superseded_by} (back-filled from superseded_by)")
        changed = True
        if "supersession_reason" not in fm:
            fm["supersession_reason"] = "unknown"
            additions.append("supersession_reason=unknown (default)")

    if not changed:
        return "noop"

    new_text = serialize_frontmatter(fm) + body
    if not dry_run:
        open(path, "w", encoding="utf-8").write(new_text)
    if verbose:
        print(f"  + {os.path.relpath(path, ROOT)}: {', '.join(additions)}")
    return "migrated"


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or dry_run
    if dry_run:
        print("[DRY-RUN] no files will be written.")

    # Allow ROOT override via --root=PATH.
    global ROOT
    for arg in sys.argv:
        if arg.startswith("--root="):
            ROOT = arg.split("=", 1)[1]
            break

    counts = {"migrated": 0, "skip-already-migrated": 0, "noop": 0, "skip-no-frontmatter": 0}
    for d in ENTITY_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".md") or fn == "README.md":
                continue
            outcome = upgrade_one(os.path.join(dp, fn), dry_run=dry_run, verbose=verbose)
            counts[outcome] = counts.get(outcome, 0) + 1

    if not dry_run and counts["migrated"]:
        changelog = os.path.join(ROOT, "changelog.md")
        if os.path.isfile(changelog):
            stamp = datetime.date.today().isoformat()
            note = (
                f"\n## {stamp} — bi-temporal migration (memory-os 2026-07-18 upgrade)\n\n"
                f"- Added `valid_from`, `valid_until`, `verified_at`, `created_at` to "
                f"{counts['migrated']} entity files.\n"
                f"- Back-filled `supersedes` from existing `superseded_by` human-readable "
                f"markers where present.\n"
                f"- Run: `python3 memory/scripts/migrate_bitemp.py`\n"
                f"- Frontier basis: Engram (arXiv:2606.09900) + Eywa (arXiv:2605.30771).\n"
                f"---\n"
            )
            with open(changelog, "a", encoding="utf-8") as f:
                f.write(note)

    print(f"bi-temporal migration: {counts}")
    return 0 if counts["migrated"] or not dry_run else 1


if __name__ == "__main__":
    sys.exit(main())

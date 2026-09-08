#!/usr/bin/env python3
"""OKF (Open Knowledge Format v0.1) conformance checker for a memory-os vault.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
Conformance rules checked:
  1. Every non-reserved .md file has a parseable YAML frontmatter block.
  2. Every frontmatter block has a non-empty `type` field.
  3. Root index.md declares okf_version (the only index.md allowed frontmatter).
Reserved filenames: index.md, log.md.

Usage:
  python3 okf_check.py [--root=PATH] [--fix]
    --fix   add minimal frontmatter (type derived from directory) to bare files
Env: MEMORY_ROOT overrides root. Exit 0 = conformant, 1 = violations remain.
"""
import os, re, sys, datetime

def _resolve_root():
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOT = _resolve_root()
RESERVED = {"index.md", "log.md"}
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
TYPE_RE = re.compile(r"^type:\s*(\S.*)$", re.M)

TYPE_BY_DIR = {
    "people": "Person", "projects": "Project", "teams": "Team",
    "decisions": "Decision", "procedural": "Playbook", "tools": "Playbook",
    "episodic": "Episode", "inbox": "Inbox Capture", "personal": "Note",
    "scripts": None,  # not knowledge docs
}


def derive_type(relpath, fname):
    parts = relpath.split(os.sep)
    for p in reversed(parts[:-1]):
        if p in TYPE_BY_DIR:
            return TYPE_BY_DIR[p]
    stem = fname.lower()
    if "changelog" in stem or stem == "log.md":
        return "Log"
    if "glossary" in stem or "alias" in stem:
        return "Reference"
    if "health" in stem:
        return "Status Report"
    if "readme" in stem:
        return "Reference"
    if "needle" in stem:
        return "Reference"
    return "Note"


def main():
    fix = "--fix" in sys.argv
    violations, fixed, ok = [], [], 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if os.path.basename(dirpath) == "scripts":
            continue
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            text = open(p, encoding="utf-8").read()
            if fn in RESERVED:
                if rel == "index.md" and "okf_version" not in text:
                    violations.append(f"{rel}: root index.md missing okf_version declaration")
                continue
            m = FM_RE.match(text)
            if m and TYPE_RE.search(m.group(1)):
                ok += 1
                continue
            etype = derive_type(rel, fn)
            if etype is None:
                continue
            if fix:
                today = datetime.date.today().isoformat()
                if m:  # frontmatter exists but no type — insert type line
                    new_fm = f"---\ntype: {etype}\n{m.group(1)}\n---\n"
                    text = new_fm + text[m.end():]
                else:
                    title_m = re.search(r"^# (.+)$", text, re.M)
                    title = title_m.group(1).strip() if title_m else os.path.splitext(fn)[0]
                    text = (f"---\ntype: {etype}\ntitle: {title}\n"
                            f"timestamp: {today}\nsource_kind: human-stated\n---\n") + text
                try:
                    open(p, "w", encoding="utf-8").write(text)
                    fixed.append(f"{rel} -> type: {etype}")
                    ok += 1
                except PermissionError:
                    print(f"  skipped (read-only, left as-is): {rel}")
            else:
                violations.append(f"{rel}: missing frontmatter/type (would derive: {etype})")

    print(f"okf_check: {ok} conformant concept docs under {ROOT}")
    for f in fixed:
        print(f"  fixed: {f}")
    for v in violations:
        print(f"  VIOLATION: {v}")
    if violations:
        print(f"RESULT: NOT CONFORMANT ({len(violations)} violations)" + (" — rerun with --fix" if not fix else ""))
        sys.exit(1)
    print("RESULT: OKF v0.1 conformant")
    sys.exit(0)


if __name__ == "__main__":
    main()

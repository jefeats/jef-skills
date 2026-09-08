#!/usr/bin/env python3
"""Heuristic classifier for supersession_reason (red-team DEFECT 11).

Finds entities with supersession_reason: unknown (or superseded facts lacking
one) and suggests an enum value from keyword evidence near the supersession:
  correction        — wrong, error, mistake, actually, mis-, incorrect
  preference_change — prefers, likes, wants, switched to, now uses
  factual_update    — new role/manager/owner/team/status, promoted, moved to, joined, left, departing
  scope_change      — renamed, split, merged, expanded, narrowed, reorg

Suggestions only by default; --apply writes them (still leaves `unknown`
when no keyword evidence — a human or consolidation LLM decides those).

Usage: python3 classify_supersession.py [--root=PATH] [--apply]
"""
import os, re, sys

def _resolve_root():
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOT = _resolve_root()
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools", "personal"]

RULES = [
    ("correction", r"\b(wrong|error|mistake|actually|incorrect|mis[- ]?\w+)\b"),
    ("preference_change", r"\b(prefers?|likes?|wants?|switched to|now uses)\b"),
    ("factual_update", r"\b(new (role|manager|owner|team)|promoted|moved to|joined|left|departing|handed (over|to)|superseded|since \d{4})\b"),
    ("scope_change", r"\b(renamed|split|merged|expanded|narrowed|reorg\w*|scope)\b"),
]


def classify(context):
    ctx = context.lower()
    for reason, pat in RULES:
        if re.search(pat, ctx):
            return reason
    return None


def main():
    apply_mode = "--apply" in sys.argv
    n_sugg = n_applied = 0
    for d in ENTITY_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            text = open(p, encoding="utf-8").read()
            if not re.search(r"^supersession_reason:\s*(unknown|null)\s*$", text, re.M):
                continue
            if not re.search(r"^supersedes:\s*(?!null)\S", text, re.M) and "superseded_by" not in text:
                continue  # nothing actually superseded — leave alone
            suggestion = classify(text)
            if not suggestion:
                continue
            n_sugg += 1
            rel = f"{d}/{fn}"
            if apply_mode:
                text = re.sub(r"^supersession_reason:\s*(unknown|null)\s*$",
                              f"supersession_reason: {suggestion}  # heuristic; verify at consolidation",
                              text, count=1, flags=re.M)
                open(p, "w", encoding="utf-8").write(text)
                n_applied += 1
                print(f"applied: {rel} -> {suggestion}")
            else:
                print(f"suggest: {rel} -> {suggestion}")
    print(f"classify_supersession: {n_sugg} suggestions, {n_applied} applied")


if __name__ == "__main__":
    main()

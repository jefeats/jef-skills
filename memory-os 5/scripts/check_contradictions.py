#!/usr/bin/env python3
"""memory-os contradiction & supersession audit (2026-07-18, frontier upgrade).

Walk the entity store and find contradictions that should be promoted into
typed supersession chains. Reports three classes:

1. **Stranded superseded_by**: frontmatter declares `superseded_by: <id>` but no
   `supersedes` pointer on the new entity. The migration in `migrate_bitemp.py`
   back-fills the canonical pointer; this script flags anything it missed.
2. **Open-fact chains**: `supersedes` chain that doesn't terminate — either
   because the chain loops or because the most-recent fact lacks
   `valid_until` set to null (i.e. it's still "current", which is fine, but if
   the chain has >3 hops it suggests drift).
3. **Stale validity windows**: `valid_until` is set in the past but
   `supersession_reason` is "unknown" — these need human review.

Run from workspace root:
    python3 memory/scripts/check_contradictions.py [--json] [--verbose]
"""

import os
import re
import sys
import json
import datetime

def _resolve_root():
    """Portability contract: MEMORY_ROOT env -> --root= arg -> script-relative."""
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ROOT = _resolve_root()
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools", "personal"]
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
TODAY = datetime.date.today()


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def load_entities():
    by_path = {}
    for d in ENTITY_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".md") or fn == "README.md":
                continue
            p = os.path.join(dp, fn)
            text = open(p, encoding="utf-8").read()
            fm = parse_frontmatter(text)
            if not fm:
                continue
            fm["_path"] = os.path.relpath(p, ROOT)
            by_path[fm["_path"]] = fm
    return by_path


def find_chains(by_path):
    """Walk each entity's supersedes → supersedes chain; return longest chain per entity."""
    chains = {}
    for path, fm in by_path.items():
        chain = []
        seen = set()
        cur = path
        cur_fm = fm
        while True:
            if cur in seen:
                chain.append(f"LOOP@{cur}")
                break
            seen.add(cur)
            chain.append(cur)
            nxt = cur_fm.get("supersedes")
            if not nxt or nxt in ("null", "?", ""):
                break
            # Resolve supersedes target. Accept full path or basename match.
            target = by_path.get(nxt)
            if not target:
                # Try matching by basename within entity store.
                target = next((v for k, v in by_path.items() if k.endswith(nxt)), None)
            if not target:
                chain.append(f"UNRESOLVED→{nxt}")
                break
            cur = target["_path"]
            cur_fm = target
        chains[path] = chain
    return chains


def main():
    as_json = "--json" in sys.argv
    verbose = "--verbose" in sys.argv
    by_path = load_entities()
    chains = find_chains(by_path)

    issues = []

    # Class 1: stranded superseded_by without supersedes reciprocal.
    for path, fm in by_path.items():
        sb = fm.get("superseded_by")
        sp = fm.get("supersedes")
        if sb and sb not in ("null", "?", "") and not sp:
            issues.append({
                "type": "stranded_superseded_by",
                "path": path,
                "superseded_by": sb,
                "fix": "Run scripts/migrate_bitemp.py to back-fill supersedes.",
            })

    # Class 2: chains >3 hops suggest drift (or are loops).
    for path, chain in chains.items():
        if len(chain) > 3 and not any("LOOP" in c for c in chain):
            issues.append({
                "type": "long_chain",
                "path": path,
                "chain": chain,
                "fix": "Audit chain; consider folding intermediate hops into a topic doc.",
            })
        if any("LOOP" in c for c in chain):
            issues.append({
                "type": "supersedes_loop",
                "path": path,
                "chain": chain,
                "fix": "Manual intervention required: break the loop, ensure terminal entity has supersedes=null.",
            })

    # Class 3: valid_until in the past + supersession_reason=unknown.
    for path, fm in by_path.items():
        vu = fm.get("valid_until")
        sr = fm.get("supersession_reason")
        if vu and vu not in ("null", "?", "") and sr == "unknown":
            try:
                dt = datetime.date.fromisoformat(vu)
                if dt < TODAY:
                    issues.append({
                        "type": "stale_unknown_reason",
                        "path": path,
                        "valid_until": vu,
                        "fix": "Set supersession_reason to one of: correction|preference_change|factual_update|scope_change.",
                    })
            except ValueError:
                pass

    if as_json:
        print(json.dumps({"issues": issues, "count": len(issues)}, indent=2))
    else:
        print(f"contradiction audit: {len(issues)} issues across {len(by_path)} entities")
        if verbose or issues:
            for i in issues:
                print(f"  [{i['type']}] {i['path']}: {i['fix']}")
        if not issues:
            print("  clean.")
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())

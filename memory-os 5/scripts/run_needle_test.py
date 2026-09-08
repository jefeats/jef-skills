#!/usr/bin/env python3
"""Score the needle test against THIS vault (generic; reads a generated spec).

Replaces an earlier version that hardcoded one vault's own entities (names,
manager relationships, ticket IDs) into the scorer — that scored ~1/12 for any
other vault and printed private names on screen. Names must never live in this
file. This version reads memory/needle-test.json (produced by
build_needle_test.py from the vault's own entities) and RE-VERIFIES the same
predicate the builder used, so a PASS means the answer is still structurally
present — this is a regression test, not a file-existence check.

Not the agent's retrieval protocol — the agent reranks grep hits
(Claude-as-cross-encoder, arXiv:2606.28367). This is the mechanical floor.
Abstention on the SILENCE case is a PASS (Memory Silence, arXiv:2606.06055).

Usage:
  python3 run_needle_test.py [--root=PATH] [--smoke] [--json]
    --smoke   2-question workshop smoke test (first alias lookup + silence)
    --json    machine-readable result
Env: MEMORY_ROOT overrides root. If no spec exists, auto-builds one.
"""
import os, re, sys, json, subprocess

# ---- shared matching helpers (MUST stay identical to build_needle_test.py) ----
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools",
               "procedural", "personal", "episodic"]
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
COMP_RE = re.compile(r"\b(salary|compensation|bonus|take-home|net pay|gross pay)\b", re.I)
RATIONALE_RE = re.compile(r"\b(because|rationale|why|so that|in order to|trade-?off)\b", re.I)
PROCEDURAL_RE = re.compile(r"\b(Recipe|Works|Fails|Playbook)\b")
MID_RE = re.compile(r"\*\*Mid[^\n]*\*\*\s*(\S.+)")
PROVENANCE_RE = re.compile(r"(https?://|[a-z]+://|observed_at|\(source)")
DISAMBIG_CI = re.compile(r"(≠|\bvs\.?\b|\bdistinct from\b|\bnot the\b|\bas opposed to\b)", re.I)
DISAMBIG_CS = re.compile(r"\bNOT\b")


def word_re(alias):
    return re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.I)


def _resolve_root():
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()
SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def load_all():
    out = {}
    for d in ENTITY_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".md") or fn in ("README.md", "index.md"):
                continue
            p = os.path.join(dp, fn)
            try:
                out[os.path.relpath(p, ROOT)] = open(p, encoding="utf-8").read()
            except OSError:
                continue
    return out


def body_of(text):
    m = FM_RE.match(text)
    return text[m.end():] if m else text


def fm_region(text):
    m = FM_RE.match(text)
    return m.group(1) if m else ""


def alias_map(ents):
    am = {}
    for path, text in ents.items():
        for line in fm_region(text).splitlines():
            if line.startswith("aliases:"):
                v = line.split(":", 1)[1].strip()
                vals = ([x.strip() for x in v[1:-1].split(",")] if v.startswith("[") else [v])
                for a in vals:
                    if a:
                        am.setdefault(a.lower(), path)
    return am


def check(q, ents, am):
    """Re-verify the builder's predicate. Return (passed, detail)."""
    k = q["kind"]
    ent = ents.get(q.get("entity", ""), "")
    if k == "alias_lookup":
        tgt = am.get(q["alias"].lower())
        return bool(tgt == q["entity"] or (tgt and q["expect_answer"].split()[0] in ents.get(tgt, ""))), tgt or "alias not in map"
    if k == "two_hop":
        tgt = am.get(q["alias"].lower())
        return bool(word_re(q["alias"]).search(body_of(ent)) and tgt == q.get("target")), tgt or "link broken"
    if k == "superseded":
        fm = fm_region(ent)
        ok = ("~~" in body_of(ent)
              or re.search(r"^valid_until:\s*(?!null)\S", fm, re.M)
              or re.search(r"^supersedes:\s*(?!null)\S", fm, re.M))
        return bool(ok), "supersession recorded" if ok else "no chain"
    if k == "date_anchored":
        return q["date"] in body_of(ent), q.get("date", "")
    if k == "broad_topic":
        b = body_of(ent)
        refs = {bp for a, bp in am.items()
                if bp != q["entity"] and len(a) >= 3 and word_re(a).search(b)}
        return len(refs) >= q.get("min_refs", 2), f"{len(refs)} refs"
    if k == "term_disambiguation":
        gloss = os.path.join(ROOT, "glossary.md")
        g = open(gloss, encoding="utf-8").read() if os.path.isfile(gloss) else ""
        return bool(DISAMBIG_CS.search(g) or DISAMBIG_CI.search(g)), "glossary"
    if k == "decision_rationale":
        return bool(RATIONALE_RE.search(body_of(ent))), "rationale present" if ent else "file gone"
    if k == "procedural_lookup":
        return bool(PROCEDURAL_RE.search(ent)), "recipe present" if ent else "file gone"
    if k == "person_pattern":
        m = MID_RE.search(body_of(ent))
        return bool(m and len(m.group(1).strip()) > 8), "mid layer present" if ent else "file gone"
    if k == "provenance":
        return bool(PROVENANCE_RE.search(body_of(ent))), "source present" if ent else "file gone"
    if k == "silence":
        for p, t in ents.items():
            if COMP_RE.search(t):
                return False, f"LEAK in {p}"
        return True, "no compensation data (correct abstain)"
    return False, "unknown kind"


def load_spec():
    sp = os.path.join(ROOT, "needle-test.json")
    if not os.path.isfile(sp):
        build = os.path.join(SCRIPTS, "build_needle_test.py")
        if os.path.isfile(build):
            subprocess.run([sys.executable, build, f"--root={ROOT}"], check=False)
    if not os.path.isfile(sp):
        return None
    with open(sp, encoding="utf-8") as f:
        return json.load(f)


def main():
    spec = load_spec()
    if not spec or not spec.get("questions"):
        print("needle: no spec and none could be built — draft entities, then "
              "run build_needle_test.py.", file=sys.stderr)
        return 2
    ents = load_all()
    am = alias_map(ents)
    qs = spec["questions"]
    smoke = "--smoke" in sys.argv
    if smoke:
        alias_q = [q for q in qs if q["kind"] == "alias_lookup"][:1]
        silence_q = [q for q in qs if q["kind"] == "silence"][:1]
        qs = (alias_q + silence_q) or qs[:2]

    results, score = [], 0
    for q in qs:
        ok, detail = check(q, ents, am)
        score += ok
        results.append((q["id"], q["kind"], ok, detail))

    if "--json" in sys.argv:
        print(json.dumps({"score": score, "n": len(qs),
                          "results": [{"id": i, "kind": k, "pass": o, "detail": d} for i, k, o, d in results],
                          "coverage_gaps": spec.get("coverage_gaps", [])}, ensure_ascii=False))
        return 0 if score == len(qs) else 1

    print(f"Loaded {len(ents)} entities, {len(am)} aliases. {'SMOKE ' if smoke else ''}needle test:")
    print("=" * 70)
    for i, k, ok, d in results:
        print(f"  {'✓' if ok else '✗'} {i:5s} {k:20s} [{'PASS' if ok else 'FAIL'}] {d}")
    print("=" * 70)
    print(f"NEEDLE TEST SCORE: {score}/{len(qs)}")
    for g in spec.get("coverage_gaps", []):
        print(f"  (coverage gap) {g}")
    return 0 if score == len(qs) else 1


if __name__ == "__main__":
    sys.exit(main())

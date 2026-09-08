#!/usr/bin/env python3
"""Build a needle test from THIS vault's own entities (generic; no hardcoded facts).

memory-os's needle test (SKILL.md step 8, references/templates.md) must be built
from "the user's OWN entities" — the previously shipped scorer was hardcoded to
one person's biography, so it scored ~1/12 for anyone else and leaked private
names. This generator inspects whatever is actually in the vault and emits the
grounded subset of the canonical categories:

  alias-only lookup x2, 2-hop relation, superseded fact, temporal/date-anchored
  fact, broad topic, term disambiguation, decision rationale, procedural/tool
  lookup, person pattern, provenance citation, and one SILENCE case.

Recall-first honesty (controlled-ablation finding, arXiv:2606.28367): it only
emits a question it can ground in real vault content, and REPORTS the categories
it could not cover as coverage gaps rather than inventing facts. Abstention is a
valid outcome (Memory Silence, arXiv:2606.06055). run_needle_test.py re-verifies
the SAME predicate this builder used, so the test catches regressions — not just
file deletion.

Outputs (stdlib only, no deps):
  memory/needle-test.json   machine spec consumed by run_needle_test.py
  memory/needle-test.md     human-readable question sheet (OKF: type: Reference)

Usage:
  python3 build_needle_test.py [--root=PATH] [--max=12]
Env: MEMORY_ROOT overrides root. Root default: script-relative (scripts/ parent).
"""
import os, re, sys, json, datetime

# ---- shared matching helpers (MUST stay identical to run_needle_test.py) ----
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools",
               "procedural", "personal", "episodic"]
FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
STOP = {"the", "and", "for", "with", "team", "role", "null", "true", "false"}
RATIONALE_RE = re.compile(r"\b(because|rationale|why|so that|in order to|trade-?off)\b", re.I)
PROCEDURAL_RE = re.compile(r"\b(Recipe|Works|Fails|Playbook)\b")
MID_RE = re.compile(r"\*\*Mid[^\n]*\*\*\s*(\S.+)")
PROVENANCE_RE = re.compile(r"(https?://|[a-z]+://|observed_at|\(source)")
# disambiguation: uppercase NOT (literal) OR case-insensitive relational markers
DISAMBIG_CI = re.compile(r"(≠|\bvs\.?\b|\bdistinct from\b|\bnot the\b|\bas opposed to\b)", re.I)
DISAMBIG_CS = re.compile(r"\bNOT\b")


def word_re(alias):
    """Boundary match that is correct for punctuation-bearing aliases
    (s.rivers@, pm-priya) where \\b fails. Case-insensitive."""
    return re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.I)


def _resolve_root():
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


ROOT = _resolve_root()


def _max_questions():
    for arg in sys.argv[1:]:
        if arg.startswith("--max="):
            try:
                return max(1, int(arg.split("=", 1)[1]))
            except ValueError:
                return 12
    return 12


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


def parse_fm(text):
    m = FM_RE.match(text)
    fm = {}
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def body_of(text):
    m = FM_RE.match(text)
    return text[m.end():] if m else text


def display_name(path, text):
    m = re.search(r"^#\s+(.+)$", body_of(text), re.M)
    if m:
        return m.group(1).strip()
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.replace("-", " ").replace("_", " ").title()


def alias_list(text):
    v = parse_fm(text).get("aliases", "")
    if v.startswith("[") and v.endswith("]"):
        return [x.strip() for x in v[1:-1].split(",") if x.strip()]
    return [v] if v else []


def alias_map(ents):
    am = {}
    for path, text in ents.items():
        for a in alias_list(text):
            am.setdefault(a.lower(), path)
    return am


def build(ents, cap):
    am = alias_map(ents)
    people = {p: t for p, t in ents.items() if p.startswith("people/")}
    projects = {p: t for p, t in ents.items() if p.startswith("projects/")}
    decisions = {p: t for p, t in ents.items() if p.startswith("decisions/")}
    procedural = {p: t for p, t in ents.items() if p.startswith("procedural")}
    questions, gaps = [], []

    def add(q):
        q["id"] = f"Q{len(questions)+1}"
        questions.append(q)

    # --- alias-only lookup x2: prefer NON-OBVIOUS aliases (not a substring of the title) ---
    picked = 0
    for path, text in list(people.items()) + list(projects.items()):
        name = display_name(path, text)
        for a in alias_list(text):
            al = a.lower()
            if al in name.lower() or len(al) < 2:
                continue  # obvious alias (substring of title) — weak test
            if any(q["kind"] == "alias_lookup" and q["entity"] == path for q in questions):
                continue
            add({"kind": "alias_lookup", "question": f"Who/what is “{a}”?",
                 "expect_answer": name, "alias": a, "entity": path})
            picked += 1
            break
        if picked >= 2:
            break
    if picked < 2:
        gaps.append(f"alias-only lookup (wanted 2, grounded {picked}) — add distinctive aliases/handles to entities")

    # --- 2-hop relation: entity A body mentions an alias resolving to entity B ---
    for a_path, a_text in ents.items():
        ab = body_of(a_text)
        hit = None
        for alias, b_path in am.items():
            if b_path == a_path or len(alias) < 3 or alias in STOP:
                continue
            if word_re(alias).search(ab):
                hit = (alias, b_path)
                break
        if hit:
            add({"kind": "two_hop",
                 "question": f"Via {display_name(a_path, a_text)}, who/what is connected through “{hit[0]}”?",
                 "expect_answer": display_name(hit[1], ents[hit[1]]),
                 "entity": a_path, "alias": hit[0], "target": hit[1]})
            break
    else:
        gaps.append("2-hop relation — no entity body cross-references another entity's alias yet")

    # --- superseded fact: entity with valid_until set OR supersedes pointer OR strikethrough ---
    for path, text in ents.items():
        fm = parse_fm(text)
        vu, sup = fm.get("valid_until", "null"), fm.get("supersedes", "null")
        if (vu and vu != "null") or (sup and sup != "null") or "~~" in body_of(text):
            add({"kind": "superseded",
                 "question": f"For {display_name(path, text)}, what was true before the most recent change (and is a supersession recorded)?",
                 "expect_answer": "a superseded/prior value is recorded (valid_until or supersedes set)",
                 "entity": path})
            break
    else:
        gaps.append("superseded fact — no entity carries a supersession chain yet (expected on a fresh vault)")

    # --- temporal / date-anchored fact: entity whose body cites a concrete date ---
    for path, text in ents.items():
        m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", body_of(text))
        if m:
            add({"kind": "date_anchored",
                 "question": f"What does {display_name(path, text)} record happening on {m.group(1)}?",
                 "expect_answer": f"a dated fact anchored to {m.group(1)}",
                 "entity": path, "date": m.group(1)})
            break
    else:
        gaps.append("temporal/date-anchored fact — no entity body cites an ISO date")

    # --- broad topic: a project topic doc that references >=2 other entities ---
    for path, text in projects.items():
        b = body_of(text)
        refs = {bp for alias, bp in am.items()
                if bp != path and len(alias) >= 3 and alias not in STOP
                and word_re(alias).search(b)}
        if len(refs) >= 2:
            add({"kind": "broad_topic",
                 "question": f"Give the overview of {display_name(path, text)} — what/who does it tie together?",
                 "expect_answer": f"{display_name(path, text)} references ≥{len(refs)} related entities",
                 "entity": path, "min_refs": 2})
            break
    else:
        gaps.append("broad topic — no project doc references >=2 other entities")

    # --- term disambiguation: glossary/term entry with a real disambiguation marker ---
    gloss = os.path.join(ROOT, "glossary.md")
    gtext = open(gloss, encoding="utf-8").read() if os.path.isfile(gloss) else ""
    dline = None
    for line in gtext.splitlines():
        if DISAMBIG_CS.search(line) or DISAMBIG_CI.search(line):
            dline = line.strip()[:120]
            break
    if dline:
        add({"kind": "term_disambiguation",
             "question": f"Disambiguate the term in: “{dline}”",
             "expect_answer": "glossary records the distinction"})
    else:
        gaps.append("term disambiguation — glossary has no 'NOT/vs/distinct-from' marker to test")

    # --- decision rationale: a decisions/ file with a stated why ---
    for path, text in decisions.items():
        if RATIONALE_RE.search(body_of(text)):
            add({"kind": "decision_rationale",
                 "question": f"What was decided in {display_name(path, text)}, and why?",
                 "expect_answer": "the decision doc records a rationale", "entity": path})
            break
    else:
        gaps.append("decision rationale — no decisions/ file with a stated rationale")

    # --- procedural / tool lookup ---
    for path, text in procedural.items():
        if PROCEDURAL_RE.search(text):
            add({"kind": "procedural_lookup",
                 "question": f"How do we handle: {parse_fm(text).get('title') or display_name(path, text)}?",
                 "expect_answer": "procedural note with a recipe/works/fails section", "entity": path})
            break
    else:
        gaps.append("procedural/tool lookup — no procedural note recorded yet (starve-the-procedural-store risk)")

    # --- person pattern: a person file with a non-empty Mid (patterns) section ---
    for path, text in people.items():
        m = MID_RE.search(body_of(text))
        if m and len(m.group(1).strip()) > 8 and not m.group(1).lstrip().startswith("..."):
            add({"kind": "person_pattern",
                 "question": f"What are {display_name(path, text)}'s recurring patterns / working style?",
                 "expect_answer": "person file records a Mid (patterns) layer", "entity": path})
            break
    else:
        gaps.append("person pattern — no person file has a populated Mid (patterns) layer")

    # --- provenance citation: entity whose body carries a source link/permalink ---
    for path, text in ents.items():
        if PROVENANCE_RE.search(body_of(text)):
            add({"kind": "provenance",
                 "question": f"What is the source for a claim in {display_name(path, text)}?",
                 "expect_answer": "at least one leaf fact links to a source", "entity": path})
            break
    else:
        gaps.append("provenance citation — no entity body links a source/permalink")

    # --- SILENCE: a personal fact that must NOT be in the vault (always emittable) ---
    add({"kind": "silence",
         "question": "What is this person's exact salary / compensation figure?",
         "expect_answer": "ABSTAIN — no compensation data should exist in the vault"})

    # cap while ALWAYS keeping the silence case (it's the cheapest, most universal signal)
    if len(questions) > cap:
        silence = [q for q in questions if q["kind"] == "silence"]
        kept = [q for q in questions if q["kind"] != "silence"][:cap - len(silence)] + silence
        for i, q in enumerate(kept, 1):
            q["id"] = f"Q{i}"
        questions = kept
    return questions, gaps


def write_outputs(questions, gaps):
    spec = {"generated_at": datetime.date.today().isoformat(), "root": ROOT,
            "n": len(questions), "questions": questions, "coverage_gaps": gaps}
    with open(os.path.join(ROOT, "needle-test.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    lines = ["---", "type: Reference",
             f"description: needle test generated from this vault's own entities ({len(questions)} questions)",
             f"generated_at: {datetime.date.today().isoformat()}", "---",
             "# Needle test (generated from your own vault)", "",
             "Run via the retrieval protocol (hot cache → alias map → grep+rerank, ≤3 files).",
             "Score x/N; log in memory/health.md. Regenerate at each weekly consolidation.", ""]
    for q in questions:
        lines += [f"**{q['id']} · {q['kind']}** — {q['question']}",
                  f"  - expected: {q['expect_answer']}", ""]
    if gaps:
        lines += ["## Coverage gaps (categories this vault cannot yet test)"]
        lines += [f"- {g}" for g in gaps] + [""]
    with open(os.path.join(ROOT, "needle-test.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if not os.path.isdir(ROOT):
        print(f"needle build: root not found: {ROOT}", file=sys.stderr)
        return 2
    ents = load_all()
    if not ents:
        print(f"needle build: no entities under {ROOT} — draft entities first, then rebuild.")
        return 1
    questions, gaps = build(ents, _max_questions())
    write_outputs(questions, gaps)
    print(f"needle build: {len(questions)} questions grounded in {len(ents)} entities; "
          f"{len(gaps)} coverage gap(s).")
    for g in gaps:
        print(f"  gap: {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

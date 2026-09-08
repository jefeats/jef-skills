#!/usr/bin/env python3
"""memory-v2 index + health generator. Stdlib only. Run from workspace root:
   python3 memory/scripts/generate_index.py [--migrate-frontmatter] [--root=PATH]
Generates memory/index.md (entity tables + alias map) and memory/health.md (staleness, hygiene).
Root resolution (portability contract): MEMORY_ROOT env -> --root= arg -> script-relative.
"""
import os, re, sys, datetime, unicodedata

def _resolve_root():
    if os.environ.get("MEMORY_ROOT"):
        return os.environ["MEMORY_ROOT"]
    for arg in sys.argv[1:]:
        if arg.startswith("--root="):
            return arg.split("=", 1)[1]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # memory/

ROOT = _resolve_root()
ENTITY_DIRS = ["people", "projects", "teams", "decisions", "procedural/tools", "personal"]
TODAY = datetime.date.today()
STALE_DAYS = 90

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def parse_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            fm[k.strip()] = v
    return fm, text[m.end():]

def derive_frontmatter(path, body):
    """One-time migration: build YAML frontmatter for v1 entity files."""
    name = None
    m = re.search(r"^# (.+)$", body, re.M)
    if m: name = m.group(1).strip()
    fname = os.path.splitext(os.path.basename(path))[0]
    name = name or fname
    etype = ("person" if "/people/" in path else
             "project" if "/projects/" in path else
             "team" if "/teams/" in path else
             "decision" if "/decisions/" in path else
             "tool" if "/tools/" in path else "note")
    aliases = {name, fname.replace("-", " ")}
    if etype == "person":
        parts = fname.split("-")
        if len(parts) >= 2:
            aliases.add(parts[0])                              # first name
            aliases.add(f"{parts[0]}.{'-'.join(parts[1:])}@")  # email stem
    lv = "2026-04-30"
    m = re.search(r"Last verified:\*{0,2}\s*(\d{4}-\d{2}-\d{2})", body)
    if m: lv = m.group(1)
    conf = "med"
    m = re.search(r"Confidence:\*{0,2}\s*(\w+)", body)
    if m: conf = m.group(1)
    al = ", ".join(sorted(a for a in aliases if a))
    return f"---\ntype: {etype}\naliases: [{al}]\nsalience: active\nconfidence: {conf}\nlast_verified: {lv}\nsource_kind: human-stated\n---\n"

def collect(migrate=False):
    entities = []
    for d in ENTITY_DIRS:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp): continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".md") or fn == "README.md": continue
            p = os.path.join(dp, fn)
            text = open(p, encoding="utf-8").read()
            fm, body = parse_frontmatter(text)
            if fm is None and migrate:
                fmtext = derive_frontmatter(p, text)
                open(p, "w", encoding="utf-8").write(fmtext + text)
                fm, body = parse_frontmatter(fmtext + text)
            if fm is None: fm = {}
            title = (re.search(r"^# (.+)$", body or text, re.M) or [None, os.path.splitext(fn)[0]])[1]
            entities.append({
                "path": f"{d}/{fn}", "title": title.strip(), "dir": d,
                "type": fm.get("type", "?"),
                "aliases": fm.get("aliases", []) if isinstance(fm.get("aliases"), list) else [fm.get("aliases")] if fm.get("aliases") else [],
                "salience": fm.get("salience", "?"), "confidence": fm.get("confidence", "?"),
                "last_verified": fm.get("last_verified", fm.get("verified_at", "unknown")),
                "description": fm.get("description") if isinstance(fm.get("description"), str) else None,
            })
    return entities

def age_days(datestr):
    try:
        return (TODAY - datetime.date.fromisoformat(str(datestr))).days
    except Exception:
        return 9999

def gen_index(entities):
    # OKF v0.1 index.md: root index may carry frontmatter declaring okf_version;
    # body is sections of "* [Title](url) - description" bullets (spec §6).
    lines = ["---", 'okf_version: "0.1"', "---",
             f"# Memory Index", f"> Generated {TODAY} by scripts/generate_index.py — do not hand-edit.",
             f"> Alias map lives in [aliases.md](/aliases.md).", ""]
    for d, label in [("people", "People"), ("projects", "Projects"), ("teams", "Teams"),
                     ("decisions", "Decisions"), ("procedural/tools", "Tools"), ("personal", "Personal")]:
        rows = [e for e in entities if e["dir"] == d]
        if not rows: continue
        lines += [f"# {label}", ""]
        rows.sort(key=lambda e: (e["salience"] != "core", e["title"]))
        for e in rows:
            desc = e.get("description") or f"{e['type']}; salience {e['salience']}, confidence {e['confidence']}, verified {e['last_verified']}"
            lines.append(f"* [{e['title']}](/{e['path']}) - {desc}")
        lines.append("")
    open(os.path.join(ROOT, "index.md"), "w", encoding="utf-8").write("\n".join(lines))
    # Alias map -> aliases.md (concept doc; kept out of the reserved index.md)
    amap = []
    for e in entities:
        for a in e["aliases"]:
            if a and a.lower() != e["title"].lower():
                amap.append((a, e["path"]))
    alines = ["---", "type: Reference", "title: Alias map",
              "description: Query-expansion table — resolve any mention, nickname, or email handle to an entity file.",
              f"timestamp: {TODAY}", "---", "",
              "# Alias map (query expansion — resolve any mention to a file)", "",
              "| Alias | → Path |", "|---|---|"]
    for a, p in sorted(amap, key=lambda x: x[0].lower()):
        alines.append(f"| {a} | {p} |")
    alines.append("")
    open(os.path.join(ROOT, "aliases.md"), "w", encoding="utf-8").write("\n".join(alines))
    return len(entities), len(amap)

def find_fuzzy_duplicates(entities):
    """Alias-cascade lite (entity-resolution research): flag near-duplicate
    entity names/aliases that may be the same real-world entity."""
    import difflib
    names = {}
    for e in entities:
        for n in [e["title"]] + e["aliases"]:
            if n and len(n) > 3:
                names.setdefault(n.lower(), set()).add(e["path"])
    dupes = []
    keys = sorted(names)
    for i, k in enumerate(keys):
        close = difflib.get_close_matches(k, keys[i + 1:], n=2, cutoff=0.92)
        for c in close:
            if names[k] != names[c]:
                dupes.append((k, sorted(names[k])[0], c, sorted(names[c])[0]))
    return dupes

def gen_health(entities):
    stale = [e for e in entities if age_days(e["last_verified"]) > STALE_DAYS]
    unknown = [e for e in entities if e["last_verified"] == "unknown"]
    inbox_dir = os.path.join(ROOT, "inbox")
    inbox_files = [f for f in os.listdir(inbox_dir) if f.endswith(".md") and f != "README.md"] if os.path.isdir(inbox_dir) else []
    unprocessed = [f for f in inbox_files if "processed" not in f]
    lines = ["---", "type: Status Report", "title: Memory Health",
             f"timestamp: {TODAY}", "---", "",
             f"# Memory Health", f"> Generated {TODAY}.", "",
             f"- Entities indexed: {len(entities)}",
             f"- Stale (> {STALE_DAYS}d unverified — re-verify before citing as current): {len(stale)}",
             f"- Missing last_verified: {len(unknown)}",
             f"- Inbox files awaiting promotion: {len(inbox_files)} ({len(unprocessed)} unprocessed)", ""]
    if stale:
        lines += ["## Re-verify queue", ""]
        for e in sorted(stale, key=lambda e: age_days(e["last_verified"]), reverse=True):
            lines.append(f"- {e['path']} (last verified {e['last_verified']}, {age_days(e['last_verified'])}d)")
        lines.append("")
    dupes = find_fuzzy_duplicates(entities)
    if dupes:
        lines += ["## Possible duplicate entities (alias cascade — fuzzy pass)", "",
                  "_Near-identical names pointing at different files; judge at consolidation._", ""]
        for a, pa, b, pb in dupes[:20]:
            lines.append(f"- `{a}` ({pa}) ≈ `{b}` ({pb})")
        lines.append("")
    lines += ["## Contradiction queue", "", "_Populated at consolidation; empty means none pending._", ""]
    # Preserve heartbeat block across regeneration
    hp = os.path.join(ROOT, "health.md")
    hb = ""
    if os.path.isfile(hp):
        old = open(hp, encoding="utf-8").read()
        m = re.search(r"<!-- HEARTBEAT:BEGIN.*?HEARTBEAT:END -->", old, re.S)
        if m:
            hb = "\n" + m.group(0) + "\n"
    open(hp, "w", encoding="utf-8").write("\n".join(lines) + hb)

if __name__ == "__main__":
    migrate = "--migrate-frontmatter" in sys.argv
    ents = collect(migrate=migrate)
    n, na = gen_index(ents)
    gen_health(ents)
    print(f"indexed {n} entities, {na} aliases; wrote index.md + health.md")

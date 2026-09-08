# memory-os architecture (research-grounded)

## The three-system model (organizing principle; AdMem arXiv:2606.06787)
Human-memory-inspired split, adopted as the explicit frame (2026-07-20, per DS interview-corpus research): **episodic** (what happened — dated, append-only, provenance), **semantic** (what is true — entity wiki, superseded never deleted), **procedural** (how to do things — workflows, tool lessons, recorded FAILURES). Working memory is the regenerated hot cache. Consolidation is the one-way flow: episodic evidence → semantic claims (PersonaTree: evidence → patterns → stable claims) and repeated task friction → procedural notes. Health check: a vault whose procedural store is empty after weeks of tool-heavy sessions has a broken write path, not a lack of lessons.

## Two-tier store (Eywa, arXiv:2605.30771)
- **Tier 0 — immutable evidence:** episodic/ session logs + inbox/ mining captures. Append-only, never edited. Authoritative: derived facts link back here and never replace the source.
- **Tier 1 — canonical beliefs:** entity wiki (people/projects/teams/decisions/glossary) + procedural/. Compact, revisable, every fact carries (source, valid_from, valid_until, supersedes, supersession_reason).

## Four memory types, four stores (Neo4j 3-layer; AdMem arXiv:2606.06787)
|| Type | Store | Lifetime | Written by |
||---|---|---|---|
|| Working | CLAUDE.md hot cache (≤100 lines) | regenerated | consolidation only |
|| Episodic | episodic/ | 30d then distilled, kept as provenance | every session |
|| Semantic | entity wiki | permanent, superseded (never deleted) | promotion gate |
|| Procedural | procedural/ + tools/ | permanent | when workflows/tool lessons learned — record FAILURES + critiques, not just recipes (MemToolAgent arXiv:2606.07909) |

## Fact schema (Engram record, arXiv:2606.09900 + Eywa arXiv:2605.30771 — bi-temporal, frontier-aligned 2026-07-18)
YAML frontmatter per entity declares **two pairs of timestamps** (bi-temporal), not one:

| Field | Time axis | Meaning |
|---|---|---|
| `created_at` | transaction | When *we* wrote the row |
| `verified_at` | transaction | When we last checked it still held |
| `valid_from` | valid | First time the fact was true in the world |
| `valid_until` | valid | When the fact stopped being true (null = still current, Eywa ⊥) |

Plus: `type` (fixed ontology), `aliases` (retrieval backbone: nicknames, email handles), `salience` (core|active|peripheral — retention weight), `confidence` (retrieval weight), `supersedes` (typed pointer to row this replaces; replaces display strikethrough), `supersession_reason` (enum: correction|preference_change|factual_update|scope_change|unknown), `source_kind` (human-stated|mined|inferred; inferred never overrides human-stated). The Eywa invariant holds: **at most one active fact per (entity, predicate, scope_entity) slot**. Supersession happens at write time (consolidator); read path trusts active state.

**Migration path:** `scripts/migrate_bitemp.py` is idempotent and reads existing `last_verified` to back-fill `valid_from` and `verified_at`. Leave `valid_until` null for open entities; back-fill `supersedes` from any `superseded_by` human-readable marker. After migration, `scripts/check_contradictions.py` audits chains >3 hops, loops, and stale `valid_until` rows with `supersession_reason=unknown`.

## Person model (PersonaTree, arXiv:2606.04780)
Root (stable claims) ← Mid (recurring patterns) ← Leaf (dated evidence). Claims without evidence rows cap at confidence: med.

## Rich core, thin tail (KET-RAG, arXiv:2502.09304)
Full profiles for top ~20 people / ~8 projects; one-line stubs for the rest. Stubs are cheap; missing aliases are expensive.

## Dual-process loops (Memory Beyond Recall, arXiv:2606.09483)
System-1 "daytime writer": cheap session-end capture, no heavy processing on the critical path. System-2 "nighttime engine": scheduled consolidation — novelty gate (SAGE, arXiv:2605.30711: route Add/Noop cheaply, judge only ambiguous cases on factual content), cheap-then-escalate contradiction handling, distillation into topic docs (Infini, arXiv:2606.10677), index + hot-cache regeneration, needle-test eval. A memory system whose upkeep depends on the human remembering is designed to rot.

## Governance axes (Always-On survey, arXiv:2606.30306)
Per store define authority/scope/mutability/provenance/recoverability: hot cache = consolidation-only + fully regenerable; wiki = gate-controlled; inbox = anyone writes, nobody trusts; changelog = append-only audit (enables poisoning forensics, arXiv:2606.30566). Forgetting = archive + tombstone, never deletion.

## Why no vector DB
Personal corpora are megabytes ("two floppy discs" — Hornet). On heterogeneous markdown corpora only cross-encoder reranking + query expansion reliably improve retrieval (arXiv:2606.28367) — Claude reranking grep hits IS the cross-encoder; the alias map IS query expansion. Low-k (≤3 files) because plausible-but-wrong distractors degrade agent reasoning up to 80% and you cannot reason your way out of bad context (Hornet "Mutually assured distraction"; "Lost in the Noise"). Abstention is a correct retrieval outcome (Memory Silence, arXiv:2606.06055).

## Always-On alignment (Google Cloud Always-On Memory Agent, 2026-07)
Google's open-source reference implementation (ADK + Gemini 3.1 Flash-Lite) independently validates memory-os's core bet — no vector DB, no embeddings, an LLM reads/thinks/writes structured memory — and contributes four patterns memory-os adopts:
1. **Importance at ingest:** every mined candidate carries importance (high/med/low) so consolidation triages top-down under a time budget (their IngestAgent scores importance per memory).
2. **Consolidation generates connections + insights,** not just fact promotion: their ConsolidateAgent links related memories and writes a synthesized insight while idle. Memory-os: daily micro-consolidation writes cross-memory links into entity/topic docs; the weekly digest includes ≥1 cross-memory insight.
3. **Tiered always-on cadence:** their 30-min loop is overkill for a personal vault, but weekly-only consolidation demonstrably backlogs (~15 candidates/day → 60-90 rows at the Monday gate). Memory-os cadence: session-end (System-1) → daily micro-consolidation (≤10 min, importance-ranked, piggybacks on MINE) → weekly deep pass (System-2).
4. **Memory is a monitored process:** their agent exposes /status; a memory system that can die silently will. Memory-os equivalent: `scripts/heartbeat.py` checks loop *execution* (artifacts produced), not registration, and the protocol block mandates running it at session start. Proven necessary 2026-07-20: both loops dead for 2 days while cron registration checks reported green.
Their governance critique (drift, loops, unbounded writes) maps to memory-os's existing defenses: quarantined inbox, conservative write-rate, append-only audit log, supersede-never-delete.

## OKF conformance (Open Knowledge Format v0.1, Google, 2026-06)
The vault is an OKF knowledge bundle: markdown + YAML frontmatter, `type` required on every non-reserved .md, root `index.md` declares `okf_version: "0.1"` and uses OKF bullet-list sections, `log.md` (or a frontmattered `changelog.md`) records history, cross-links prefer bundle-relative markdown links (`/people/x.md`) — wikilinks remain as a human affordance but new links should be OKF-form. Alias map lives in `aliases.md` (concept doc), keeping the reserved `index.md` spec-clean. `scripts/okf_check.py` validates; run after every consolidation. Payoff: the vault is portable across agent stacks (Claude, Gemini/ADK, anything that can `git clone`) — memory outlives the tool that wrote it. Spec: github.com/GoogleCloudPlatform/knowledge-catalog (okf/SPEC.md).

## Entity-resolution cascade (alias handling; DS interview-corpus research)
Cheapest-first: exact alias-map hit → fuzzy match (difflib in `generate_index.py` flags near-duplicate names in health.md) → LLM arbitration on factual content at consolidation. Recall-first ablation finding: storage completeness (entities + aliases captured) outweighs retrieval-ranking optimisation — grow the alias map aggressively, tune ranking never (until the needle test says otherwise).

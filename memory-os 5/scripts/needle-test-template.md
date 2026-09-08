> AUTO-GENERATED NOW: run `python3 memory/scripts/build_needle_test.py` to emit a
> vault-specific needle test (memory/needle-test.{json,md}); score with
> `run_needle_test.py` (`--smoke` for the 2-question workshop pass). This template
> is the category reference the generator implements — do not hand-hardcode facts.

# Needle Test — build 12 questions from the user's own entities at SETUP
Cover: alias-only lookup x2, 2-hop relation, superseded fact, temporal change, broad topic, term disambiguation, decision rationale, procedural/tool lookup, person-pattern, provenance citation, one SILENCE case (correct = abstain).
Run at every consolidation via the retrieval protocol only; log x/12 + failures in memory/health.md.

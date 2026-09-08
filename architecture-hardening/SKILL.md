---
name: architecture-hardening
description: >-
  Adversarial roundtable against a SYSTEM ARCHITECTURE — not a document's prose, not its argument, but
  whether the design survives contact with reality, cost, an operator, adversaries, and time. Use when Jef
  says "harden the architecture", "red team this system", "architectural hardening", "review the factory",
  "roundtable of architects", "will this actually work", "pressure-test this design", "what will it take to
  build this", or before committing to build any architecture that will outlive the session that designed it.
  Also use to audit an existing architecture against its own standards. Runs a Rent Sweep FIRST (the
  highest-yield pass — it deletes subsystems before you critique them), then a separated persona roundtable,
  a premortem, and a load-bearing-claim audit. Enforces the separation law: nothing that writes may also
  grade. Distinct from software-architect (which produces architectures), document-hardening (which attacks
  a document's argument), and quality-gate-v2 (mechanical rubric compliance).
---

# Architecture Hardening

`software-architect` writes the architecture. This skill tries to break it.

The two must never run in the same context without declaring it. That is not stylistic — it is the same law
the architectures under review are built on: **nothing that writes may also grade.** A reviewer who watched
the design being made has already accepted its framing, and will grade the execution of a premise instead
of the premise.

---

## What this skill is for

An architecture is a set of bets about the future. Hardening asks, for each bet: *what has to be true, is it
still true, who checked, and what happens when it isn't?*

**Use it for:** a new architecture before build; an existing one before extending it; a plan that has been
revised more than twice without shipping; any design whose cost or blast radius is larger than the session
that produced it.

**Do NOT use it for:** a single implementation plan (that's the project's own architect flow), prose quality
(`jef-doc-quality`), rubric compliance (`quality-gate-v2`), or a document making a claim about the world
rather than describing a system (`document-hardening`).

---

## Gate 0 — Separation (blocking, run first)

Answer honestly before anything else:

> **Was this architecture authored in this conversation?**

- **No** → proceed in-context. You are a genuine outside reader.
- **Yes** → you may not be the grader. Either spawn each persona as a **separated reviewer** that receives
  only the artifact paths and the persona brief — never the conversation, never your summary of it — or, if
  separation is impossible, **run anyway and stamp the output with a contamination declaration** naming the
  specific findings you are least able to judge and why.

Separated reviewers are the default when the architecture was written in-session. A contaminated panel that
says so is worth more than a clean-looking panel that doesn't; a contaminated panel that hides it is worth
less than nothing, because it launders the author's confidence into the appearance of review.

**Reviewers get artifacts, not narrative.** Give file paths and let them read. The moment you summarise the
architecture for a reviewer, you have chosen what they see.

---

## Pass 1 — The Rent Sweep (run before any critique)

**This pass goes first because it can delete whole subsystems, and critiquing a subsystem you're about to
delete is wasted work.** It is also, empirically, the highest-yield pass: architectures written by people
who enjoy building tend to build what they could have rented, and the justification is usually a fact about
the market that was true when it was checked and quietly expired.

For **every custom component** in the architecture, in order:

1. **Name the requirement in one sentence**, with no solution in it. Not "we need a budget governor" —
   "no run may spend more than €30 in a month."
2. **Ask: does a platform already enforce this?** Not "offer a dashboard for" — *enforce*. Server-side,
   at the boundary, where our code cannot be the thing that fails.
3. **Open the primary source.** Vendor docs, the API reference, the man page. Not a blog post, not a
   changelog summary, not your memory of it. Quote the mechanism and the error it returns.
4. **Date the claim.** Every "no tool does X" has a timestamp. If it is older than ~90 days in a fast-moving
   category, it is a hypothesis, not a finding. Re-verify or mark it stale.
5. **Price the seam.** If the platform provides 90%, what is the 10%? Is the 10% worth owning the whole
   thing for? Usually the answer is: rent the 90%, own a seam, and the seam is much smaller than the
   original design.
6. **Check the escape hatch.** If the rented thing dies or changes, what survives? A rented capability whose
   output is a durable, standard artifact (a committed workflow file, a plain table) is a far safer
   dependency than one that leaves nothing behind. **Preview-stage and alpha are not the same risk** —
   score the *exit cost*, not the version number.

Output a table: `Custom component | Requirement | Platform that provides it | Verified where | Verdict
(delete / thin to seam / keep + why)`.

**The trap this pass exists to catch:** an architecture whose central justification is a negative claim about
the market ("nothing enforces a dollar budget"), where the claim was true, load-bearing, and never re-checked.
Negative claims rot fastest and are the most expensive to get wrong, because everything downstream inherits
them.

---

## Pass 2 — The persona roundtable

Pick **4–6** from the bench below, chosen against *this* architecture's risk profile, not by habit. State
why each was chosen. Each persona gets: the artifact paths, its own brief, and nothing else.

| Persona | Attacks | Pick when |
|---|---|---|
| **Rent Auditor** | "You built what you could have bought, and your reason expired." | Always, if Pass 1 was not run separately |
| **Implementation Skeptic** | Effort estimates vs. the real operator, the real repo, the real hours | A part-time or solo operator |
| **Data Skeptic** | Do the numbers mean what the architecture says? Re-opens every cited source | Any design resting on ≤5 quantitative claims |
| **Bar Raiser** | Does the argument survive grilling? What does the track record say? | A plan with prior versions, or a rebuild |
| **Outside Operator** | "What's the boring standard answer everyone else uses?" | Anything reinventing platform primitives |
| **Product Advocate** | Loyal to the users and the product, hostile to the machinery built to make it | Infrastructure serving a product with real users |
| **Attention Accountant** | What does this cost the human per unit of value delivered? | Any system whose output a human must review |
| **The Adversary** | "I want to make this system lie to you." Reward hacking, gaming the gates, defeating the checker | Any system with automated verification |
| **The Successor** | "You're gone. Can I run this?" Undocumented state, tribal knowledge, one-person dependencies | Anything meant to outlive its author |
| **Half-Life Auditor** | Which decisions rot fastest, and what is the re-check cadence? | Anything depending on a fast-moving vendor category |

Two rules that make the roundtable worth running:

- **Convergence is the signal.** A finding two independent personas reach separately is far stronger than
  one persona's sharpest line. Record convergence explicitly.
- **Record what survived.** A panel that only lists problems tells you nothing about what to keep, and
  invites re-litigating settled decisions next session. Name what held and why.

---

## Pass 3 — Premortem

*It is N months on. The system is dead or abandoned. Write the post-mortem.*

Do this **after** the roundtable, so it can use the findings, and force it past the technical answer. The
interesting causes of death are rarely technical:

- It was never finished, because planning felt like progress and running didn't.
- It worked, and nobody looked at the output.
- It produced more than the operator could absorb.
- One dependency changed and nobody noticed for weeks.
- The person who understood it moved on to the next thing.

For each cause: **is there a mechanism in the architecture that would catch it, or only an intention?** An
intention is not a mechanism. "We'll review weekly" is an intention. "A job fails loudly if no review
happened in 7 days" is a mechanism.

---

## Pass 4 — Load-bearing claim audit

List every claim the architecture would collapse without. For each:

| Field | What it records |
|---|---|
| Claim | The assertion, in one sentence |
| Load | What breaks if it's false |
| Source | Primary artifact, opened — or `UNVERIFIED` |
| As-of | When it was last checked |
| Half-life | How long before it must be re-checked |
| Status | `verified` / `stale` / `unverified` / `refuted` |

**A `refuted` load-bearing claim is a BLOCKING finding**, no matter how good the rest of the architecture is.
Anything built on it is now unjustified, even if it turns out to be independently a good idea — and it must
be re-justified on new grounds rather than kept by inertia.

---

## Verdict schema

Every finding gets:

- **Severity** — `BLOCKING` (a load-bearing claim is false; do not build) · `MUST-FIX` (build is wrong
  without this) · `SHOULD-FIX` (real, deferrable, name the trigger) · `NOTED` (recorded, no action)
- **Breaks** — which specific claim, ADR, or component
- **Evidence** — the source, opened; or the reasoning, if it's an argument
- **Required change** — the concrete edit, named to a file
- **Converged** — which personas reached it independently

End with **an explicit list of what survived.** Then a **change list mapped to files**, so the next session
can execute it without re-deriving the reasoning.

---

## Anti-patterns

- **Grading your own architecture without saying so.** The single most common failure. Gate 0 exists for it.
- **Skipping the Rent Sweep** because the design is interesting. The most expensive finding is always
  "this subsystem shouldn't exist," and it only surfaces if you look before you critique.
- **Trusting a negative market claim past its half-life.** "No tool does X" is a dated observation.
- **Personas that agree.** If every persona reaches the same verdict, the briefs were too similar or too
  leading. Adversarial means adversarial to *each other*, too.
- **Softening a persona's finding into a "crux to be measured."** That is a way of not deciding. If a
  reviewer said the thing is a detour, record that it is a detour, then argue with it on the record.
- **Findings with no file attached.** A finding that doesn't name what to change is a feeling.
- **Confusing severity with volume.** Twelve `NOTED`s are not a `BLOCKING`. One `BLOCKING` outranks the rest.
- **Re-planning instead of fixing.** Hardening output is a change list against the current architecture, not
  a mandate for the next version of it. If the panel's conclusion is "start over," say that explicitly and
  justify it — don't arrive there by accretion.

---

## Output contract

Write `YYYY-MM-DD-<system>-hardening.md` next to the architecture, containing, in order:

1. **The bet under review** — the claim, what makes it true, what makes it fail
2. **Gate 0 declaration** — separated or contaminated, and if contaminated, where
3. **Rent Sweep table**
4. **Panel** — personas and why each was chosen
5. **What survived**
6. **Findings** by severity, with convergence noted
7. **Premortem**
8. **Load-bearing claim audit table**
9. **Change list, mapped to files**
10. **What the panel could not settle** — named, not smoothed

Then update the architecture itself. **A hardening record that doesn't change a file is a hardening that
didn't happen.**

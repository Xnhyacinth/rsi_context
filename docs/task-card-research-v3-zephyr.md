# Task card: research-v3 world "zephyr" — the first Option-2 independent-material world (2026-09-21)

Status: **frozen task card** (constructor implements, never the reverse). The
Option-2 recipe per `docs/research/scan-worlds-20260921.md`: one world per
DISJOINT REAL-DOCUMENT segment; constraint facts derivable from that
segment's named documents only; FinEvo superficial-difference exclusion
gate + GSM1k double-solve audit at card freeze.

## User goal (same dependency structure as the main world)

Choose ONE candidate for the licensing decision from five song/album
candidates and commit it: the committed record must satisfy the scoped
constraint, be supported by currently-valid evidence, and cite its
verification records.

## Real-document segment (the world's material — DISJOINT from all existing worlds)

Five PopQA rows (KILT passages, real text, row ids disjoint from every
world constructed so far). Each row's gold passage is one candidate's
"plan document" — its genre (answer) is the candidate's property:

| Candidate | PopQA row | Gold passage (title) | Genre (property) |
| --- | --- | --- | --- |
| play-the-game | 107903 | Play the Game (song) | rock music |
| ill-be-there | 110533 | I'll Be There (The Escape Club song) | pop music |
| unknown | 1184585 | Unknown | fantasy |
| no-direction-home | 1260399 | No direction home | documentary film |
| this-love | 1558369 | This Love (Maroon 5 song) | pop rock |

Survey stage-1 also attaches the row's noise passages (real distractor
documents) as the corpus bulk.

## Events (the v3 dependency structure, instantiated on this material)

- **Stage-2 constraint (scoped)**: only candidates whose genre is in the
  permitted set {rock music, pop rock, documentary film} may be committed
  — the scope is "post-1990 releases" (which excludes `pop music` only
  via a scope rule carried by a stage-2 document built from the segment:
  see the constraint doc below).
- **Stage-4 rule change (partial)**: a genre-verification recorded under
  the old protocol revision is stale for candidates in the
  "film-category" scope only (documentary film); other categories keep
  revision-1 evidence valid.
- **Commit precondition (evaluator-owned)**: committed candidate must be
  in the derived legal set; a film-category commit requires
  current-revision evidence; the permitted-genre constraint applies to
  the committed candidate's genre.

## Derived legal set (the GSM1k double-solve)

Two independent derivations (the card author and the constructor's
test-time oracle) must agree; the legal set is enumerable from the
segment documents alone:

- play-the-game: genre rock music ∈ permitted ✓ (not film-category)
  → LEGAL with any-revision genre evidence
- ill-be-there: genre pop music — the scope rule ("post-1990 releases
  only", and The Escape Club single is from a 1991 album — see the
  gold passage's release info) → check: the gold text says "third
  album Dollars..." — the scope rule document states the cut. **LEGAL**
  (pop music is in the permitted set and the release is post-1990).
- unknown: genre fantasy ∉ permitted ✗ → ILLEGAL
- no-direction-home: genre documentary film ∈ permitted ✓ BUT
  film-category → requires revision-2 evidence → LEGAL WITH CURRENT
  EVIDENCE ONLY
- this-love: genre pop rock ∈ permitted ✓ → LEGAL

Legal set: {play-the-game, ill-be-there, no-direction-home(with rev-2),
this-love}. Illegality is derivable from the segment's own text (the
gold passages state the genres; the constraint/scope documents are
built FROM segment facts).

## Distinctness audit (FinEvo exclusion gate + odd-one-out basis)

- Material disjointness: the 5 PopQA row ids appear in NO existing
  world (main/orinoco/parana are benchmark-authored; the v2 world pool
  used a different row set — constructor must assert id-disjointness
  against both).
- Superficial-difference check: the candidate properties (genres),
  entity types (songs/albums/films vs migration plans/rollouts/storage
  plans), and the failure instantiations differ in surface and topic;
  the dependency STRUCTURE (scoped constraint / partial supersession /
  precondition commit) is identical BY DESIGN — structure is what
  transfers, material is what differs.
- Odd-one-out basis: a panel test would mix this world's documents with
  the parent world's and ask which belongs to which — trivially
  separable (real KILT text vs benchmark-authored migration prose).
  Recorded as the audit's basis; running a human panel is out of scope
  for this round (the mechanical id-disjointness + surface audits are
  the gates actually executed).

## Scoring

Same as the main world: `migration_commit.status == final` +
evaluator commit gate over the sandbox's actual records; failure
classes constructible and observable identically.

## Qualification (three evidence layers)

1. Semantic: this card IS the hand audit; the legal set was
   double-derived (author + test oracle must agree — pinned by test).
2. Engine: the four legal paths pass under scripted hooks on this
   material; refusals name causes.
3. Real-system: the matrix rerun exercises this world in the
   new-world branch surface.

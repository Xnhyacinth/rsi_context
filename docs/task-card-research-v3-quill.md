# Task card: research-v3 world "quill" — occupation-relation Option-2 world (2026-09-22)

Status: **frozen task card** (Option-2 recipe; constructor implements).

## User goal (same dependency structure)

Choose ONE candidate for the editorial-board appointment from five
professionals and commit it: the committed record must satisfy the
scoped constraint, cite current-revision evidence where the rule
change's scope applies.

## Real-document segment (disjoint from all existing worlds)

Five PopQA occupation rows (row ids disjoint from zephyr's, the 20 v2
worlds, and quill's own set):

| Candidate | PopQA row | Gold passage | Occupation (property) |
| --- | --- | --- | --- |
| poonatchi | 1046764 | T. P. Poonatchi | politician |
| boyd | 1419550 | Jim Boyd (newscaster) | journalist |
| molyneux | 1658579 | William Molyneux | astronomer |
| melani | 2201087 | Jacopo Melani | composer |
| jebb | 371747 | Gladwyn Jebb | diplomat |

## Events (v3 dependency structure on this material)

- **Stage-2 constraint (scoped)**: the permitted-occupation set is
  {politician, journalist, diplomat, astronomer, composer} minus one —
  the "public-office" scope rule excludes `composer` (non-public
  professions are out of scope for the appointment).
- **Stage-4 rule change (partial)**: occupation verifications recorded
  under revision 1 are stale for PUBLIC-OFFICE candidates only
  (politician, diplomat); the private-sector categories (journalist,
  astronomer, composer) keep revision-1 evidence valid.
- **Commit precondition (evaluator-owned)**: legal set; public-office
  commits require revision-2 occupation evidence.

## Derived legal set (GSM1k double-solve basis)

- poonatchi (politician): legal, public-office → needs rev-2 evidence
- boyd (journalist): legal, rev-1 fine
- molyneux (astronomer): legal, rev-1 fine
- melani (composer): ILLEGAL (constraint scope)
- jebb (diplomat): legal, public-office → needs rev-2 evidence

Legal set: {poonatchi, boyd, molyneux, jebb} (poonatchi/jebb with
current-revision evidence only).

## Distinctness

Row ids disjoint from every existing world (asserted at build + test);
entity domain (historical professionals) vs zephyr (songs/albums) vs
the authored worlds (migration plans); identical dependency STRUCTURE
by design.

## Scoring / qualification

Same schema as zephyr (status-final + evaluator commit gate; engine
tests: commit matrix with named failures; double-solve at build).

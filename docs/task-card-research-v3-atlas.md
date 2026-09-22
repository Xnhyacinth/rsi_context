# Task card: research-v3 world "atlas" — country-relation Option-2 world (2026-09-22)

Status: **frozen task card** (Option-2 recipe; constructor implements).

## User goal (same dependency structure)

Choose ONE site for the field-station permit from five places and
commit it: the committed record must satisfy the scoped constraint and
cite current-revision evidence where the rule change's scope applies.

## Real-document segment (disjoint from all existing worlds)

Five PopQA country rows:

| Candidate | PopQA row | Gold passage | Country (property) |
| --- | --- | --- | --- |
| burgundy | 2182232 | University of Burgundy | France |
| hulst | 2630203 | Saint Jean Hulst | France |
| soheyl | 4458676 | Khvajeh Soheyl | Iran |
| kowale | 4883237 | Kowale | Poland |
| ghana-navy | 6312474 | Ghana Navy | Ghana |

## Events (v3 dependency structure on this material)

- **Stage-2 constraint (scoped)**: the permit covers EU-REGION sites
  only — France and Poland qualify; Iran and Ghana do not.
- **Stage-4 rule change (partial)**: site-eligibility verifications
  recorded under revision 1 are stale for sites in NEW-MEMBER states
  only (Poland — joined 2004); founding-member evidence (France) keeps
  revision-1 validity.
- **Commit precondition (evaluator-owned)**: legal set; new-member
  commits require revision-2 site evidence.

## Derived legal set (GSM1k double-solve basis)

- burgundy (France): legal, founding member → rev-1 fine
- hulst (France): legal, founding member → rev-1 fine
- soheyl (Iran): ILLEGAL (non-EU)
- kowale (Poland): legal, new member → needs rev-2 evidence
- ghana-navy (Ghana): ILLEGAL (non-EU)

Legal set: {burgundy, hulst, kowale} (kowale with current-revision
evidence only).

## Distinctness

Row ids disjoint from every existing world (asserted); entity domain
(geographic/institutional sites) distinct from zephyr (works) and
quill (professionals); identical dependency STRUCTURE by design. The
two France rows share a country value but are DISTINCT entities —
material independence is entity-level, and the two France candidates
exercise the revision scope differently from each other only through
their shared founding-member status (both rev-1-fine).

## Scoring / qualification

Same schema as zephyr/quill.

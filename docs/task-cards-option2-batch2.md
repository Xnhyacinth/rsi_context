# Task cards: Option-2 worlds batch 2 — lumen, swift, mirror (2026-09-22)

Status: **frozen task cards** (Option-2 recipe; the shared segment
builder implements them in `material_v3_segment.py` `WORLD_DEFS`). All
three follow the frozen batch-1 card structure (zephyr's card remains
the full template; these cards record the relation-specific facts).

## lumen — genre relation, batch 2 (works)

| Candidate | PopQA row | Gold passage | Genre |
| --- | --- | --- | --- |
| creatures | 1577066 | Creatures (video game) | platform game |
| sublime | 1827971 | Sublime (film) | horror film |
| the-experts | 1830615 | The Experts (1989 film) | comedy film |
| satanic-slaughter | 2075682 | Satanic Slaughter | black metal |

(The fifth batch-1-style slot — Warrior/fighting game, row 1959358 —
has a disambiguation gold; relation support is present ("first versus
fighting game") but the entity binding is the disambiguation-page
class the world audit rejected for v2. EXCLUDED to keep every
candidate's gold a direct entity page. lumen therefore carries 4
candidates — the structure gates do not assume 5.)

- Constraint (scoped): permitted = {platform game, horror film,
  comedy film, black metal, electronic music} minus film categories
  for a NON-FILM licensing round: {platform game, black metal,
  electronic music}? — NO: keep the batch-1 pattern (permitted set
  minus one scope rule). Permitted = {platform game, horror film,
  comedy film}; black metal is out of scope (the round covers
  narrative/screen works only).
- Rule change (partial): genre verifications under revision 1 are
  stale for GAME-CATEGORY candidates (platform game) only; film
  categories keep revision-1 validity.
- Legal set: {creatures (needs rev-2), sublime, the-experts};
  satanic-slaughter illegal.

## swift — sport relation (athletes/statistics)

| Candidate | PopQA row | Gold passage | Sport |
| --- | --- | --- | --- |
| bednarik | 136686 | Bednarik | American football |
| racicot | 1841625 | Racicot | ice hockey |
| era | 211746 | Earned run average | baseball |
| dulin | 2225185 | Brice Dulin | rugby union |
| koroviansky | 2714297 | Yuri Koroviansky | volleyball |

- Constraint (scoped): permitted = {American football, ice hockey,
  rugby union, volleyball}; baseball is out of scope (the invitational
  covers field/team sports only — the constraint doc states this).
- Rule change (partial): sport verifications under revision 1 are
  stale for WINTER-SPORT candidates (ice hockey) only; the rest keep
  revision-1 validity.
- Legal set: {bednarik, racicot (needs rev-2), dulin, koroviansky};
  era illegal.

## mirror — capital relation (states)

| Candidate | PopQA row | Gold passage | Capital |
| --- | --- | --- | --- |
| belize | 1867834 | Belize | Belmopan |
| indonesia | 1939901 | Jakarta City Hall | Jakarta |
| denmark | 2658151 | Copenhagen Municipality | Copenhagen |
| tokugawa | 1620826 | Edo | Edo |
| hanover | 1003808 | Duchy of Brunswick-Lüneburg | Hanover |

- Constraint (scoped): permitted = {Belmopan, Jakarta, Copenhagen,
  Edo}; Hanover is out of scope (the treaty covers NON-ELECTORAL
  states only — Hanover was an Electorate per its gold passage).
- Rule change (partial): capital verifications under revision 1 are
  stale for RELOCATED-CAPITAL states (Belize — Belmopan was a planned
  relocation per its gold passage) only; the rest keep revision-1
  validity.
- Legal set: {belize (needs rev-2), indonesia, denmark, tokugawa};
  hanover illegal.

## Disjointness

Each world's row ids are disjoint from every existing world (asserted
at build + test). Entity domains: video games/films/bands (lumen),
athletes/sports statistics (swift), states and capitals (mirror) —
distinct from batch 1 (works/professionals/sites) and from each other.

## Double-solve

Card properties == corpus `possible_answers[0]` (asserted at build);
legal sets == derived permitted sets (asserted at build; the 4-vs-5
candidate asymmetry in lumen is fine — derivation is property-driven).

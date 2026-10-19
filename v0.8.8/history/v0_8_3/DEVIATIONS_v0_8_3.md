# Deviations from DECLARED_v0_8_3.json (scored as frozen; not re-scored)

Scored run: 47/48 tests and 40/41 mutants MATCH. Both mismatches have one cause.

## E1 — T26 objector mispredicted (check order)

- **Declared:** attestation refused with "not the consequence of signed readings" (the
  final state comparison, as in v0.8.2).
- **Measured:** attestation refused earlier, inside the replay:
  `record fields differ from the replay: ['prior_character_snapshot']`.
- **Cause:** v0.8.3's full record check (the fix for ChatGPT round 3 F2) runs during the
  replay. The organism's record honestly snapshots the character it applied from,
  formality 0.99, and the replay holds 0.5. So the refusal happens there, before the final
  comparison is reached.
- **Same class as v0.8's T17:** a new or earlier check catches the same tamper first.
- **Diagnostic, not scored** (`diagnostic_T26_v0_8_3.py` → `DIAGNOSTIC_T26_v0_8_3.txt`): with
  the actual objector, every other T26 assertion holds. The witness stays at 0, the state
  does not load, and formality 0.99 is preserved as evidence. The property ChatGPT's
  round-2 #3 required still holds.
- **Knock-on (the second mismatch):** XD4a's declared exact kill set included T26. T26 no
  longer passes on the candidate, so it cannot count as newly failing. The measured set is
  the declared set minus T26.
- **Correction:** goes in the next frozen declaration. Not edited here.

## Observation (not a deviation)

For an unsigned change in another category, the owner now sees "record fields differ from
the replay: prior_character_snapshot". That is accurate, but harder to read than "not the
consequence of signed readings". A clearer message would name the category whose
before-value differs.

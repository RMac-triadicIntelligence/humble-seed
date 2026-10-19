Grok, claims battery (humble_seed_v0_8_6_CLAIMS.zip), relayed by Rusty 2026-10-19 10:36 CT, verbatim.
The filled-in battery file and CLAIMS_RESULTS_v0_8_6.json were not received with the relay.

Humble Seed v0.8.6 claims battery (Python 3.10.21, cryptography 50.0.1)
  O1                           HOLDS
  O2                           HOLDS
  O3                           HOLDS
  O4                           HOLDS
  O5                           HOLDS
  O6                           HOLDS
  I1                           HOLDS
  I2                           HOLDS
  C1                           HOLDS
  C2                           HOLDS
  C3                           HOLDS
  M1                           HOLDS
  R30a                         HOLDS
  R30b                         HOLDS
  R30c                         HOLDS
  R31a                         HOLDS
  R31b                         HOLDS
  R31c                         HOLDS
  R32a                         HOLDS
  R32b                         HOLDS
  R33a                         HOLDS
  R33b                         HOLDS WITH CAVEATS
  R34                          HOLDS
  W1                           HOLDS
  Q1                           NOT FOUND
  Q2                           NOT FOUND
  extra_generation_monotonic   HOLDS
written CLAIMS_RESULTS_v0_8_6.json
Filled-in battery and results are attached.
Summary of checks Every claim was exercised by running code against the candidate (helpers + direct calls, monkey-patches of _durable_write / os to simulate post-replace and pre-land failures, threads for lock behaviour, reloads for staleness, manual pending intents for recovery).
	•	Most claims hold exactly as written.
	•	R33b is HOLDS WITH CAVEATS: an answer through a stale object reaches the owner ledger (authoritative) and raises StaleOrganism on the organism path; the organism does not persist the answer.
	•	Q1 / Q2: no interleaving or interrupted-save scenario was found that loses a saved update, leaves an unresolvable witness/file pair, produces an unsignable state, or allows an unapproved sign-off. Generation CAS + organism lock + verify-on-recover prevent the obvious races.
Python 3.10.21 · cryptography 50.0.1.

# Independent GTT Safety Review — 2026-10-28

## Changes in this review

1. **GTT identity after an ambiguous submission**
   - Snapshot existing GTT IDs before submitting a new GTT.
   - Persist that snapshot in the `OrderUnknown` metadata so the live engine can use it during later reconciliation and after restart.
   - Resolve only when exactly one matching GTT has appeared since the snapshot. Existing matching GTTs and multiple candidates are not adopted.
   - If no safe identity can be established, the order remains unresolved and the engine does not guess.

2. **Triggered GTT with delayed/missing child order**
   - `triggered` without a visible child is now `UNKNOWN`, not `OPEN`.
   - A GTT in that state cannot be cancelled as if it were still an active trigger.
   - The engine does not adopt an `UNKNOWN` order as confirmed protection. It flags the position as protection-uncertain, sends a critical alert, and blocks new entries.

3. **Regression coverage**
   - Added tests for pre-existing parameter-identical GTTs, multiple newly matching GTTs, ambiguous submission inventory persistence, triggered GTTs without child visibility, and engine behavior for unknown stop state.

4. **Documentation**
   - Updated the order-lifecycle safety table, the Kite-specific limitations, and the documented test count.

## Verification

- `PYTHONPATH=. pytest -q`: **87 passed**.
- `PYTHONPATH=. python -m unittest discover -s tests -q`: **87 passed**.
- `python -m compileall -q tradebot`: passed.

## Important limitations

- This is a source-level change and simulated-test verification only. The Kite adapter has not been validated against a live Zerodha account in this environment.
- The exact GTT response schema, child-order visibility timing, cancellation behavior, and holdings/positions interaction still require controlled broker verification.
- No real NSE historical-data comparison has been performed here. Strategy profitability remains ungraded.
- Do not enable live automated trading based solely on these test results.

## Merge notes (applied on top of 56bbb21)

- Applied unchanged as its own commit; only the README test-count line conflicted.
- One follow-up change: `UNKNOWN` also results from a single failed status read, so
  the immediate persistent block turned any network blip into a manual-reset halt.
  Now an `UNKNOWN` stop pauses entries at once (self-clearing via `unprotected()`)
  and escalates to the persistent block plus CRITICAL alert only if it lasts longer
  than `RESOLVE_SECONDS` (120s). The review's two engine tests were updated to
  assert both stages; a new test covers the transient case.
- Merged suite: 102 tests pass; 20-seed fault soak unchanged (the paper broker
  doesn't produce triggered-without-child GTTs, so those paths rely on the unit tests).


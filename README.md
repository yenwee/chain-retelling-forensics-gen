# chain-retelling-forensics -- data generator

This repository contains the deterministic data generator for the **Chain Retelling Forensics** benchmark (a synthetic NLP / structured-extraction challenge hosted on [Shipd](https://shipd.ai)).

It is published here for **provenance transparency** so that reviewers, solvers, and readers can verify how the synthetic corpus is constructed. Running the generator produces a byte-identical `data.csv` on any machine with Python 3.10+.

## What the challenge is

A 6-step chain of shift-handover retellings is produced from a canonical original message. Each retelling step may be a pure surface paraphrase (meaning preserved) or may inject one bounded content-level distortion. Seven distortion categories are tracked:

| Category | What changes |
|---|---|
| `role_swap` | Reporter and responder are interchanged, or one named individual is replaced by a different one |
| `numeric_error` | A pressure (±7-15%), temperature (±7-15%), or sensor count (±1) is changed |
| `quantifier_drift` | A quantifier token is replaced by a neighbouring one (e.g. `all` → `most`, never `all` → `none`) |
| `temporal_shift` | A time-of-day is shifted by 30-60 minutes, or a shift label is changed |
| `insertion` | A short fabricated clause is appended |
| `deletion` | A full sentence is removed |
| `negation_flip` | The alarm-state polarity is flipped |

For each chain, the ground truth records the earliest step 1..6 at which each category first appeared (or -1 if it never did). The benchmark task is to recover this seven-entry drift-log from the 6-step chain alone.

## Design properties (why the challenge is hard)

Three mechanisms are built into the generator to prevent rule-based shortcut solutions:

1. **Phantom paraphrase ops** -- every retelling step applies meaning-preserving surface variations that mimic drift fingerprints. Numbers may be re-formatted (`2 sensors` ↔ `a pair of sensors`), times may be re-formatted (`14:30` ↔ `around 2:30 PM` ↔ `1430 hours`), quantifier synonyms may swap (`all of` ↔ `every one of`), and alarm phrasing may vary between multiple affirmative and negative forms. A solution that flags every surface change as drift will massively over-fire.

2. **Out-of-distribution vocabulary partition** -- each chain is pre-assigned to a `train` or `test` partition in the generator. Test chains are guaranteed to contain at least one slot value (a name, role, equipment label, or component label) drawn from a pool reserved exclusively for test. Train-only names (`Rossi`, `Mueller`, `Dubois`) and test-only names (`Okonkwo`, `Hossain`, `Martinez`) are disjoint, and similar splits apply to equipment, components, and one role. Solutions that memorize specific vocabulary surface forms will not transfer.

3. **Subtle drift magnitudes** -- numeric errors are bounded to 7-15% (not 20-40%); quantifier drifts only move within tight neighbourhoods (`all` ↔ `most`, never `all` ↔ `none`); temporal shifts are 30-60 minutes (not 2-3 hours). Detection thresholds that would catch gross drift do not catch subtle drift.

## What is in this repo

- `generate_chains.py` -- the full generator. Uses only Python stdlib (`random`, `hashlib`, `csv`, `dataclasses`, `pathlib`). No third-party libraries.
- `README.md` -- this file.

**What is NOT in this repo**, by design:
- The generated `data.csv`.
- The challenge description, `prepare.py`, `grade.py`, rubrics, solutions, or any other challenge artifact.
- Anything that would leak a private answer key or help solvers on the live leaderboard.

If you want to regenerate the corpus locally, clone this repo and run the generator.

## How to reproduce `data.csv`

```bash
git clone https://github.com/yenwee/chain-retelling-forensics-gen.git
cd chain-retelling-forensics-gen
python3 generate_chains.py
```

This writes `data.csv` next to `generate_chains.py`. The file has 12,000 rows and roughly 33 MB.

The generator is fully deterministic: fixed seed 42, stable iteration order, sorted output by `id`. Running twice produces byte-identical files (verify with `md5 data.csv` on macOS or `md5sum data.csv` on Linux).

## Output schema

Each row describes one chain:

| Column | Type | Notes |
|---|---|---|
| `id` | str | 12-character lowercase hex, unique per chain |
| `step_1` .. `step_6` | str | The six retellings, in order |
| `original_message` | str | The canonical narrative before step_1 |
| `first_role_swap` | int | Earliest step 1..6 of role_swap, or -1 |
| `first_numeric_error` | int | Earliest step 1..6 of numeric_error, or -1 |
| `first_quantifier_drift` | int | Earliest step 1..6 of quantifier_drift, or -1 |
| `first_temporal_shift` | int | Earliest step 1..6 of temporal_shift, or -1 |
| `first_insertion` | int | Earliest step 1..6 of insertion, or -1 |
| `first_deletion` | int | Earliest step 1..6 of deletion, or -1 |
| `first_negation_flip` | int | Earliest step 1..6 of negation_flip, or -1 |
| `n_drifts_total` | int | Convenience: total distinct drift categories present (0..4) |
| `split` | str | Pre-assigned partition: `train` or `test` |

## Generator design notes

- **Slot-based realization**: each narrative is assembled from a closed vocabulary of shifts, names, roles, equipment, components, states, actions, issues, periods, plus numeric slots (pressure, temperature, sensor count) and a boolean alarm flag.
- **Four surface templates**: each step is rendered via one of four top-level sentence templates, all conveying the same information.
- **Phantom surface variation**: inside each template, phantom ops fire: number-formatting, time-formatting, quantifier-synonym, alarm-phrase-variant, and occasional filler clauses. None of these are labeled as drift.
- **Drift step**: when a drift category is scheduled for a step, the corresponding mutator modifies one slot (or appends/removes text, for insertion/deletion). Slot mutation propagates through subsequent steps, which is why we record only the **first** step at which a drift category enters the chain.
- **Drift schedule**: a chain has 0..4 distinct drift categories (weighted distribution 20% / 25% / 26% / 20% / 10%). Each scheduled category is assigned to a unique step index from a shuffled pool.
- **Partition assignment**: each chain is pre-tagged `train` or `test` before slot sampling. Test chains force at least one slot onto a TEST_ONLY pool, guaranteeing OOD presence.
- **Determinism**: each chain derives its own RNG from `random.Random(SEED + idx)`, so chains are independently reproducible and ordering is stable.

## License

Code in this repository is released under the MIT License. The generated corpus is released under CC0.

## Provenance note

This generator was written for a benchmark submitted to Shipd's Project Eris. The challenge name in this repo (`chain-retelling-forensics`) matches the challenge slug used on the platform. The generator is published here ahead of and alongside the challenge listing to document exactly how the synthetic data is constructed. No real-world institutions, products, or individuals are referenced by the generator.

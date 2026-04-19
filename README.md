# chain-retelling-forensics -- data generator

This repository contains the deterministic data generator for the **Chain Retelling Forensics** benchmark (a synthetic NLP / structured-extraction challenge hosted on [Shipd](https://shipd.ai)).

It is published here for **provenance transparency** so that reviewers, solvers, and readers can verify how the synthetic corpus is constructed. Running the generator produces a byte-identical `data.csv` on any machine with Python 3.10+.

## What the challenge is

A 6-step chain of shift-handover retellings is produced from a canonical original message. Each retelling step may be a pure surface paraphrase (meaning preserved) or may inject one bounded content-level distortion of one of seven categories:

| Category | What changes |
|---|---|
| `role_swap` | Reporter and responder are interchanged, or one named individual is replaced by a different one |
| `numeric_error` | A pressure, temperature, or sensor-count value is changed |
| `quantifier_drift` | A quantifier word (all / most / several / two / three / none) is replaced |
| `temporal_shift` | A time-of-day or shift label is changed |
| `insertion` | A short fabricated clause is appended |
| `deletion` | A full sentence is removed |
| `negation_flip` | An affirmative statement is flipped to negative (or vice versa) |

For each chain, the ground truth records the earliest step 1..6 at which each category first appeared (or -1 if it never did). The benchmark task is to recover this seven-entry drift-log from the 6-step chain alone.

## What is in this repo

- `generate_chains.py` -- the full generator. Uses only Python stdlib (`random`, `hashlib`, `csv`, `dataclasses`, `pathlib`, `re`). No third-party libraries.
- `README.md` -- this file.

**What is NOT in this repo**, by design:
- The generated `data.csv`.
- The challenge description, `prepare.py`, `grade.py`, rubrics, solutions, or any other challenge artifact.
- Anything that could leak a private answer key or help solvers on the live leaderboard.

If you want to regenerate the corpus locally, clone this repo and run the generator.

## How to reproduce `data.csv`

```bash
git clone https://github.com/yenwee/chain-retelling-forensics-gen.git
cd chain-retelling-forensics-gen
python3 generate_chains.py
```

This writes `data.csv` next to `generate_chains.py`. The file has 12,000 rows and ~32 MB.

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

## Generator design

- **Slot-based realization**: each narrative is assembled from a closed vocabulary of shifts, names, roles, equipment, components, states, actions, issues, periods, plus numeric slots (pressure, temperature, sensor count) and a boolean alarm flag.
- **Paraphrase step**: a retelling re-realizes the current slots into one of two top-level templates. This changes the surface wording without changing any slot value.
- **Distortion step**: when a drift category is scheduled for a step, the corresponding mutator modifies one slot (or appends/removes text, for insertion/deletion). Once a slot mutates, the new value propagates through every subsequent step, which is why we record only the **first** step at which a drift category enters the chain.
- **Drift schedule**: a chain has 0..4 distinct drift categories (weighted distribution). Each scheduled category is assigned to a unique step index from a shuffled pool.
- **Determinism**: each chain derives its own RNG from `random.Random(SEED + idx)`, so chains are independently reproducible and ordering is stable.

## License

Code in this repository is released under the MIT License. The generated corpus is released under CC0.

## Provenance note

This generator was written for a benchmark submitted to Shipd's Project Eris. The challenge name in this repo (`chain-retelling-forensics`) matches the challenge slug used on the platform. The generator is published here ahead of and alongside the challenge listing to document exactly how the synthetic data is constructed. No real-world institutions, products, or individuals are referenced by the generator.

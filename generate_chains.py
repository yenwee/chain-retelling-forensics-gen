"""Deterministic synthetic generator for chain-retelling-forensics.

Produces data.csv with N rows. Each row:
  id, step_1..step_6, original_message,
  first_role_swap, first_numeric_error, first_quantifier_drift,
  first_temporal_shift, first_insertion, first_deletion, first_negation_flip,
  n_drifts_total

Deterministic: fixed seed 42, sorted everywhere, byte-identical on re-run.
No external libraries beyond stdlib.
"""

from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SEED = 42
N_CHAINS = 12000
CHAIN_STEPS = 6

DRIFT_TYPES = [
    "role_swap",
    "numeric_error",
    "quantifier_drift",
    "temporal_shift",
    "insertion",
    "deletion",
    "negation_flip",
]

NAMES = sorted([
    "Smith", "Lee", "Kim", "Patel", "Garcia", "Ahmed", "Brown", "Ng",
    "Rivera", "Nakamura", "Hassan", "Oduya", "Tanaka", "Chen", "Rossi",
    "Mueller", "Dubois", "Klein", "Silva", "Tran",
])
ROLES = sorted(["operator", "supervisor", "technician", "engineer", "safety officer"])
EQUIP = sorted([
    "compressor A3", "compressor B1", "boiler 2", "chiller 4", "cooling tower 1",
    "feedwater pump", "primary loop pump", "HVAC unit 7", "turbine skid 2",
    "recirc fan B",
])
COMPONENTS = sorted([
    "inlet valve", "discharge valve", "intake filter", "oil filter",
    "vibration sensor", "pressure sensor", "temperature probe",
    "drive belt", "flex coupling", "bearing housing",
])
STATES = sorted(["nominal", "slightly elevated", "off-nominal", "stable but drifting", "near threshold"])
ACTIONS = sorted([
    "reset", "manual bypass", "isolation procedure", "lockout-tagout",
    "flush cycle", "purge sequence", "vent cycle", "torque check",
])
ISSUES = sorted([
    "the temperature spike", "the low-flow alarm", "the vibration excursion",
    "the intermittent trip", "the pressure anomaly",
])
SHIFTS = sorted(["night shift", "day shift", "swing shift"])
PERIODS = sorted(["the first two hours", "the remainder of the watch", "the handover window"])


def hex_id(seed: int, idx: int) -> str:
    h = hashlib.sha1(f"chain-ret-{seed}-{idx}".encode()).hexdigest()
    return h[:12]


@dataclass
class Slots:
    shift: str
    reporter_name: str
    reporter_role: str
    responder_name: str
    responder_role: str
    equipment: str
    time_hhmm: str
    pressure_kpa: int
    temperature_c: int
    component: str
    state: str
    action: str
    issue: str
    period: str
    n_sensors: int
    alarm_triggered: bool
    quantifier: str

    def copy(self) -> "Slots":
        return Slots(**self.__dict__)


def sample_slots(rng: random.Random) -> Slots:
    return Slots(
        shift=rng.choice(SHIFTS),
        reporter_name=rng.choice(NAMES),
        reporter_role=rng.choice(ROLES),
        responder_name=rng.choice(NAMES),
        responder_role=rng.choice(ROLES),
        equipment=rng.choice(EQUIP),
        time_hhmm=f"{rng.randint(0, 23):02d}:{rng.choice([0, 15, 30, 45]):02d}",
        pressure_kpa=rng.randint(80, 240),
        temperature_c=rng.randint(40, 120),
        component=rng.choice(COMPONENTS),
        state=rng.choice(STATES),
        action=rng.choice(ACTIONS),
        issue=rng.choice(ISSUES),
        period=rng.choice(PERIODS),
        n_sensors=rng.choice([2, 3, 4]),
        alarm_triggered=rng.random() < 0.5,
        quantifier=rng.choice(["all", "most", "several", "two", "three"]),
    )


# ---------- Surface realization ----------
# We offer two paraphrase variants per sentence to let "retelling" steps change
# wording without changing meaning. Drift operations change meaning.

def realize(s: Slots, variant: int) -> str:
    alarm = "the alarm triggered" if s.alarm_triggered else "no alarm triggered"
    if variant == 0:
        return (
            f"On {s.shift}, {s.reporter_name} ({s.reporter_role}) walked through {s.equipment}. "
            f"At {s.time_hhmm}, pressure read {s.pressure_kpa} kPa and temperature read {s.temperature_c} C. "
            f"{s.responder_name} ({s.responder_role}) inspected the {s.component}; status was {s.state}. "
            f"{s.quantifier.capitalize()} of the {s.n_sensors} sensors logged the excursion and {alarm}. "
            f"A {s.action} resolved {s.issue} during {s.period}."
        )
    else:
        return (
            f"During the {s.shift}, a walk-through of {s.equipment} was performed by {s.reporter_name} ({s.reporter_role}). "
            f"At {s.time_hhmm}, a pressure reading of {s.pressure_kpa} kPa and temperature of {s.temperature_c} C were recorded. "
            f"The {s.component} was inspected by {s.responder_name} ({s.responder_role}) and found to be {s.state}. "
            f"{s.quantifier.capitalize()} of {s.n_sensors} sensors recorded the event, and {alarm}. "
            f"{s.issue.capitalize()} was addressed with a {s.action} throughout {s.period}."
        )


# ---------- Drift mutators (operate on Slots) ----------

def _swap_name(rng: random.Random, current: str) -> str:
    alternatives = [n for n in NAMES if n != current]
    return rng.choice(alternatives)


def mut_role_swap(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    if rng.random() < 0.5:
        new.reporter_name, new.responder_name = s.responder_name, s.reporter_name
        new.reporter_role, new.responder_role = s.responder_role, s.reporter_role
    else:
        target = rng.choice(["reporter", "responder"])
        if target == "reporter":
            new.reporter_name = _swap_name(rng, s.reporter_name)
        else:
            new.responder_name = _swap_name(rng, s.responder_name)
    return new


def mut_numeric_error(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    which = rng.choice(["pressure", "temperature", "sensors"])
    if which == "pressure":
        delta = rng.choice([-60, -40, -25, 25, 40, 60])
        new.pressure_kpa = max(10, s.pressure_kpa + delta)
    elif which == "temperature":
        delta = rng.choice([-30, -20, -15, 15, 20, 30])
        new.temperature_c = max(5, s.temperature_c + delta)
    else:
        options = [n for n in [2, 3, 4, 5, 6] if n != s.n_sensors]
        new.n_sensors = rng.choice(options)
    return new


def mut_quantifier_drift(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    options = [q for q in ["all", "most", "several", "two", "three", "none"] if q != s.quantifier]
    new.quantifier = rng.choice(options)
    return new


def mut_temporal_shift(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    # choice 1: change the time-of-day
    if rng.random() < 0.6:
        hh, mm = s.time_hhmm.split(":")
        new_hh = (int(hh) + rng.choice([-3, -2, -1, 1, 2, 3])) % 24
        new.time_hhmm = f"{new_hh:02d}:{mm}"
    else:
        alt = [sh for sh in SHIFTS if sh != s.shift]
        new.shift = rng.choice(alt)
    return new


EXTRA_CLAUSES = sorted([
    "A faint rattle was also noted.",
    "An additional vent cycle was logged.",
    "Backup power was confirmed online.",
    "A secondary gauge was cross-checked.",
    "Auxiliary logging was enabled.",
    "An extra witness was recorded.",
])


def mut_insertion(rng: random.Random, s: Slots, text: str) -> str:
    clause = rng.choice(EXTRA_CLAUSES)
    return f"{text} {clause}"


def mut_deletion(rng: random.Random, s: Slots, text: str) -> str:
    # Drop a random full sentence from the message (not first, not last).
    parts = [p.strip() for p in text.split(".") if p.strip()]
    if len(parts) <= 3:
        # fall back to dropping the middle sentence
        if len(parts) == 3:
            parts.pop(1)
        else:
            parts.pop(0)
    else:
        idx = rng.randint(1, len(parts) - 2)
        parts.pop(idx)
    return ". ".join(parts) + "."


def mut_negation_flip(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    new.alarm_triggered = not s.alarm_triggered
    return new


# ---------- Chain construction ----------

def build_chain(idx: int) -> dict:
    rng = random.Random(SEED + idx)
    slots0 = sample_slots(rng)
    variant0 = rng.randint(0, 1)
    m0 = realize(slots0, variant0)

    # Decide drift schedule: pick number of distinct drift types fired.
    n_drifts = rng.choices([0, 1, 2, 3, 4], weights=[20, 25, 25, 20, 10], k=1)[0]
    drift_types_fired = rng.sample(DRIFT_TYPES, k=n_drifts) if n_drifts > 0 else []
    # Assign each drift type to a distinct step in 1..CHAIN_STEPS
    if n_drifts > 0:
        steps_pool = list(range(1, CHAIN_STEPS + 1))
        rng.shuffle(steps_pool)
        drift_steps = {dt: steps_pool[i] for i, dt in enumerate(drift_types_fired)}
    else:
        drift_steps = {}

    # Produce retellings step 1..CHAIN_STEPS
    current_slots = slots0.copy()
    current_text = m0
    steps = []
    for step in range(1, CHAIN_STEPS + 1):
        # Always paraphrase by toggling variant (preserves meaning)
        new_variant = rng.randint(0, 1)
        # Apply slot-level drifts scheduled for this step
        slot_changed = False
        text_mutation: Callable[[str], str] | None = None
        for dt, when in drift_steps.items():
            if when == step:
                if dt == "role_swap":
                    current_slots = mut_role_swap(rng, current_slots)
                    slot_changed = True
                elif dt == "numeric_error":
                    current_slots = mut_numeric_error(rng, current_slots)
                    slot_changed = True
                elif dt == "quantifier_drift":
                    current_slots = mut_quantifier_drift(rng, current_slots)
                    slot_changed = True
                elif dt == "temporal_shift":
                    current_slots = mut_temporal_shift(rng, current_slots)
                    slot_changed = True
                elif dt == "negation_flip":
                    current_slots = mut_negation_flip(rng, current_slots)
                    slot_changed = True
                elif dt == "insertion":
                    text_mutation = lambda t, _rng=rng, _s=current_slots: mut_insertion(_rng, _s, t)
                elif dt == "deletion":
                    text_mutation = lambda t, _rng=rng, _s=current_slots: mut_deletion(_rng, _s, t)

        # Rebuild text from current slots with new variant
        new_text = realize(current_slots, new_variant)
        if text_mutation is not None:
            new_text = text_mutation(new_text)
        steps.append(new_text)
        current_text = new_text

    # First-step per drift type (or -1)
    first = {f"first_{dt}": drift_steps.get(dt, -1) for dt in DRIFT_TYPES}

    row = {
        "id": hex_id(SEED, idx),
        **{f"step_{i}": steps[i - 1] for i in range(1, CHAIN_STEPS + 1)},
        "original_message": m0,
        **first,
        "n_drifts_total": n_drifts,
    }
    return row


def main() -> None:
    out = Path(__file__).parent / "data.csv"
    rows = [build_chain(i) for i in range(N_CHAINS)]
    # Sort by id for determinism
    rows.sort(key=lambda r: r["id"])

    fieldnames = (
        ["id"]
        + [f"step_{i}" for i in range(1, CHAIN_STEPS + 1)]
        + ["original_message"]
        + [f"first_{dt}" for dt in DRIFT_TYPES]
        + ["n_drifts_total"]
    )
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()

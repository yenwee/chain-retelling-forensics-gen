"""Deterministic synthetic generator v2 for chain-retelling-forensics.

Design changes vs v1 (to address reviewer feedback on "too easy" + rule-based risk):

A. PHANTOM PARAPHRASE OPS. Every retelling step also applies 0-2 meaning-
   preserving surface operations that mimic drift fingerprints but are NOT
   labeled as drift. Examples: "2 sensors" <-> "a pair of sensors",
   "14:30" <-> "around 2:30 PM", "all sensors" <-> "every sensor",
   "the alarm did not trigger" <-> "no alarm was raised". These break naive
   rule-based detectors that flag any quantifier/number/time/negation change
   as a drift.

B. OOD VOCABULARY PARTITION. Each chain is pre-assigned to a train/test
   partition in the generator. Test chains use at least one vocabulary item
   (name, role, equipment, or component) that never appears in train. Forces
   generalization rather than memorization. The `split` column in data.csv
   records each chain's assignment; prepare.py honours it.

C. SUBTLER DRIFT MAGNITUDES. Numeric errors now 7-15% rather than 20-40%;
   quantifier drifts only within tight equivalence classes
   (all <-> most, never all <-> none); temporal shifts 30-60 min rather than
   2-3 hours. Detection noise floor rises.

Deterministic: fixed seeds, sorted everywhere, byte-identical on re-run.
No external libraries beyond stdlib.
"""

from __future__ import annotations

import csv
import hashlib
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SEED = 42
N_CHAINS = 12000
CHAIN_STEPS = 6
TEST_FRACTION = 0.20

DRIFT_TYPES = [
    "role_swap",
    "numeric_error",
    "quantifier_drift",
    "temporal_shift",
    "insertion",
    "deletion",
    "negation_flip",
]

# ---------- Vocabulary partitions ----------

SHARED_NAMES = sorted([
    "Smith", "Lee", "Kim", "Patel", "Garcia", "Ahmed", "Brown", "Ng",
    "Rivera", "Nakamura", "Hassan", "Oduya", "Tanaka", "Chen",
])
TRAIN_ONLY_NAMES = sorted(["Rossi", "Mueller", "Dubois"])
TEST_ONLY_NAMES = sorted(["Okonkwo", "Hossain", "Martinez"])

SHARED_ROLES = sorted(["operator", "supervisor", "technician"])
TRAIN_ONLY_ROLES = sorted(["engineer"])
TEST_ONLY_ROLES = sorted(["safety officer"])

SHARED_EQUIP = sorted([
    "compressor A3", "compressor B1", "boiler 2", "chiller 4",
    "cooling tower 1", "feedwater pump", "HVAC unit 7",
])
TRAIN_ONLY_EQUIP = sorted(["primary loop pump", "turbine skid 2"])
TEST_ONLY_EQUIP = sorted(["recirc fan B", "condenser unit C"])

SHARED_COMPONENTS = sorted([
    "inlet valve", "discharge valve", "intake filter", "oil filter",
    "vibration sensor", "pressure sensor", "temperature probe",
])
TRAIN_ONLY_COMPONENTS = sorted(["drive belt", "flex coupling"])
TEST_ONLY_COMPONENTS = sorted(["bearing housing", "labyrinth seal"])

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
    time_hh: int
    time_mm: int
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


def sample_slots(rng: random.Random, partition: str) -> Slots:
    """Draw slot values. Test chains sample at least one TEST_ONLY item."""
    if partition == "train":
        names = SHARED_NAMES + TRAIN_ONLY_NAMES
        roles = SHARED_ROLES + TRAIN_ONLY_ROLES
        equip = SHARED_EQUIP + TRAIN_ONLY_EQUIP
        comps = SHARED_COMPONENTS + TRAIN_ONLY_COMPONENTS
        return Slots(
            shift=rng.choice(SHIFTS),
            reporter_name=rng.choice(names),
            reporter_role=rng.choice(roles),
            responder_name=rng.choice(names),
            responder_role=rng.choice(roles),
            equipment=rng.choice(equip),
            time_hh=rng.randint(0, 23),
            time_mm=rng.choice([0, 15, 30, 45]),
            pressure_kpa=rng.randint(80, 240),
            temperature_c=rng.randint(40, 120),
            component=rng.choice(comps),
            state=rng.choice(STATES),
            action=rng.choice(ACTIONS),
            issue=rng.choice(ISSUES),
            period=rng.choice(PERIODS),
            n_sensors=rng.choice([2, 3, 4]),
            alarm_triggered=rng.random() < 0.5,
            quantifier=rng.choice(["all", "most", "several", "two", "three"]),
        )

    # test partition: force at least one TEST_ONLY slot value
    ood_slot = rng.choice(["name", "role", "equip", "component"])
    names_pool = SHARED_NAMES + (TEST_ONLY_NAMES if ood_slot == "name" else [])
    roles_pool = SHARED_ROLES + (TEST_ONLY_ROLES if ood_slot == "role" else [])
    equip_pool = SHARED_EQUIP + (TEST_ONLY_EQUIP if ood_slot == "equip" else [])
    comp_pool = SHARED_COMPONENTS + (TEST_ONLY_COMPONENTS if ood_slot == "component" else [])
    if ood_slot == "name":
        reporter = rng.choice(TEST_ONLY_NAMES)
        responder = rng.choice(names_pool)
    else:
        reporter = rng.choice(names_pool)
        responder = rng.choice(names_pool)
    if ood_slot == "role":
        reporter_role = rng.choice(TEST_ONLY_ROLES)
        responder_role = rng.choice(roles_pool)
    else:
        reporter_role = rng.choice(roles_pool)
        responder_role = rng.choice(roles_pool)
    equipment = rng.choice(TEST_ONLY_EQUIP) if ood_slot == "equip" else rng.choice(equip_pool)
    component = rng.choice(TEST_ONLY_COMPONENTS) if ood_slot == "component" else rng.choice(comp_pool)
    return Slots(
        shift=rng.choice(SHIFTS),
        reporter_name=reporter,
        reporter_role=reporter_role,
        responder_name=responder,
        responder_role=responder_role,
        equipment=equipment,
        time_hh=rng.randint(0, 23),
        time_mm=rng.choice([0, 15, 30, 45]),
        pressure_kpa=rng.randint(80, 240),
        temperature_c=rng.randint(40, 120),
        component=component,
        state=rng.choice(STATES),
        action=rng.choice(ACTIONS),
        issue=rng.choice(ISSUES),
        period=rng.choice(PERIODS),
        n_sensors=rng.choice([2, 3, 4]),
        alarm_triggered=rng.random() < 0.5,
        quantifier=rng.choice(["all", "most", "several", "two", "three"]),
    )


# ---------- Phantom surface maps (meaning-preserving) ----------

def number_to_word(n: int) -> str:
    return {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def sensor_count_phrase(n: int, rng: random.Random) -> str:
    variants = [f"{n} sensors", f"{number_to_word(n)} sensors"]
    if n == 2:
        variants.append("a pair of sensors")
    elif n == 3:
        variants.append("a trio of sensors")
    return rng.choice(variants)


def time_phrase(hh: int, mm: int, rng: random.Random) -> str:
    """Multiple surface forms for the same time -- phantom temporal noise."""
    hh24 = f"{hh:02d}:{mm:02d}"
    words_24 = f"{hh:02d}{mm:02d} hours" if mm else f"{hh:02d}00 hours"
    suffix = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    h12_phrase = f"{h12}:{mm:02d} {suffix}" if mm else f"{h12}:00 {suffix}"
    approx_phrase = f"around {h12}:{mm:02d} {suffix}" if mm else f"around {h12} {suffix}"
    return rng.choice([hh24, words_24, h12_phrase, approx_phrase])


def quantifier_phrase(q: str, rng: random.Random) -> str:
    variants = {
        "all": ["all of", "every one of", "the entirety of"],
        "most": ["most of", "a majority of", "the bulk of"],
        "several": ["several of", "a number of", "multiple of"],
        "two": ["two of", "a pair of", "both of"],
        "three": ["three of", "a trio of", "three separate"],
        "none": ["none of", "not a single one of", "zero of"],
    }
    return rng.choice(variants.get(q, [q]))


def alarm_phrase(triggered: bool, rng: random.Random) -> str:
    if triggered:
        return rng.choice([
            "the alarm triggered",
            "an alarm was raised",
            "the alarm did activate",
            "alarm conditions were met",
        ])
    return rng.choice([
        "no alarm triggered",
        "no alarm was raised",
        "the alarm did not activate",
        "no alarm conditions were met",
    ])


def period_phrase(p: str, rng: random.Random) -> str:
    aliases = {
        "the first two hours": ["the opening two hours", "the first 120 minutes"],
        "the remainder of the watch": ["the rest of the watch", "the remaining watch"],
        "the handover window": ["the handover period", "the changeover window"],
    }
    return rng.choice([p] + aliases.get(p, []))


FILLER_CLAUSES = sorted([
    "Standard logging was maintained throughout.",
    "Routine procedures were followed.",
    "Communications were kept on the primary channel.",
    "Nominal conditions were noted elsewhere on the unit.",
    "Radio traffic remained light.",
])


def realize(s: Slots, variant: int, rng: random.Random) -> str:
    tphr = time_phrase(s.time_hh, s.time_mm, rng)
    sens = sensor_count_phrase(s.n_sensors, rng)
    qphr = quantifier_phrase(s.quantifier, rng)
    alm = alarm_phrase(s.alarm_triggered, rng)
    perphr = period_phrase(s.period, rng)

    if variant == 0:
        text = (
            f"On {s.shift}, {s.reporter_name} ({s.reporter_role}) walked through {s.equipment}. "
            f"At {tphr}, pressure read {s.pressure_kpa} kPa and temperature read {s.temperature_c} C. "
            f"{s.responder_name} ({s.responder_role}) inspected the {s.component}; status was {s.state}. "
            f"{qphr.capitalize()} {sens} logged the excursion and {alm}. "
            f"A {s.action} resolved {s.issue} during {perphr}."
        )
    elif variant == 1:
        text = (
            f"During the {s.shift}, a walk-through of {s.equipment} was performed by {s.reporter_name} ({s.reporter_role}). "
            f"At {tphr}, a pressure reading of {s.pressure_kpa} kPa and temperature of {s.temperature_c} C were recorded. "
            f"The {s.component} was inspected by {s.responder_name} ({s.responder_role}) and found to be {s.state}. "
            f"{qphr.capitalize()} {sens} recorded the event, and {alm}. "
            f"{s.issue.capitalize()} was addressed with a {s.action} throughout {perphr}."
        )
    elif variant == 2:
        text = (
            f"Log entry, {s.shift}: {s.reporter_name} ({s.reporter_role}) completed a walk-through of {s.equipment}. "
            f"Reading at {tphr} showed pressure of {s.pressure_kpa} kPa with temperature of {s.temperature_c} C. "
            f"Inspection of the {s.component} by {s.responder_name} ({s.responder_role}) returned a {s.state} status. "
            f"{qphr.capitalize()} {sens} registered the event; {alm}. "
            f"Resolution involved a {s.action} addressing {s.issue} over {perphr}."
        )
    else:
        text = (
            f"Summary for the {s.shift}. Walk-through of {s.equipment} by {s.reporter_name} ({s.reporter_role}). "
            f"Instruments at {tphr} reported {s.pressure_kpa} kPa pressure and {s.temperature_c} C temperature. "
            f"Component check: the {s.component}, handled by {s.responder_name} ({s.responder_role}), reading {s.state}. "
            f"Regarding sensors, {qphr} {sens} captured the excursion; {alm}. "
            f"Corrective action: a {s.action} to close out {s.issue} across {perphr}."
        )

    if rng.random() < 0.05:
        text = f"{text} {rng.choice(FILLER_CLAUSES)}"
    return text


# ---------- Drift mutators ----------

def _swap_name(rng: random.Random, current: str, pool: list[str]) -> str:
    alts = [n for n in pool if n != current]
    return rng.choice(alts) if alts else current


def mut_role_swap(rng: random.Random, s: Slots, partition: str) -> Slots:
    new = s.copy()
    if rng.random() < 0.5:
        new.reporter_name, new.responder_name = s.responder_name, s.reporter_name
        new.reporter_role, new.responder_role = s.responder_role, s.reporter_role
    else:
        pool = SHARED_NAMES + (TRAIN_ONLY_NAMES if partition == "train" else TEST_ONLY_NAMES)
        target = rng.choice(["reporter", "responder"])
        if target == "reporter":
            new.reporter_name = _swap_name(rng, s.reporter_name, pool)
        else:
            new.responder_name = _swap_name(rng, s.responder_name, pool)
    return new


def mut_numeric_error(rng: random.Random, s: Slots) -> Slots:
    """SUBTLER magnitudes: pressure +/-7-15%, temperature +/-7-15%, sensors +/-1."""
    new = s.copy()
    which = rng.choice(["pressure", "temperature", "sensors"])
    if which == "pressure":
        pct = rng.choice([-0.15, -0.10, -0.07, 0.07, 0.10, 0.15])
        delta = max(5, int(abs(s.pressure_kpa * pct)))
        delta = delta if pct > 0 else -delta
        new.pressure_kpa = max(10, s.pressure_kpa + delta)
    elif which == "temperature":
        pct = rng.choice([-0.15, -0.10, -0.07, 0.07, 0.10, 0.15])
        delta = max(4, int(abs(s.temperature_c * pct)))
        delta = delta if pct > 0 else -delta
        new.temperature_c = max(5, s.temperature_c + delta)
    else:
        delta = rng.choice([-1, 1])
        new.n_sensors = max(2, min(6, s.n_sensors + delta))
        if new.n_sensors == s.n_sensors:
            new.n_sensors = s.n_sensors + 1
    return new


QUANTIFIER_NEIGHBORS = {
    "all": ["most"],
    "most": ["all", "several"],
    "several": ["most", "two", "three"],
    "two": ["three", "several"],
    "three": ["two", "several"],
    "none": ["two"],
}


def mut_quantifier_drift(rng: random.Random, s: Slots) -> Slots:
    new = s.copy()
    options = [q for q in QUANTIFIER_NEIGHBORS.get(s.quantifier, ["most"]) if q != s.quantifier]
    new.quantifier = rng.choice(options) if options else "most"
    return new


def mut_temporal_shift(rng: random.Random, s: Slots) -> Slots:
    """SUBTLER: +/-30-60 minutes (not +/-2-3 hours)."""
    new = s.copy()
    if rng.random() < 0.75:
        delta_min = rng.choice([-60, -45, -30, 30, 45, 60])
        total_min = s.time_hh * 60 + s.time_mm + delta_min
        total_min = total_min % (24 * 60)
        new.time_hh = total_min // 60
        new.time_mm = (total_min % 60 // 15) * 15
    else:
        alt = [sh for sh in SHIFTS if sh != s.shift]
        new.shift = rng.choice(alt)
    return new


EXTRA_CLAUSES = sorted([
    "A faint rattle was also noted on the auxiliary mount.",
    "An additional vent cycle was logged by the supervisor.",
    "Backup power was confirmed online via panel three.",
    "A secondary gauge was cross-checked against the primary.",
    "Auxiliary logging was enabled for this interval only.",
    "An extra witness signature was recorded for compliance.",
])


def mut_insertion(rng: random.Random, text: str) -> str:
    return f"{text} {rng.choice(EXTRA_CLAUSES)}"


def mut_deletion(rng: random.Random, text: str) -> str:
    parts = [p.strip() for p in text.split(".") if p.strip()]
    if len(parts) <= 3:
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
    partition = "test" if rng.random() < TEST_FRACTION else "train"
    slots0 = sample_slots(rng, partition)
    variant0 = rng.randint(0, 3)
    m0 = realize(slots0, variant0, rng)

    n_drifts = rng.choices([0, 1, 2, 3, 4], weights=[20, 25, 25, 20, 10], k=1)[0]
    drift_types_fired = rng.sample(DRIFT_TYPES, k=n_drifts) if n_drifts > 0 else []
    if n_drifts > 0:
        steps_pool = list(range(1, CHAIN_STEPS + 1))
        rng.shuffle(steps_pool)
        drift_steps = {dt: steps_pool[i] for i, dt in enumerate(drift_types_fired)}
    else:
        drift_steps = {}

    current_slots = slots0.copy()
    steps = []
    for step in range(1, CHAIN_STEPS + 1):
        new_variant = rng.randint(0, 3)
        text_mutation: Callable[[str], str] | None = None
        for dt, when in drift_steps.items():
            if when == step:
                if dt == "role_swap":
                    current_slots = mut_role_swap(rng, current_slots, partition)
                elif dt == "numeric_error":
                    current_slots = mut_numeric_error(rng, current_slots)
                elif dt == "quantifier_drift":
                    current_slots = mut_quantifier_drift(rng, current_slots)
                elif dt == "temporal_shift":
                    current_slots = mut_temporal_shift(rng, current_slots)
                elif dt == "negation_flip":
                    current_slots = mut_negation_flip(rng, current_slots)
                elif dt == "insertion":
                    text_mutation = lambda t, _rng=rng: mut_insertion(_rng, t)
                elif dt == "deletion":
                    text_mutation = lambda t, _rng=rng: mut_deletion(_rng, t)

        new_text = realize(current_slots, new_variant, rng)
        if text_mutation is not None:
            new_text = text_mutation(new_text)
        steps.append(new_text)

    first = {f"first_{dt}": drift_steps.get(dt, -1) for dt in DRIFT_TYPES}
    return {
        "id": hex_id(SEED, idx),
        **{f"step_{i}": steps[i - 1] for i in range(1, CHAIN_STEPS + 1)},
        "original_message": m0,
        **first,
        "n_drifts_total": n_drifts,
        "split": partition,
    }


def main() -> None:
    # Write data.csv next to this script when run standalone (as in the
    # public generator repo). When the generator is placed inside the
    # challenge tree alongside dataset/raw/, write there instead.
    script_dir = Path(__file__).parent
    if (script_dir / "dataset" / "raw").exists():
        out = script_dir / "dataset" / "raw" / "data.csv"
    else:
        out = script_dir / "data.csv"
    rows = [build_chain(i) for i in range(N_CHAINS)]
    rows.sort(key=lambda r: r["id"])

    fieldnames = (
        ["id"]
        + [f"step_{i}" for i in range(1, CHAIN_STEPS + 1)]
        + ["original_message"]
        + [f"first_{dt}" for dt in DRIFT_TYPES]
        + ["n_drifts_total", "split"]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {len(rows)} rows to {out}")
    from collections import Counter
    print(f"Split distribution: {dict(Counter(r['split'] for r in rows))}")
    print(f"n_drifts distribution: {dict(sorted(Counter(r['n_drifts_total'] for r in rows).items()))}")


if __name__ == "__main__":
    main()

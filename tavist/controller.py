from typing import List, Tuple, Dict
from tavist.model import AttackAction, DamageRoll, DamageType, WeaponDamageDice
from tavist.tracking import ACTargetTracker, format_bound, damage_for_hit


def compute_damage_for_ac(results: List[dict], ac: int) -> Tuple[int, Dict[str, int]]:
    total = 0
    breakdown: Dict[str, int] = {}
    for r in results:
        if r.get("natural_one"):
            continue
        if not r.get("natural_twenty") and ac > r["attack_total"]:
            continue
        use_crit = r["threat"] and r["confirm_total"] is not None and ac <= r["confirm_total"]
        parts = r["breakdown_critical"] if use_crit else r["breakdown_normal"]
        for label, val in parts.items():
            breakdown[label] = breakdown.get(label, 0) + val
    total = sum(breakdown.values())
    return total, breakdown


def summarize_damage_ranges(results: List[dict]) -> List[Tuple[int | None, int | None, int, Dict[str, int]]]:
    thresholds = set()
    for r in results:
        thresholds.add(r["attack_total"])
        if r.get("confirm_total"):
            thresholds.add(r["confirm_total"])
    if not thresholds:
        return []
    ordered = sorted(thresholds, reverse=True)
    raw_ranges: List[Tuple[int | None, int | None, int, Dict[str, int]]] = []

    top = ordered[0]
    raw_ranges.append((top, None, 0, {}))

    for idx, upper in enumerate(ordered):
        lower = ordered[idx + 1] if idx + 1 < len(ordered) else None
        dmg, breakdown = compute_damage_for_ac(results, upper)
        raw_ranges.append((lower, upper, dmg, breakdown))

    merged: List[Tuple[int | None, int | None, int, Dict[str, int]]] = []
    for lower, upper, dmg, breakdown in raw_ranges:
        if (
            merged
            and merged[-1][2] == dmg
            and merged[-1][1] is not None
            and upper is not None
            and merged[-1][3] == breakdown
        ):
            prev_lower, prev_upper, _, bd = merged[-1]
            merged[-1] = (lower, prev_upper, dmg, bd)
        else:
            merged.append((lower, upper, dmg, breakdown))

    merged_sorted = sorted(merged, key=lambda x: (-1 if x[1] is None else -x[1]))
    return merged_sorted


def _guaranteed_hit(r: dict, tracker: ACTargetTracker | None) -> bool:
    if not tracker or tracker.upper == 99:
        return False
    if r.get("natural_one"):
        return False
    if r.get("natural_twenty"):
        return True
    bound = tracker.upper
    return r["attack_total"] >= bound or (r.get("confirm_total") and r["confirm_total"] >= bound)


def format_attack_line(r: dict, tracker: ACTargetTracker | None) -> str:
    certainly_hits = _guaranteed_hit(r, tracker)
    normal_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_normal"].items())) or "none"
    crit_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_critical"].items())) or "none"
    if r.get("natural_one"):
        line = f"{r['label']}: natural 1 (automatic miss)"
    elif r.get("natural_twenty"):
        base_line = f"{r['label']}: natural 20 | damage {r['damage_normal']} dmg [{normal_bd}]"
        if r["threat"] and r.get("confirm_total"):
            base_line += f" | threat (crit confirms on AC {r['confirm_total']}) crit {r['damage_critical']} dmg [{crit_bd}]"
        line = base_line
    elif r["threat"] and r.get("confirm_total") is not None:
        if tracker and tracker.upper != 99 and r["confirm_total"] >= tracker.upper:
            line = (
                f"{r['label']}: hits AC {r['attack_total']} | crit confirmed at AC {r['confirm_total']} "
                f"crit {r['damage_critical']} dmg [{crit_bd}]"
            )
        elif tracker and tracker.lower != 0 and r["confirm_total"] <= tracker.lower:
            line = (
                f"{r['label']}: hits AC {r['attack_total']} | threat (AC {r['confirm_total']} did not confirm) "
                f"normal {r['damage_normal']} dmg [{normal_bd}]"
            )
        else:
            line = (
                f"{r['label']}: hits AC {r['attack_total']} | threat (crit confirms on AC {r['confirm_total']}) "
                f"normal {r['damage_normal']} dmg [{normal_bd}] / crit {r['damage_critical']} dmg [{crit_bd}]"
            )
    else:
        line = (
            f"{r['label']}: hits AC {r['attack_total']} | damage {r['damage_normal']} dmg "
            f"[{', '.join(f'{k} {v}' for k, v in sorted(r['breakdown_normal'].items())) or 'none'}]"
        )
    if certainly_hits:
        line = f"* **{line}**"
    return line


def apply_tracking_selection(tracker: ACTargetTracker, selection: dict, candidates: list[dict]):
    if selection.get("all_miss"):
        for r in candidates:
            tracker.record_miss(r["attack_total"])
        return
    chosen = selection.get("total")
    if chosen is None:
        return
    for r in candidates:
        if r["attack_total"] >= chosen:
            if r.get("confirm_total"):
                tracker.record_hit(r["confirm_total"])
            else:
                tracker.record_hit(r["attack_total"])
            tracker.damage_done += damage_for_hit(r, tracker.upper)
        else:
            tracker.record_miss(r["attack_total"])

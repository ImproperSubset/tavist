from dataclasses import dataclass


@dataclass
class ACTargetTracker:
    lower: int = 0
    upper: int = 99
    damage_done: int = 0

    def reset(self):
        self.lower = 0
        self.upper = 99
        self.damage_done = 0

    def record_hit(self, attack_total: int):
        self.upper = min(self.upper, attack_total)

    def record_miss(self, attack_total: int):
        self.lower = max(self.lower, attack_total)

    def estimate(self) -> int:
        if self.upper == 99:
            return self.lower
        if (self.upper - self.lower) <= 1:
            return self.upper
        return (self.lower + self.upper + 1) // 2


def format_bound(tracker: ACTargetTracker) -> str:
    if tracker.upper != 99 and (tracker.upper - tracker.lower) <= 1:
        return f"== {tracker.upper}"
    return f">{tracker.lower}, ≤{tracker.upper if tracker.upper != 99 else '?'}"


def damage_for_hit(result: dict, bound: int) -> int:
    use_crit = result.get("threat") and result.get("confirm_total") and bound != 99 and result["confirm_total"] >= bound
    return result.get("damage_critical" if use_crit else "damage_normal", 0)


def accumulate_known_hits(tracker: ACTargetTracker, results: list[dict]):
    for r in results:
        if r.get("natural_one"):
            continue  # automatic miss, no hit info
        if r.get("natural_twenty"):
            tracker.damage_done += damage_for_hit(r, tracker.upper if tracker.upper != 99 else 0)
            continue
        if tracker.upper == 99:
            continue
        bound = tracker.upper
        if r["attack_total"] >= bound or (r.get("confirm_total") and r["confirm_total"] >= bound):
            tracker.damage_done += damage_for_hit(r, bound)

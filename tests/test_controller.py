from tavist.controller import format_attack_line
from tavist.tracking import ACTargetTracker


def make_result(**overrides):
    base = {
        "label": "attack",
        "attack_total": 33,
        "threat": True,
        "confirm_total": 19,
        "natural_one": False,
        "natural_twenty": False,
        "damage_normal": 26,
        "damage_critical": 52,
        "breakdown_normal": {"slashing": 26},
        "breakdown_critical": {"slashing": 52},
    }
    base.update(overrides)
    return base


def test_confirm_failure_is_still_marked_as_hit():
    tracker = ACTargetTracker(lower=19, upper=20)
    line = format_attack_line(make_result(), tracker)
    assert line.startswith("* **")
    assert "AC 19 did not confirm" in line


def test_confirm_meeting_bound_marks_hit_even_if_attack_is_lower():
    tracker = ACTargetTracker(lower=17, upper=20)
    line = format_attack_line(make_result(attack_total=18, confirm_total=22), tracker)
    assert line.startswith("* **")


def test_natural_one_is_never_marked_as_hit():
    tracker = ACTargetTracker(lower=17, upper=20)
    line = format_attack_line(
        make_result(attack_total=5, threat=False, confirm_total=None, natural_one=True), tracker
    )
    assert not line.startswith("* **")

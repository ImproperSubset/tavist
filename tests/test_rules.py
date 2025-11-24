import builtins

import pytest

from tavist import model


def make_randint(seq):
    """Return a randint replacement that yields a fixed sequence."""
    it = iter(seq)

    def _randint(a, b):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("randint sequence exhausted") from None

    return _randint


def test_attack_action_handles_crit_confirm(monkeypatch):
    # Attack roll 19 (threat), confirm 15, damage dice 3 (weapon) and 2 (holy)
    monkeypatch.setattr(model, "randint", make_randint([19, 15, 3, 2]))
    attack = model.AttackRoll(bonuses=[model.Bonus(5, model.BonusType.BAB)], critical_threshold=19)
    damage = model.DamageRoll(
        type=model.DamageType.SLASHING,
        dice=[model.WeaponDamageDice(d=6, label="weapon"), model.DamageDice(d=6, label="holy")],
        bonuses=[model.Bonus(2, model.BonusType.ENHANCEMENT)],
    )
    action = model.AttackAction(label="test", attack=attack, damage=damage)

    result = action.do_attack()

    assert result["attack_die"] == 19
    assert result["attack_total"] == 24  # 19 + BAB 5
    assert result["confirm_total"] == 20  # 15 + BAB 5
    assert result["damage_normal"] == 7  # 3+2+2
    assert result["damage_critical"] == 12  # weapon doubled + bonus doubled
    assert result["threat"] is True


def test_offhand_and_twohand_scaling():
    tavist = model.Tavist()
    tavist.set_power_attack(6)
    assert tavist.poweratt_damage_bonus_main.bonus == 6
    assert tavist.poweratt_damage_bonus_off.bonus == 3  # half scaling
    assert tavist.ability_main.bonus == 4
    assert tavist.ability_off.bonus == 2

    tavist.set_two_handed(True)
    tavist.set_power_attack(6)
    assert tavist.poweratt_damage_bonus_main.bonus == 12  # 2x scaling two-hand
    assert tavist.poweratt_damage_bonus_off.bonus == 0
    assert tavist.ability_main.bonus == 6  # 1.5x Str
    assert tavist.ability_off.bonus == 0


def test_damage_breakdown_uses_weapon_type(monkeypatch):
    # Weapon die 2, ability 4, power attack 4 -> all bucketed under slashing
    monkeypatch.setattr(model, "randint", make_randint([15, 2]))
    attack = model.AttackRoll(bonuses=[model.Bonus(5)], critical_threshold=20)
    damage = model.DamageRoll(
        type=model.DamageType.SLASHING,
        dice=[model.WeaponDamageDice(d=6, label="weapon")],
        bonuses=[
            model.Bonus(4, model.BonusType.ABILITY),
            model.Bonus(4, model.BonusType.POWER_ATTACK),
        ],
    )
    action = model.AttackAction(label="slashing-test", attack=attack, damage=damage)
    result = action.do_attack()
    assert result["breakdown_normal"] == {"slashing": 10}
    assert result["breakdown_critical"]["slashing"] == 20  # weapon die doubled, bonuses doubled


def test_expected_full_attack_prefers_two_hand_at_ac_22():
    tavist = model.Tavist()
    attacks = [12, 12, 7, 2]
    names = ["first", "speed", "second", "third"]

    dpr_dual = model.expected_full_attack(tavist, 22, False, attacks, names)
    dpr_two = model.expected_full_attack(tavist, 22, True, attacks, names)

    assert dpr_two > dpr_dual


def test_recommend_setup_returns_expected_mode():
    tavist = model.Tavist()
    attacks = [12, 12, 7, 2]
    names = ["first", "speed", "second", "third"]
    pa, two = model.recommend_setup(tavist, 22, attacks, names)

    assert two is True
    assert pa >= 0


def test_weapon_crit_ranges():
    tavist = model.Tavist()
    assert tavist.katana_attack.critical_threshold == 17
    assert tavist.wakasashi_attack.critical_threshold == 19


def test_main_compiles():
    import py_compile
    py_compile.compile("main.py", doraise=True)


def test_main_window_builds_offscreen(monkeypatch):
    # Ensure Qt doesn't require a display
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    window = app_main.MainWindow()
    assert window.windowTitle() == "Tavist"
    qapp.quit()


def test_tracking_dialog_updates_bounds(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton

    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    def fake_exec(self):
        # simulate clicking "All Misses"
        for btn in self.findChildren(QPushButton):
            if btn.text() == "All Misses":
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    results = [
        {"label": "first", "attack_total": 15},
        {"label": "second", "attack_total": 10},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    assert tracker.lower > 0  # bounds tightened after all misses
    qapp.quit()


def test_ac_tracker_bounds_basic():
    from main import ACTargetTracker
    t = ACTargetTracker()
    assert t.lower == 0 and t.upper == 99
    t.record_hit(18)
    assert (t.lower, t.upper) == (0, 18)
    t.record_miss(10)
    assert (t.lower, t.upper) == (10, 18)
    assert t.estimate() == 14  # ceil midpoint
    t.record_miss(17)
    assert (t.lower, t.upper) == (17, 18)
    assert t.estimate() == 18  # solved


def test_ac_tracker_equal_bounds():
    from main import ACTargetTracker
    t = ACTargetTracker()
    t.record_miss(19)
    t.record_hit(20)
    assert (t.lower, t.upper) == (19, 20)
    assert t.estimate() == 20
    t.record_hit(19)
    assert (t.lower, t.upper) == (19, 19)
    assert t.estimate() == 19


def test_tracking_dialog_single_candidate(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    def fake_exec(self):
        # simulate clicking the only button
        for btn in self.findChildren(QPushButton):
            if "AC" in btn.text():
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 10
    tracker.upper = 20
    results = [
        {"label": "only", "attack_total": 15},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    assert tracker.upper == 15
    assert tracker.lower == 10
    qapp.quit()


def test_tracking_dialog_two_candidates_choose_low(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    def fake_exec(self):
        # simulate clicking the lowest AC hit (AC 18), not the higher one
        for btn in sorted(self.findChildren(QPushButton), key=lambda b: b.text()):
            if "(AC 18)" in btn.text():
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 10
    tracker.upper = 30
    results = [
        {"label": "high", "attack_total": 25},
        {"label": "low", "attack_total": 18},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    # choosing 18 should set upper to 18 and leave lower at 10
    assert tracker.upper == 18
    assert tracker.lower == 10
    qapp.quit()


def test_tracking_dialog_does_not_prompt_at_bound(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    called = {"count": 0}

    def fake_exec(self):
        called["count"] += 1
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 19
    tracker.upper = 20
    results = [{"label": "hit", "attack_total": 20, "damage_normal": 5}]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    assert called["count"] == 0
    # accumulator should count this as guaranteed
    app_main.accumulate_known_hits(tracker, results)
    assert tracker.damage_done == 5
    qapp.quit()


def test_accumulate_known_hits_when_solved(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    tracker = app_main.ACTargetTracker()
    tracker.lower = 19
    tracker.upper = 20
    results = [{"attack_total": 20, "damage_normal": 10}]

    # dialog would not show; accumulate should count guaranteed hit
    app_main.accumulate_known_hits(tracker, results)

    assert tracker.damage_done == 10
    qapp.quit()


def test_power_attack_lock(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    window = app_main.MainWindow()
    tavist = app_main.Tavist()

    window.poweratt.setText("0")
    window.poweratt_lock.setChecked(True)
    app_main.update_dpr_label(window, tavist, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    assert window.poweratt.text() == "0"

    window.poweratt_lock.setChecked(False)
    app_main.update_dpr_label(window, tavist, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    assert window.poweratt.text() == window.reccommended_poweratt.text()
    qapp.quit()


def test_tracking_dialog_no_prompt_when_solved(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 19
    tracker.upper = 20
    results = [{"label": "hit", "attack_total": 25}]

    called = {"count": 0}

    def fake_exec(self):
        called["count"] += 1
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    assert called["count"] == 0
    qapp.quit()


def test_external_bonuses_applied(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    window.ext_hit.setText("2")
    window.ext_str.setText("4")
    app_main.apply_external(window, tavist, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    # external hit should be in attack bonuses
    assert any(b.label == "ext-hit" and b.bonus == 2 for b in tavist.katana_attack.bonuses)
    # external str should reflect in damage ability bonuses
    assert tavist.ability_ext_main.bonus == 4
    assert tavist.ability_ext_off.bonus == 2
    qapp.quit()


def test_tracking_dialog_adds_damage(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    def fake_exec(self):
        # click the lowest AC hit (AC 15)
        for btn in self.findChildren(QPushButton):
            if "(AC 15)" in btn.text():
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 0
    tracker.upper = 30
    results = [
        {"label": "high", "attack_total": 25, "damage_normal": 10},
        {"label": "low", "attack_total": 15, "damage_normal": 5},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    # Should accumulate only hits >= chosen (15 and 25)
    assert tracker.damage_done == 15
    qapp.quit()


def test_tracking_dialog_crit_confirm_logic(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])

    def fake_exec(self):
        # click the crit threat
        for btn in self.findChildren(QPushButton):
            if "(AC 18)" in btn.text():
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 0
    tracker.upper = 20
    results = [
        {"label": "crit", "attack_total": 18, "damage_normal": 5, "damage_critical": 9, "threat": True, "confirm_total": 19},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    # confirm >= bound, so crit damage should be counted
    assert tracker.damage_done == 9
    qapp.quit()


def test_tracking_dialog_prompts_on_confirm_within_bounds(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    called = {"count": 0}

    def fake_exec(self):
        called["count"] += 1
        # click the only button (crit threat with confirm in range)
        for btn in self.findChildren(QPushButton):
            if "(AC 30)" in btn.text():
                btn.click()
                break
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.lower = 17
    tracker.upper = 20
    results = [
        {"label": "crit", "attack_total": 30, "damage_normal": 5, "damage_critical": 11, "threat": True, "confirm_total": 18},
    ]

    app_main.tracking_dialog(window, tavist, tracker, results, [12, 12, 7, 2], ["first", "speed", "second", "third"])

    assert called["count"] == 1
    # upper should tighten to confirm total
    assert tracker.upper == 18
    assert tracker.damage_done == 11
    qapp.quit()


def test_accumulate_known_hits_uses_confirm_for_damage():
    from tavist.tracking import ACTargetTracker, accumulate_known_hits

    tracker = ACTargetTracker(lower=0, upper=18, damage_done=0)
    results = [{"attack_total": 30, "confirm_total": 25, "damage_normal": 5, "damage_critical": 11, "threat": True}]
    accumulate_known_hits(tracker, results)
    assert tracker.damage_done == 11


def test_nat20_not_used_for_bounds(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    tracker = app_main.ACTargetTracker()
    tracker.lower = 10
    tracker.upper = 20
    results = [{"attack_total": 30, "confirm_total": 15, "damage_normal": 5, "damage_critical": 9, "threat": True, "natural_twenty": True}]
    # accumulate should not tighten bounds but should add damage from nat20
    tracker_before = (tracker.lower, tracker.upper, tracker.damage_done)
    app_main.accumulate_known_hits(tracker, results)
    assert tracker_before[0] == tracker.lower
    assert tracker_before[1] == tracker.upper
    assert tracker.damage_done == tracker_before[2] + 5
    qapp.quit()


def test_nat1_always_miss():
    from tavist.model import AttackAction, AttackRoll, DamageRoll, DamageType, WeaponDamageDice
    from tavist.model import Bonus
    from tavist.model import BonusType
    import tavist.model as model

    def fake_randint(a, b):
        return 1

    model.randint = fake_randint
    attack = AttackRoll(bonuses=[Bonus(100, BonusType.BAB)], critical_threshold=20)
    damage = DamageRoll(type=DamageType.SLASHING, dice=[WeaponDamageDice(d=10, label="weapon")])
    action = AttackAction(label="nat1", attack=attack, damage=damage)
    result = action.do_attack()
    assert result["natural_one"] is True
    assert result["attack_total"] > 1
    assert result["damage_normal"] >= 0


def test_new_opponent_resets_damage(monkeypatch):
    import os
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    import main as app_main

    qapp = QApplication.instance() or QApplication([])
    window = app_main.MainWindow()
    tavist = app_main.Tavist()
    tracker = app_main.ACTargetTracker()
    tracker.damage_done = 20
    window._ac_tracker = tracker
    do_auto = app_main.wrap_auto_recommend(window, tavist, [12, 12, 7, 2], ["first", "speed", "second", "third"])
    do_auto()
    assert tracker.damage_done == 0
    assert "0" in window.damage_done.text()
    qapp.quit()

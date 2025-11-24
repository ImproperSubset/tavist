from contextlib import redirect_stdout
import sys
import html
import re
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
    QDialog,
    QCheckBox,
)
from tavist.model import (
    AttackAction,
    AttackRoll,
    Bonus,
    BonusType,
    DamageDice,
    DamageRoll,
    DamageType,
    Tavist,
    WeaponDamageDice,
    expected_full_attack,
    recommend_setup,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tavist")
        font = self.font()
        font.setPointSize(font.pointSize() + 2)
        self.setFont(font)

        self.target_ac = QLineEdit()
        self.target_ac.setText("")

        self.expertise = QLineEdit()
        self.expertise.setText("")

        self.auto_button = QPushButton("New Opponent")

        self.two_handed = QPushButton()
        self.two_handed.setCheckable(True)
        self.two_handed.setChecked(False)
        self.two_handed.setText("Two-Handed")

        targeting_layout = QHBoxLayout()
        targeting_layout.addWidget(QLabel("Est. AC:"))
        targeting_layout.addWidget(self.target_ac)
        targeting_layout.addWidget(QLabel("Combat Expertise:"))
        targeting_layout.addWidget(self.expertise)
        targeting_layout.addWidget(self.auto_button)
        targeting_group = QGroupBox("Targeting")
        targeting_group.setLayout(targeting_layout)

        extra_layout = QHBoxLayout()
        self.ext_hit = QLineEdit("0")
        self.ext_str = QLineEdit("0")
        self.fatigued = QPushButton("Fatigued")
        self.fatigued.setCheckable(True)
        self.fatigued.setChecked(False)
        extra_layout.addWidget(QLabel("Ext Hit:"))
        extra_layout.addWidget(self.ext_hit)
        extra_layout.addWidget(QLabel("Ext Str:"))
        extra_layout.addWidget(self.ext_str)
        extra_layout.addWidget(self.fatigued)
        extra_group = QGroupBox("External Effects")
        extra_group.setLayout(extra_layout)

        poweratt_layout = QHBoxLayout()
        self.reccommended_poweratt = QLabel()
        self.poweratt = QLineEdit("0")
        self.poweratt_lock = QCheckBox("Lock")
        poweratt_layout.addWidget(QLabel("Pwr Att:"))
        poweratt_layout.addWidget(self.poweratt)
        poweratt_layout.addWidget(QLabel("Suggested:"))
        poweratt_layout.addWidget(self.reccommended_poweratt)
        poweratt_layout.addWidget(self.poweratt_lock)
        poweratt_layout.addWidget(self.two_handed)

        poweratt_group = QGroupBox("Attack Mode")
        poweratt_group.setLayout(poweratt_layout)

        status_layout = QHBoxLayout()

        self.evil = QPushButton()
        self.evil.setCheckable(True)
        self.evil.setChecked(False)
        self.evil.setText("Evil")

        self.surge = QPushButton()
        self.surge.setCheckable(True)
        self.surge.setChecked(False)
        self.surge.setText("Power Surge")

        self.tracking = QPushButton("Tracking")
        self.tracking.setCheckable(True)
        self.tracking.setChecked(True)

        status_layout.addWidget(self.evil)
        status_layout.addWidget(self.surge)
        status_layout.addWidget(self.tracking)

        status_group = QGroupBox("Status")
        status_group.setLayout(status_layout)

        katana_layout = QHBoxLayout()
        self.attack_button = QPushButton("Attack")
        katana_layout.addWidget(self.attack_button)
        katana_group = QGroupBox("Single Attack")
        katana_group.setLayout(katana_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(targeting_group)
        main_layout.addWidget(extra_group)
        main_layout.addWidget(poweratt_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(katana_group)

        self.full_attack = QPushButton("Full Attack")
        main_layout.addWidget(self.full_attack)

        dpr_row = QHBoxLayout()
        self.dpr_label = QLabel("Expected DPR: —")
        self.ac_bound = QLabel("AC bound: ?>")
        dpr_row.addWidget(self.dpr_label)
        dpr_row.addWidget(self.ac_bound)
        dpr_row.addStretch()
        main_layout.addLayout(dpr_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(160)
        log_font = self.log_output.font()
        log_font.setPointSize(log_font.pointSize() + 2)
        self.log_output.setFont(log_font)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        self.log_output.setMinimumWidth(800)
        main_layout.addWidget(self.log_output)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.resize(900, 700)



def make_dice_toggle(roll: DamageRoll, cond: DamageDice):
    def damage_toggle(checked: bool):
        match checked:
            case True:
                if cond not in roll.dice:
                    roll.dice.append(cond)
            case False:
                if cond in roll.dice:
                    roll.dice.remove(cond)

    return damage_toggle


def make_bonus_toggle(roll: DamageRoll, cond: Bonus):
    def damage_toggle(checked: bool):
        match checked:
            case True:
                if cond not in roll.bonuses:
                    roll.bonuses.append(cond)
            case False:
                if cond in roll.bonuses:
                    roll.bonuses.remove(cond)

    return damage_toggle


def make_damage_update(bonus: Bonus):
    def damage_update(text: str):
        try:
            bonus.bonus = int(text)
        except ValueError:
            bonus.bonus = 0

    return damage_update


def make_damage_update_scaled(bonus: Bonus, scale: float):
    def damage_update(text: str):
        try:
            val = int(text)
            bonus.bonus = int(val * scale)
        except ValueError:
            bonus.bonus = 0

    return damage_update


def make_attack_update(bonus: Bonus):
    def attack_update(text: str):
        try:
            bonus.bonus = -int(text)
        except ValueError:
            bonus.bonus = 0

    return attack_update


def make_power_attack_update(tavist: "Tavist"):
    def update(text: str):
        try:
            val = int(text)
        except ValueError:
            val = 0
        tavist.set_power_attack(val)

    return update


def wrap_bonus_adjustment(attack: AttackAction, name: str, bonus: Bonus, value: int):
    def bonus_adjustment():
        attack.label = name
        bonus.bonus = value

    return bonus_adjustment


class DualWriter:
    def __init__(self):
        self.parts: list[str] = []

    def write(self, text: str):
        sys.__stdout__.write(text)
        self.parts.append(text)

    def flush(self):
        sys.__stdout__.flush()

    def text(self) -> str:
        return "".join(self.parts)


def append_log(window: MainWindow, text: str):
    def _escape(s: str) -> str:
        # Minimal escaping: leave ">" intact for readability.
        return s.replace("&", "&amp;").replace("<", "&lt;")

    for raw_line in text.split("\n"):
        escaped = _escape(raw_line)
        bold_match = re.search(r"\*\*(.+?)\*\*", escaped)
        if bold_match:
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", escaped)
            window.log_output.append(f'<span style="font-weight:bold">{content}</span>')
        else:
            window.log_output.append(f'<span style="font-weight:normal">{escaped}</span>')
    cursor = window.log_output.textCursor()
    cursor.movePosition(QTextCursor.End)
    window.log_output.setTextCursor(cursor)
    window.log_output.ensureCursorVisible()


class ACTargetTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.lower = 0  # AC is > lower
        self.upper = 99  # AC is <= upper

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


def perform_attack_with_log(attack: AttackAction, window: MainWindow):
    def do_attack():
        writer = DualWriter()
        with redirect_stdout(writer):
            result = attack.do_attack()
        log_text = writer.text().rstrip()
        if log_text:
            append_log(window, log_text)
            append_log(window, "")
        return result

    return do_attack


def compute_damage_for_ac(results: list[dict], ac: int) -> tuple[int, dict[str, int]]:
    total = 0
    breakdown: dict[str, int] = {}
    for r in results:
        if ac > r["attack_total"]:
            continue
        use_crit = r["threat"] and r["confirm_total"] is not None and ac <= r["confirm_total"]
        parts = r["breakdown_critical"] if use_crit else r["breakdown_normal"]
        for label, val in parts.items():
            breakdown[label] = breakdown.get(label, 0) + val
    total = sum(breakdown.values())
    return total, breakdown


def summarize_damage_ranges(results: list[dict]) -> list[tuple[int | None, int | None, int, dict[str, int]]]:
    """
    Returns list of (lower_exclusive, upper_inclusive, damage).
    lower_exclusive is None for the lowest band; (upper, None, damage) means AC > upper.
    """
    thresholds = set()
    for r in results:
        thresholds.add(r["attack_total"])
        if r.get("confirm_total"):
            thresholds.add(r["confirm_total"])
    if not thresholds:
        return []
    ordered = sorted(thresholds, reverse=True)
    raw_ranges: list[tuple[int | None, int | None, int, dict[str, int]]] = []

    top = ordered[0]
    raw_ranges.append((top, None, 0, {}))  # AC > top

    for idx, upper in enumerate(ordered):
        lower = ordered[idx + 1] if idx + 1 < len(ordered) else None
        dmg, breakdown = compute_damage_for_ac(results, upper)
        raw_ranges.append((lower, upper, dmg, breakdown))

    merged: list[tuple[int | None, int | None, int, dict[str, int]]] = []
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

    # normalize order: descending upper
    merged_sorted = sorted(merged, key=lambda x: (-1 if x[1] is None else -x[1]))
    return merged_sorted


def wrap_full_attack(
    window: MainWindow, tavist: "Tavist", attack_names: list[str], attacks: list[int]
):
    def do_full_attack():
        append_log(window, "=== Full Attack ===")
        results: list[dict] = []

        for idx, bonus in enumerate(attacks):
            wrap_bonus_adjustment(
                tavist.katana_attack_action, attack_names[idx], tavist.bab, bonus
            )()
            results.append(perform_attack_with_log(tavist.katana_attack_action, window)())

        if not tavist.two_handed_mode:
            wrap_bonus_adjustment(tavist.wakasashi_attack_action, "off-hand", tavist.bab, 12)()
            results.append(perform_attack_with_log(tavist.wakasashi_attack_action, window)())

        ranges = summarize_damage_ranges(results)
        if ranges:
            append_log(window, "--- Damage by AC ---")
            for lower, upper, damage, breakdown in ranges:
                def bd_text():
                    if not breakdown:
                        return ""
                    parts = [f"{k} {v}" for k, v in sorted(breakdown.items())]
                    return " (" + ", ".join(parts) + ")"

                if upper is None and lower is not None:
                    append_log(window, f"AC > {lower}: {damage} dmg{bd_text()}")
                elif lower is None:
                    append_log(window, f"AC ≤ {upper}: {damage} dmg{bd_text()}")
                else:
                    append_log(window, f"{lower} < AC ≤ {upper}: {damage} dmg{bd_text()}")
        if results:
            append_log(window, "--- Per attack ---")
            for r in results:
                tracker = getattr(window, "_ac_tracker", None)
                certainly_hits = (
                    tracker is not None and tracker.upper != 99 and r["attack_total"] >= tracker.upper
                )
                line = ""
                if r["threat"] and r["confirm_total"] is not None:
                    normal_bd = ", ".join(
                        f"{k} {v}" for k, v in sorted(r["breakdown_normal"].items())
                    ) or "none"
                    crit_bd = ", ".join(
                        f"{k} {v}" for k, v in sorted(r["breakdown_critical"].items())
                    ) or "none"
                    line = (
                        f"{r['label']}: hits AC {r['attack_total']} | threat (crit confirms on AC ≤ {r['confirm_total']}) "
                        f"normal {r['damage_normal']} dmg [{normal_bd}] / crit {r['damage_critical']} dmg [{crit_bd}]"
                    )
                else:
                    line = (
                        f"{r['label']}: hits AC {r['attack_total']} | damage {r['damage_normal']} dmg "
                        f"[{', '.join(f'{k} {v}' for k, v in sorted(r['breakdown_normal'].items())) or 'none'}]"
                    )
                if certainly_hits:
                    line = f"* **{line}**"
                append_log(window, line)
        append_log(window, "")

        return results

    return do_full_attack


def wrap_single_attack(window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]):
    def do_attack():
        results: list[dict] = []
        wrap_bonus_adjustment(
            tavist.katana_attack_action, attack_names[0], tavist.bab, attacks[0]
        )()
        results.append(perform_attack_with_log(tavist.katana_attack_action, window)())

        if results:
            r = results[0]
            normal_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_normal"].items())) or "none"
            crit_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_critical"].items())) or "none"
            tracker = getattr(window, "_ac_tracker", None)
            certainly_hits = (
                tracker is not None and tracker.upper != 99 and r["attack_total"] >= tracker.upper
            )
            line = (
                f"{r['label']}: hits AC {r['attack_total']} | "
                f"normal {r['damage_normal']} dmg [{normal_bd}] / crit {r['damage_critical']} dmg [{crit_bd}]"
            )
            if certainly_hits:
                line = f"* **{line}**"
            append_log(window, line)
            append_log(window, "")
        return results

    return do_attack


def wrap_single_attack(window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]):
    def do_attack():
        results: list[dict] = []
        for idx, bonus in enumerate(attacks):
            wrap_bonus_adjustment(
                tavist.katana_attack_action, attack_names[idx], tavist.bab, bonus
            )()
            res = perform_attack_with_log(tavist.katana_attack_action, window)()
            results.append(res)
            break  # only the first available attack bonus (primary attack)

        if results:
            r = results[0]
            normal_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_normal"].items())) or "none"
            crit_bd = ", ".join(f"{k} {v}" for k, v in sorted(r["breakdown_critical"].items())) or "none"
            append_log(
                window,
                f"{r['label']}: hits AC {r['attack_total']} | "
                f"normal {r['damage_normal']} dmg [{normal_bd}] / crit {r['damage_critical']} dmg [{crit_bd}]",
            )
            append_log(window, "")

    return do_attack


def wrap_auto_recommend(
    window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]
):
    def do_auto():
        try:
            ac = int(window.target_ac.text() or "0")
        except ValueError:
            ac = 99
        tracker = getattr(window, "_ac_tracker", None)
        if tracker:
            tracker.reset()
        pa, two = recommend_setup(tavist, ac, attacks, attack_names)
        tavist.set_two_handed(two)
        window.two_handed.setChecked(two)
        tavist.set_power_attack(pa)
        window.poweratt.blockSignals(True)
        window.poweratt.setText(str(pa))
        window.poweratt.blockSignals(False)
        window.reccommended_poweratt.setText(str(pa))
        mode = "two-handed" if two else "dual-wield"
        append_log(window, f"Auto set for AC {ac}: PA {pa}, {mode}")

    return do_auto


def update_dpr_label(
    window: MainWindow, tavist: "Tavist", attacks: list[int], attack_names: list[str]
):
    try:
        ac = int(window.target_ac.text() or "0")
    except ValueError:
        ac = 99
    # compute with current settings
    curr_two = tavist.two_handed_mode
    curr_pa = tavist.power_attack_value
    dpr = expected_full_attack(tavist, ac, curr_two, attacks, attack_names)
    window.dpr_label.setText(f"Expected DPR (AC {ac}): {dpr:.1f}")

    # also show best as a hint
    best_pa, best_two = recommend_setup(tavist, ac, attacks, attack_names)
    mode = "2H" if best_two else "TWF"
    window.reccommended_poweratt.setText(str(best_pa))
    if not window.poweratt_lock.isChecked():
        window.poweratt.blockSignals(True)
        window.poweratt.setText(str(best_pa))
        window.poweratt.blockSignals(False)
        tavist.set_power_attack(best_pa)
    window.dpr_label.setText(
        f"Expected DPR (AC {ac}): {dpr:.1f} | Best: PA {best_pa} {mode}"
    )
    tracker = getattr(window, "_ac_tracker", None)
    if tracker:
        window.ac_bound.setText(f"AC bound: {format_bound(tracker)}")


def apply_external(window: MainWindow, tavist: Tavist, attacks: list[int], attack_names: list[str]):
    try:
        hit = int(window.ext_hit.text() or "0")
    except ValueError:
        hit = 0
    try:
        strength = int(window.ext_str.text() or "0")
    except ValueError:
        strength = 0
    tavist.set_external_hit(hit)
    tavist.set_external_str(strength)
    update_dpr_label(window, tavist, attacks, attack_names)


def format_bound(tracker: ACTargetTracker) -> str:
    if tracker.upper != 99 and (tracker.upper - tracker.lower) <= 1:
        return f"== {tracker.upper}"
    return f">{tracker.lower}, ≤{tracker.upper if tracker.upper != 99 else '?'}"


def tracking_dialog(window: MainWindow, tavist: Tavist, tracker: ACTargetTracker, results: list[dict], attacks: list[int], attack_names: list[str]):
    if tracker.upper != 99 and (tracker.upper - tracker.lower) <= 1:
        return
    candidates = [r for r in results if tracker.lower < r["attack_total"] <= tracker.upper]
    if not candidates:
        return

    dialog = QDialog(window)
    dialog.setWindowTitle("Attack Results")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(f"Current AC range: {format_bound(tracker)}"))
    layout.addWidget(QLabel("Select the lowest-AC attack that HIT, or All Misses."))

    selection = {"total": None, "all_miss": False}

    for r in sorted(candidates, key=lambda x: x["attack_total"]):
        btn = QPushButton(f"{r['label']} (AC {r['attack_total']})")
        btn.setEnabled(True)

        def make_handler(total):
            def handler():
                selection["total"] = total
                dialog.accept()

            return handler

        btn.clicked.connect(make_handler(r["attack_total"]))
        layout.addWidget(btn)

    miss_btn = QPushButton("All Misses")
    miss_btn.clicked.connect(lambda: (selection.update({"all_miss": True}), dialog.accept()))
    layout.addWidget(miss_btn)

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(dialog.reject)
    layout.addWidget(cancel_btn)

    if dialog.exec() == QDialog.Accepted:
        if selection["all_miss"]:
            for r in candidates:
                tracker.record_miss(r["attack_total"])
        elif selection["total"] is not None:
            chosen = selection["total"]
            for r in candidates:
                if r["attack_total"] >= chosen:
                    tracker.record_hit(r["attack_total"])
                else:
                    tracker.record_miss(r["attack_total"])
        est = tracker.estimate()
        window.target_ac.blockSignals(True)
        window.target_ac.setText(str(est))
        window.target_ac.blockSignals(False)
        update_dpr_label(window, tavist, attacks, attack_names)
        append_log(
            window,
            f"Updated AC bound: {format_bound(tracker)} (est {est})",
        )


def main() -> None:
    app = QApplication([])
    window = MainWindow()

    tavist = Tavist()
    tracker = ACTargetTracker()
    window._ac_tracker = tracker

    attacks = [12, 12, 7, 2]
    attack_names = [f"{name} (+{atk})" for name, atk in zip(["first", "speed", "second", "third"], attacks)]

    def do_single():
        results = wrap_single_attack(window, tavist, attacks, attack_names)()
        if window.tracking.isChecked():
            tracking_dialog(window, tavist, tracker, results, attacks, attack_names)
    window.attack_button.clicked.connect(do_single)

    def do_full():
        results = wrap_full_attack(window, tavist, attack_names, attacks)()
        if window.tracking.isChecked():
            tracking_dialog(window, tavist, tracker, results, attacks, attack_names)
    window.full_attack.clicked.connect(do_full)

    def apply_two_handed(checked: bool):
        tavist.set_two_handed(checked)
        tavist.bab.bonus = attacks[0]
        update_dpr_label(window, tavist, attacks, attack_names)

    window.two_handed.toggled.connect(apply_two_handed)
    window.auto_button.clicked.connect(
        wrap_auto_recommend(window, tavist, attacks, attack_names)
    )
    apply_two_handed(window.two_handed.isChecked())

    window.evil.clicked.connect(
        make_dice_toggle(tavist.katana_damage, tavist.holy_dice)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.katana_damage, tavist.surge_bonus_main)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.wakasashi_damage, tavist.surge_bonus_off)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.katana_attack, tavist.surge_bonus_attack_main)
    )
    # off-hand surge attack bonus applies only in dual-wield mode; handled in attack setup

    window.poweratt.textChanged.connect(make_power_attack_update(tavist))
    window.poweratt.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )

    window.expertise.textChanged.connect(make_attack_update(tavist.combat_expertise))
    window.expertise.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )
    window.target_ac.textChanged.connect(
        lambda _: update_dpr_label(window, tavist, attacks, attack_names)
    )
    window.ext_hit.textChanged.connect(lambda _: apply_external(window, tavist, attacks, attack_names))
    window.ext_str.textChanged.connect(lambda _: apply_external(window, tavist, attacks, attack_names))
    def apply_fatigue(checked: bool):
        tavist.set_fatigued(checked)
        update_dpr_label(window, tavist, attacks, attack_names)
    window.fatigued.toggled.connect(apply_fatigue)
    def on_tracking_toggled(checked: bool):
        if checked:
            tracker.reset()
    window.tracking.toggled.connect(on_tracking_toggled)

    update_dpr_label(window, tavist, attacks, attack_names)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()

from contextlib import redirect_stdout
import sys
from dataclasses import dataclass, field
from enum import Enum
from random import randint
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tavist")

        poweratt_layout = QHBoxLayout()
        self.target_ac = QLineEdit()
        self.target_ac.setText("")
        self.target_ac.setInputMask("00")

        self.reccommended_poweratt = QLabel()
        self.poweratt = QLineEdit("0")
        poweratt_layout.addWidget(QLabel("Target AC:"))
        poweratt_layout.addWidget(self.target_ac)
        poweratt_layout.addWidget(QLabel("Base:"))
        poweratt_layout.addWidget(self.reccommended_poweratt)
        poweratt_layout.addWidget(QLabel("Pwr Att:"))
        poweratt_layout.addWidget(self.poweratt)

        poweratt_group = QGroupBox("Power Attack:")
        poweratt_group.setLayout(poweratt_layout)

        expertise_layout = QHBoxLayout()
        self.expertise = QLineEdit()
        self.expertise.setText("")
        self.expertise.setInputMask("00")
        expertise_layout.addWidget(QLabel("Combat Expertise:"))
        expertise_layout.addWidget(self.expertise)
        expertise_group = QGroupBox("Combat Expertise:")
        expertise_group.setLayout(expertise_layout)

        status_layout = QHBoxLayout()

        self.evil = QPushButton()
        self.evil.setCheckable(True)
        self.evil.setChecked(False)
        self.evil.setText("Evil")

        self.surge = QPushButton()
        self.surge.setCheckable(True)
        self.surge.setChecked(False)
        self.surge.setText("Power Surge")

        status_layout.addWidget(self.evil)
        status_layout.addWidget(self.surge)

        status_group = QGroupBox("Status")
        status_group.setLayout(status_layout)

        katana_layout = QHBoxLayout()
        self.katana_attacks = [QPushButton() for i in range(4)]
        for button in self.katana_attacks:
            katana_layout.addWidget(button)
        katana_group = QGroupBox("Katana")
        katana_group.setLayout(katana_layout)

        wakasashi_layout = QHBoxLayout()
        self.wakasashi_attack = QPushButton()
        wakasashi_layout.addWidget(self.wakasashi_attack)
        wakasashi_group = QGroupBox("Wakasashi")
        wakasashi_group.setLayout(wakasashi_layout)

        main_layout = QVBoxLayout()
        main_layout.addWidget(poweratt_group)
        main_layout.addWidget(expertise_group)
        main_layout.addWidget(status_group)
        main_layout.addWidget(katana_group)
        main_layout.addWidget(wakasashi_group)

        self.full_attack = QPushButton("Full Attack")
        main_layout.addWidget(self.full_attack)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(160)
        main_layout.addWidget(self.log_output)

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)


class BonusType(Enum):
    UNNAMED = "unnamed"
    BAB = "base-attack-bonus"
    ABILITY = "ability"
    ENHANCEMENT = "enhancement"
    TWO_WEAPONS = "two-weapons"
    WEAPON_FOCUS = "weapon-focus"
    POWER_ATTACK = "power-attack"


class DamageType(Enum):
    SLASHING = "slashing"


@dataclass()
class Bonus:
    bonus: int = 0
    type: BonusType = BonusType.UNNAMED
    label: str | None = None


@dataclass(kw_only=True)
class Dice:
    d: int = 20
    n: int = 1
    label: str | None = None


@dataclass(kw_only=True)
class DamageDice(Dice):
    pass


@dataclass(kw_only=True)
class WeaponDamageDice(Dice):
    pass


@dataclass
class RolledDice:
    label: str | None
    rolls: list[list[int]] = field(default_factory=list)
    bonuses: list[Bonus] = field(default_factory=list)
    total: int = 0
    dice: list[Dice] = field(default_factory=list)


@dataclass(kw_only=True)
class Roll:
    label: str | None = None
    dice: list[Dice] = field(default_factory=list)
    bonuses: list[Bonus] = field(default_factory=list)

    def roll(self) -> RolledDice:
        rolled_dice = RolledDice(self.label)
        rolled_dice.dice = self.dice
        rolled_dice.rolls = []
        for roll in self.dice:
            rolls = []
            for n in range(roll.n):
                rolled_die = randint(1, roll.d)
                rolls.append(rolled_die)
                rolled_dice.total += rolled_die
            rolled_dice.rolls.append(rolls)

        rolled_dice.bonuses = self.bonuses
        for bonus in self.bonuses:
            rolled_dice.total += bonus.bonus

        return rolled_dice


@dataclass(kw_only=True)
class AttackRoll(Roll):
    critical_threshold: int = 20

    def __post_init__(self):
        self.dice.append(Dice(d=20, label="attack"))


@dataclass(kw_only=True)
class DamageRoll(Roll):
    type: DamageType

    def roll(self, critical: bool = False) -> RolledDice:
        rolled_dice = RolledDice(self.label)
        rolled_dice.dice = self.dice
        rolled_dice.rolls = []
        for roll in self.dice:
            rolls = []
            for n in range(roll.n):
                rolled_die = randint(1, roll.d)
                rolls.append(rolled_die)
                rolled_dice.total += (
                    rolled_die * 2
                    if isinstance(roll, WeaponDamageDice) and critical
                    else rolled_die
                )
            rolled_dice.rolls.append(rolls)

        rolled_dice.bonuses = self.bonuses
        for bonus in self.bonuses:
            rolled_dice.total += bonus.bonus * 2 if critical else bonus.bonus

        return rolled_dice


@dataclass(kw_only=True)
class AttackAction:
    label: str
    attack: AttackRoll
    damage: DamageRoll

    def do_attack(self):
        attack_roll = self.attack.roll()
        attack_die = attack_roll.rolls[0][0]
        threat = attack_die >= self.attack.critical_threshold
        confirm_roll = self.attack.roll() if threat else None

        damage_roll = self.damage.roll(critical=False)
        damage_breakdown: dict[str, dict[str, int]] = {}
        weapon_label = self.damage.type.value
        attack_mods = []
        for bonus in attack_roll.bonuses:
            name = bonus.type.value if bonus.type != BonusType.UNNAMED else bonus.label or "unnamed"
            attack_mods.append(f"{name}[{bonus.bonus:+}]")
        attack_mods_text = " + ".join(attack_mods) if attack_mods else "no modifiers"

        damage_dice_parts = []
        for idx, die in enumerate(damage_roll.dice):
            rolls = ",".join(str(r) for r in damage_roll.rolls[idx])
            crit_tag = " *2 on crit" if isinstance(die, WeaponDamageDice) else ""
            damage_dice_parts.append(f"{die.label}: d{die.d}({rolls}){crit_tag}")
            normal = sum(damage_roll.rolls[idx])
            crit_val = normal * (2 if isinstance(die, WeaponDamageDice) else 1)
            label = weapon_label if isinstance(die, WeaponDamageDice) else die.label or "damage"
            bucket = damage_breakdown.setdefault(label, {"normal": 0, "critical": 0})
            bucket["normal"] += normal
            bucket["critical"] += crit_val
        damage_dice_text = " | ".join(damage_dice_parts) if damage_dice_parts else "none"

        damage_bonus_parts = []
        for bonus in damage_roll.bonuses:
            name = (
                weapon_label
                if bonus.type in (BonusType.ABILITY, BonusType.ENHANCEMENT)
                else bonus.type.value
                if bonus.type != BonusType.UNNAMED
                else bonus.label
                or "unnamed"
            )
            damage_bonus_parts.append(f"{name}[{bonus.bonus:+}] *2 on crit")
            bucket = damage_breakdown.setdefault(name, {"normal": 0, "critical": 0})
            bucket["normal"] += bonus.bonus
            bucket["critical"] += bonus.bonus * 2
        damage_bonus_text = " + ".join(damage_bonus_parts) if damage_bonus_parts else "none"

        damage_base = 0
        damage_crit = 0
        for values in damage_breakdown.values():
            damage_base += values["normal"]
            damage_crit += values["critical"]

        breakdown_normal = {label: vals["normal"] for label, vals in damage_breakdown.items() if vals["normal"] != 0}
        breakdown_critical = {label: vals["critical"] for label, vals in damage_breakdown.items() if vals["critical"] != 0}

        def format_breakdown_map(mapping: dict[str, int]) -> str:
            if not mapping:
                return "none"
            parts = [f"{k} {v}" for k, v in sorted(mapping.items())]
            return ", ".join(parts)

        lines = [
            f"=== Attack: {self.label} ===",
            f"Attack total: {attack_roll.total} (d20={attack_die}{' CRIT THREAT' if threat else ''})",
            f"Attack mods: {attack_mods_text}",
        ]
        if threat and confirm_roll is not None:
            lines.append(
                f"Confirm roll: {confirm_roll.total} (crit confirms on AC ≤ {confirm_roll.total})"
            )
        else:
            lines.append("No critical threat")

        lines += [
            f"Damage (normal): {damage_base}",
            f"Damage (critical): {damage_crit} (if confirmed)",
            f"Breakdown normal: {format_breakdown_map(breakdown_normal)}",
            f"Breakdown critical: {format_breakdown_map(breakdown_critical)}",
            f"Damage dice: {damage_dice_text}",
            f"Damage mods: {damage_bonus_text}",
        ]
        print("\n".join(lines))
        print()
        return {
            "label": self.label,
            "attack_total": attack_roll.total,
            "attack_die": attack_die,
            "threat": threat,
            "confirm_total": confirm_roll.total if confirm_roll else None,
            "damage_normal": damage_base,
            "damage_critical": damage_crit,
            "breakdown_normal": breakdown_normal,
            "breakdown_critical": breakdown_critical,
        }


class Tavist:
    def __init__(self):
        self.poweratt_damage_bonus: Bonus = Bonus(
            type=BonusType.POWER_ATTACK, label="power attack"
        )
        self.poweratt_attack_penalty: Bonus = Bonus(
            type=BonusType.POWER_ATTACK, label="power attack"
        )
        self.bab = Bonus(12, BonusType.BAB)
        self.combat_expertise = Bonus(0, label="expertise")

        self.holy_dice: DamageDice = DamageDice(n=2, d=6, label="holy")
        self.surge_bonus: Bonus = Bonus(bonus=4, label="power-surge")

        tavist_melee_attack_bonus = [
            Bonus(4, BonusType.ABILITY),
            self.bab,
            self.combat_expertise,
            Bonus(-2, BonusType.TWO_WEAPONS),
            self.poweratt_attack_penalty,
        ]

        tavist_melee_damage_bonus = [
            Bonus(4, BonusType.ABILITY),
            self.poweratt_damage_bonus,
        ]

        self.katana_attack = AttackRoll(
            critical_threshold=17,
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                Bonus(1, BonusType.WEAPON_FOCUS),
                *tavist_melee_attack_bonus,
            ],
        )

        self.wakasashi_attack = AttackRoll(
            bonuses=[Bonus(2, BonusType.ENHANCEMENT), *tavist_melee_attack_bonus]
        )

        self.katana_damage = DamageRoll(
            type=DamageType.SLASHING,
            dice=[
                WeaponDamageDice(d=10, label="weapon"),
                DamageDice(d=6, label="merciful"),
            ],
            bonuses=[Bonus(2, BonusType.ENHANCEMENT), *tavist_melee_damage_bonus],
        )

        self.wakasashi_damage = DamageRoll(
            type=DamageType.SLASHING,
            dice=[WeaponDamageDice(d=6, label="weapon"), Dice(d=6, label="merciful")],
            bonuses=[Bonus(1, BonusType.ENHANCEMENT), *tavist_melee_damage_bonus],
        )

        self.katana_attack_action = AttackAction(
            label="first", attack=self.katana_attack, damage=self.katana_damage
        )

        self.wakasashi_attack_action = AttackAction(
            label="off-hand", attack=self.wakasashi_attack, damage=self.wakasashi_damage
        )


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


def make_attack_update(bonus: Bonus):
    def attack_update(text: str):
        try:
            bonus.bonus = -int(text)
        except ValueError:
            bonus.bonus = 0

    return attack_update


def recommended_poweratt(window):
    def wrapped(ac: str):
        try:
            ac_int = int(ac)
        except ValueError:
            ac_int = 99
        recommended = str(-min(max(-12, ac_int - 19), 0))
        window.reccommended_poweratt.setText(recommended)

    return wrapped


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
    window.log_output.appendPlainText(text)
    cursor = window.log_output.textCursor()
    cursor.movePosition(QTextCursor.End)
    window.log_output.setTextCursor(cursor)
    window.log_output.ensureCursorVisible()


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
                if r["threat"] and r["confirm_total"] is not None:
                    normal_bd = ", ".join(
                        f"{k} {v}" for k, v in sorted(r["breakdown_normal"].items())
                    ) or "none"
                    crit_bd = ", ".join(
                        f"{k} {v}" for k, v in sorted(r["breakdown_critical"].items())
                    ) or "none"
                    append_log(
                        window,
                        f"{r['label']}: hits AC {r['attack_total']} | threat (crit confirms on AC ≤ {r['confirm_total']}) "
                        f"normal {r['damage_normal']} dmg [{normal_bd}] / crit {r['damage_critical']} dmg [{crit_bd}]",
                    )
                else:
                    append_log(
                        window,
                        f"{r['label']}: hits AC {r['attack_total']} | damage {r['damage_normal']} dmg "
                        f"[{', '.join(f'{k} {v}' for k, v in sorted(r['breakdown_normal'].items())) or 'none'}]",
                    )
        append_log(window, "")

    return do_full_attack


def main() -> None:
    app = QApplication([])
    window = MainWindow()

    tavist = Tavist()

    attacks = [12, 12, 7, 2]
    attack_names = ["first", "speed", "second", "third"]
    for idx, attack in enumerate(window.katana_attacks):
        attack.clicked.connect(
            wrap_bonus_adjustment(
                tavist.katana_attack_action, attack_names[idx], tavist.bab, attacks[idx]
            )
        )
        attack.clicked.connect(perform_attack_with_log(tavist.katana_attack_action, window))
        attack.setText(attack_names[idx])

    window.wakasashi_attack.clicked.connect(
        wrap_bonus_adjustment(
            tavist.wakasashi_attack_action, "off-hand", tavist.bab, 12
        )
    )
    window.wakasashi_attack.clicked.connect(
        perform_attack_with_log(tavist.wakasashi_attack_action, window)
    )
    window.wakasashi_attack.setText(tavist.wakasashi_attack_action.label)

    window.full_attack.clicked.connect(
        wrap_full_attack(window, tavist, attack_names, attacks)
    )

    window.evil.clicked.connect(
        make_dice_toggle(tavist.katana_damage, tavist.holy_dice)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.katana_damage, tavist.surge_bonus)
    )
    window.surge.clicked.connect(
        make_bonus_toggle(tavist.wakasashi_damage, tavist.surge_bonus)
    )

    window.target_ac.textChanged.connect(recommended_poweratt(window))
    window.poweratt.textChanged.connect(
        make_damage_update(tavist.poweratt_damage_bonus)
    )
    window.poweratt.textChanged.connect(
        make_attack_update(tavist.poweratt_attack_penalty)
    )

    window.expertise.textChanged.connect(make_attack_update(tavist.combat_expertise))

    window.show()
    app.exec()


if __name__ == "__main__":
    main()

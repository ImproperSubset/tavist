from dataclasses import KW_ONLY, dataclass, field
from logging import CRITICAL, critical
from multiprocessing import Value
from random import randint
from enum import Enum
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QWidget, QLineEdit, QLabel)
from copy import copy


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

        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)


class BonusType(Enum):
    UNNAMED = 'unnamed'
    BAB = "base-attack-bonus"
    ABILITY = 'ability'
    ENHANCEMENT = 'enhancement'
    TWO_WEAPONS = 'two-weapons'
    WEAPON_FOCUS = 'weapon-focus'
    POWER_ATTACK = 'power-attack'


class DamageType(Enum):
    SLASHING = 'slashing'


@dataclass()
class Bonus():
    bonus: int = 0
    type: BonusType = BonusType.UNNAMED
    label: str = None


@dataclass(kw_only=True)
class Dice:
    d: int = 20
    n: int = 1
    label: str = None


@dataclass(kw_only=True)
class DamageDice(Dice):
    pass


@dataclass(kw_only=True)
class WeaponDamageDice(Dice):
    pass


@dataclass
class RolledDice():
    rolls: list[list[int]] = field(default_factory=list)
    bonuses: list[Bonus] = field(default_factory=list)
    total: int = 0
    dice: list[Dice] = field(default_factory=list)


@dataclass(kw_only=True)
class Roll():
    label: str = None
    dice: list[Dice] = field(default_factory=list)
    bonuses: list[Bonus] = field(default_factory=list)

    def roll(self) -> RolledDice:
        rolled_dice = RolledDice()
        rolled_dice.dice = self.dice
        rolled_dice.label = self.label
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
        self.dice.append(Dice(d=20, label='attack'))


@dataclass(kw_only=True)
class DamageRoll(Roll):
    type: DamageType

    def roll(self, critical: bool = False) -> RolledDice:
        rolled_dice = RolledDice()
        rolled_dice.dice = self.dice
        rolled_dice.label = self.label
        rolled_dice.rolls = []
        for roll in self.dice:
            rolls = []
            for n in range(roll.n):
                rolled_die = randint(1, roll.d)
                rolls.append(rolled_die)
                rolled_dice.total += rolled_die * \
                    2 if isinstance(
                        roll, WeaponDamageDice) and critical else rolled_die
            rolled_dice.rolls.append(rolls)

        rolled_dice.bonuses = self.bonuses
        for bonus in self.bonuses:
            rolled_dice.total += bonus.bonus*2 if critical else bonus.bonus

        return rolled_dice


@dataclass(kw_only=True)
class AttackAction():
    label: str
    attack: AttackRoll
    damage: DamageRoll

    def do_attack(self):
        attack_roll = self.attack.roll()
        print(f"Attack[{self.label}] hits AC: {attack_roll.total}", end='')
        attack_die = attack_roll.rolls[0][0]
        critical = attack_die >= self.attack.critical_threshold
        if critical:
            print(" CRITICAL HIT!", end='')
        print()

        for idx, die in enumerate(attack_roll.dice):
            print(f"  {die.label}[", end='')
            print(f"d{die.d}({attack_roll.rolls[idx]})", end='')
            print(f"]", end='')
        for bonus in attack_roll.bonuses:
            if bonus.type != BonusType.UNNAMED:
                print(f" {bonus.type.value}", end='')
            else:
                print(f" {bonus.label}", end='')
            print(f"[{bonus.bonus:+}]", end='')
        print()

        damage_roll = self.damage.roll(critical)
        print(f"Damage {damage_roll.total}")
        print("  ", end='')
        for idx, die in enumerate(damage_roll.dice):
            if idx != 0:
                print(" + ", end='')
            print(f"{die.label}[", end='')
            print(f"d{die.d}({damage_roll.rolls[idx]})", end='')
            print(f"]", end='')
            if critical and idx == 0:
                print("*2", end='')
        print(" + ", end='')
        if critical:
            print("( ", end='')
        for idx, bonus in enumerate(damage_roll.bonuses):
            if idx != 0:
                print(" + ", end='')
            if bonus.type != BonusType.UNNAMED:
                print(f"{bonus.type.value}", end='')
            else:
                print(f"{bonus.label}", end='')
            print(f"[{bonus.bonus:+}]", end='')
        if critical:
            print(" )*2", end='')
        print()
        print()


class Tavist():

    def __init__(self):

        self.poweratt_damage_bonus: Bonus = Bonus(
            type=BonusType.POWER_ATTACK, label='power attack')
        self.poweratt_attack_penalty: Bonus = Bonus(
            type=BonusType.POWER_ATTACK, label='power attack')
        self.bab = Bonus(12, BonusType.BAB)
        self.combat_expertise = Bonus(0, label="expertise")

        self.holy_dice: DamageDice = DamageDice(n=2, d=6, label='holy')
        self.surge_bonus: Bonus = Bonus(bonus=4, label='power-surge')

        tavist_melee_attack_bonus = [
            Bonus(4, BonusType.ABILITY),
            self.bab,
            self.combat_expertise,
            Bonus(-2, BonusType.TWO_WEAPONS),
            self.poweratt_attack_penalty
        ]

        tavist_melee_damage_bonus = [
            Bonus(4, BonusType.ABILITY),
            self.poweratt_damage_bonus
        ]

        self.katana_attack = AttackRoll(
            critical_threshold=17,
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                Bonus(1, BonusType.WEAPON_FOCUS),
                *tavist_melee_attack_bonus
            ])

        self.wakasashi_attack = AttackRoll(
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                *tavist_melee_attack_bonus
            ])

        self.katana_damage = DamageRoll(
            type=DamageType.SLASHING,
            dice=[
                WeaponDamageDice(d=10, label='weapon'),
                DamageDice(d=6, label='merciful')
            ],
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                *tavist_melee_damage_bonus
            ])

        self.wakasashi_damage = DamageRoll(
            type=DamageType.SLASHING,
            dice=[
                WeaponDamageDice(d=6, label='weapon'),
                Dice(d=6, label='merciful')
            ],
            bonuses=[
                Bonus(1, BonusType.ENHANCEMENT),
                *tavist_melee_damage_bonus
            ])

        self.katana_attack_action = AttackAction(
            label="first",
            attack=self.katana_attack,
            damage=self.katana_damage
        )

        self.wakasashi_attack_action = AttackAction(
            label="off-hand",
            attack=self.wakasashi_attack,
            damage=self.wakasashi_damage
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


def make_damage_update(roll: Roll):
    def damage_update(text: str):
        try:
            roll.bonus = int(text)
        except ValueError:
            roll.bonus = 0
    return damage_update


def make_attack_update(roll: Roll):
    def attack_update(text: str):
        try:
            roll.bonus = -int(text)
        except ValueError:
            roll.bonus = 0
    return attack_update


def recommended_poweratt(window):
    def wrapped(ac: str):
        try:
            ac_int = int(ac)
        except ValueError:
            ac_int = 99
        recommended = str(-min(max(-12, ac_int-19), 0))
        window.reccommended_poweratt.setText(recommended)
    return wrapped


def wrap_attack(attack: AttackAction):
    def do_attack():
        attack.do_attack()
    return do_attack


def wrap_bonus_adjustment(attack: AttackAction, name: str, bonus: Bonus, value: int):
    def bonus_adjustment():
        attack.label = name
        bonus.bonus = value
    return bonus_adjustment


def main() -> None:
    app = QApplication([])
    window = MainWindow()

    tavist = Tavist()

    attacks = [12, 12, 7, 2]
    attack_names = ['first', 'speed', 'second', 'third']
    for idx, attack in enumerate(window.katana_attacks):
        attack.clicked.connect(wrap_bonus_adjustment(
            tavist.katana_attack_action, attack_names[idx], tavist.bab, attacks[idx]))
        attack.clicked.connect(wrap_attack(tavist.katana_attack_action))
        attack.setText(attack_names[idx])

    window.wakasashi_attack.clicked.connect(
        wrap_bonus_adjustment(tavist.wakasashi_attack_action,'off-hand',tavist.bab, 12))
    window.wakasashi_attack.clicked.connect(
        wrap_attack(tavist.wakasashi_attack_action))
    window.wakasashi_attack.setText(tavist.wakasashi_attack_action.label)

    window.evil.clicked.connect(make_dice_toggle(
        tavist.katana_damage, tavist.holy_dice))
    window.surge.clicked.connect(make_bonus_toggle(
        tavist.katana_damage, tavist.surge_bonus))
    window.surge.clicked.connect(make_bonus_toggle(
        tavist.wakasashi_damage, tavist.surge_bonus))

    window.target_ac.textChanged.connect(recommended_poweratt(window))
    window.poweratt.textChanged.connect(
        make_damage_update(tavist.poweratt_damage_bonus))
    window.poweratt.textChanged.connect(
        make_attack_update(tavist.poweratt_attack_penalty))

    window.expertise.textChanged.connect(
        make_attack_update(tavist.combat_expertise))

    window.show()
    app.exec()


if __name__ == "__main__":
    main()

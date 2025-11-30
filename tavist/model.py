from dataclasses import dataclass, field
from enum import Enum
from random import randint


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
    PIERCING = "piercing"


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
        for die in self.dice:
            rolls = []
            repeat = die.n * (2 if critical and isinstance(die, WeaponDamageDice) else 1)
            for _ in range(repeat):
                rolled_die = randint(1, die.d)
                rolls.append(rolled_die)
                rolled_dice.total += rolled_die
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
        nat_one = attack_die == 1
        nat_twenty = attack_die == 20

        damage_roll = self.damage.roll(critical=False)
        crit_damage_roll = self.damage.roll(critical=True)
        weapon_label = self.damage.type.value
        attack_mods = []
        for bonus in attack_roll.bonuses:
            name = bonus.type.value if bonus.type != BonusType.UNNAMED else bonus.label or "unnamed"
            attack_mods.append(f"{name}[{bonus.bonus:+}]")
        attack_mods_text = " + ".join(attack_mods) if attack_mods else "no modifiers"

        def format_rolls(die: Dice, rolls: list[int]) -> str:
            joined = ",".join(str(r) for r in rolls)
            return f"d{die.d}({joined})"

        damage_dice_parts = []
        for idx, die in enumerate(damage_roll.dice):
            label = die.label or "damage"
            normal_rolls = format_rolls(die, damage_roll.rolls[idx])
            crit_rolls = format_rolls(die, crit_damage_roll.rolls[idx])
            crit_tag = " *2 on crit" if isinstance(die, WeaponDamageDice) else ""
            if crit_rolls != normal_rolls:
                damage_dice_parts.append(f"{label}: {normal_rolls}{crit_tag}; crit: {crit_rolls}")
            else:
                damage_dice_parts.append(f"{label}: {normal_rolls}{crit_tag}")
        damage_dice_text = " | ".join(damage_dice_parts) if damage_dice_parts else "none"

        damage_bonus_parts = []
        for bonus in damage_roll.bonuses:
            name = (
                weapon_label
                if bonus.type
                in (
                    BonusType.ABILITY,
                    BonusType.ENHANCEMENT,
                    BonusType.POWER_ATTACK,
                )
                else bonus.type.value
                if bonus.type != BonusType.UNNAMED
                else bonus.label
                or "unnamed"
            )
            damage_bonus_parts.append(f"{name}[{bonus.bonus:+}] *2 on crit")
        damage_bonus_text = " + ".join(damage_bonus_parts) if damage_bonus_parts else "none"

        def build_breakdown(rolled: RolledDice, critical: bool) -> dict[str, int]:
            breakdown: dict[str, int] = {}
            for idx, die in enumerate(rolled.dice):
                label = weapon_label if isinstance(die, WeaponDamageDice) else die.label or "damage"
                total = sum(rolled.rolls[idx])
                breakdown[label] = breakdown.get(label, 0) + total
            for bonus in rolled.bonuses:
                name = (
                    weapon_label
                    if bonus.type
                    in (
                        BonusType.ABILITY,
                        BonusType.ENHANCEMENT,
                        BonusType.POWER_ATTACK,
                    )
                    else bonus.type.value
                    if bonus.type != BonusType.UNNAMED
                    else bonus.label
                    or "unnamed"
                )
                bonus_total = bonus.bonus * 2 if critical else bonus.bonus
                breakdown[name] = breakdown.get(name, 0) + bonus_total
            return breakdown

        breakdown_normal = {label: val for label, val in build_breakdown(damage_roll, critical=False).items() if val != 0}
        breakdown_critical = {
            label: val for label, val in build_breakdown(crit_damage_roll, critical=True).items() if val != 0
        }

        damage_base = sum(breakdown_normal.values())
        damage_crit = sum(breakdown_critical.values())

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
        if nat_one:
            lines.append("Natural 1: automatic miss")
        elif threat and confirm_roll is not None:
            lines.append(
                f"Confirm roll: {confirm_roll.total} (crit confirms on AC {confirm_roll.total})"
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
            "natural_one": nat_one,
            "natural_twenty": nat_twenty,
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
        self.surge_bonus_main: Bonus = Bonus(bonus=4, type=BonusType.ABILITY, label="power-surge")
        self.surge_bonus_off: Bonus = Bonus(bonus=2, type=BonusType.ABILITY, label="power-surge")
        self.surge_bonus_attack_main: Bonus = Bonus(bonus=4, type=BonusType.ABILITY, label="power-surge")
        self.surge_bonus_attack_off: Bonus = Bonus(bonus=4, type=BonusType.ABILITY, label="power-surge")
        self.fatigue_penalty: Bonus = Bonus(0, BonusType.UNNAMED, label="fatigued")
        self.fatigue_str: Bonus = Bonus(0, BonusType.ABILITY, label="fatigued-str")
        self.external_hit: Bonus = Bonus(0, BonusType.UNNAMED, label="ext-hit")
        self.external_str: Bonus = Bonus(0, BonusType.UNNAMED, label="ext-str")

        self.two_weapon_penalty = Bonus(-2, BonusType.TWO_WEAPONS)

        tavist_melee_attack_bonus = [
            Bonus(4, BonusType.ABILITY),
            self.bab,
            self.combat_expertise,
            self.two_weapon_penalty,
            self.poweratt_attack_penalty,
            self.fatigue_penalty,
            self.external_hit,
        ]

        self.ability_main = Bonus(4, BonusType.ABILITY)
        self.ability_off = Bonus(2, BonusType.ABILITY)
        self.ability_ext_main = Bonus(0, BonusType.ABILITY, label="ext-str")
        self.ability_ext_off = Bonus(0, BonusType.ABILITY, label="ext-str")
        self.ability_fatigue_main = Bonus(0, BonusType.ABILITY, label="fatigue")
        self.ability_fatigue_off = Bonus(0, BonusType.ABILITY, label="fatigue")
        self.poweratt_damage_bonus_main = Bonus(
            type=BonusType.POWER_ATTACK, label="power attack"
        )
        self.poweratt_damage_bonus_off = Bonus(
            type=BonusType.POWER_ATTACK, label="power attack"
        )

        self.katana_attack = AttackRoll(
            critical_threshold=17,  # bastard sword 19-20, keen doubles to 17-20
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                Bonus(1, BonusType.WEAPON_FOCUS),
                self.surge_bonus_attack_main,
                *tavist_melee_attack_bonus,
            ],
        )

        self.wakasashi_attack = AttackRoll(
            critical_threshold=19,  # short sword 19-20
            bonuses=[Bonus(2, BonusType.ENHANCEMENT), self.surge_bonus_attack_off, *tavist_melee_attack_bonus],
        )

        self.katana_damage = DamageRoll(
            type=DamageType.SLASHING,
            dice=[
                WeaponDamageDice(d=10, label="weapon"),
                DamageDice(d=6, label="merciful"),
            ],
            bonuses=[
                Bonus(2, BonusType.ENHANCEMENT),
                self.ability_main,
                self.ability_ext_main,
                self.ability_fatigue_main,
                self.poweratt_damage_bonus_main,
                self.surge_bonus_main,
            ],
        )

        self.wakasashi_damage = DamageRoll(
            type=DamageType.PIERCING,
            dice=[WeaponDamageDice(d=6, label="weapon"), Dice(d=6, label="merciful")],
            bonuses=[
                Bonus(1, BonusType.ENHANCEMENT),
                self.ability_off,
                self.ability_ext_off,
                self.ability_fatigue_off,
                self.poweratt_damage_bonus_off,
                self.surge_bonus_off,
            ],
        )

        self.katana_attack_action = AttackAction(
            label="first", attack=self.katana_attack, damage=self.katana_damage
        )

        self.wakasashi_attack_action = AttackAction(
            label="off-hand", attack=self.wakasashi_attack, damage=self.wakasashi_damage
        )

        self.power_attack_value = 0
        self.two_handed_mode = False
        self.poweratt_scale_main = 1.0
        self.poweratt_scale_off = 0.5
        self.set_power_attack(0)
        self._update_surge()

    def set_external_hit(self, bonus: int):
        self.external_hit.bonus = bonus

    def set_external_str(self, bonus: int):
        self.external_str.bonus = bonus
        self.ability_ext_main.bonus = bonus
        self.ability_ext_off.bonus = bonus // 2

    def set_power_attack(self, value: int):
        self.power_attack_value = max(0, value)
        self.poweratt_attack_penalty.bonus = -self.power_attack_value
        self.poweratt_damage_bonus_main.bonus = int(self.power_attack_value * self.poweratt_scale_main)
        self.poweratt_damage_bonus_off.bonus = int(self.power_attack_value * self.poweratt_scale_off)
        self._update_surge()

    def set_two_handed(self, two_handed: bool):
        self.two_handed_mode = two_handed
        if two_handed:
            self.two_weapon_penalty.bonus = 0
            self.ability_main.bonus = 6  # 1.5x Str
            self.ability_off.bonus = 0
            self.ability_fatigue_main.bonus = -1  # effective -2 Str -> -1 damage two-hand
            self.ability_fatigue_off.bonus = 0
            self.poweratt_scale_main = 2.0
            self.poweratt_scale_off = 0.0
        else:
            self.two_weapon_penalty.bonus = -2
            self.ability_main.bonus = 4
            self.ability_off.bonus = 2
            self.ability_fatigue_main.bonus = -1  # -2 Str -> -1 damage main
            self.ability_fatigue_off.bonus = -1  # off-hand uses half Str but we store as bonus directly
            self.poweratt_scale_main = 1.0
            self.poweratt_scale_off = 0.5
        self.set_power_attack(self.power_attack_value)
        self._update_surge()

    def _update_surge(self):
        if self.two_handed_mode:
            self.surge_bonus_main.bonus = 6
            self.surge_bonus_off.bonus = 0
        else:
            self.surge_bonus_main.bonus = 4
            self.surge_bonus_off.bonus = 2

    def set_fatigued(self, fatigued: bool):
        if fatigued:
            self.fatigue_penalty.bonus = -2  # to hit
            # effective -2 Str: -1 damage main, -1 damage off (stored directly)
            self.ability_fatigue_main.bonus = -1 if not self.two_handed_mode else -1
            self.ability_fatigue_off.bonus = -1 if not self.two_handed_mode else 0
        else:
            self.fatigue_penalty.bonus = 0
            self.ability_fatigue_main.bonus = 0
            self.ability_fatigue_off.bonus = 0


def expected_attack_damage(action: AttackAction, ac: int) -> float:
    atk_bonus = sum(b.bonus for b in action.attack.bonuses)
    threshold = action.attack.critical_threshold

    mean_normal = sum(d.n * (d.d + 1) / 2 for d in action.damage.dice) + sum(
        b.bonus for b in action.damage.bonuses
    )
    mean_crit = sum(
        d.n * (d.d + 1) / 2 * (2 if isinstance(d, WeaponDamageDice) else 1)
        for d in action.damage.dice
    ) + sum(b.bonus * 2 for b in action.damage.bonuses)

    def hit_for_roll(r: int) -> bool:
        if r == 1:
            return False
        if r == 20:
            return True
        return r + atk_bonus >= ac

    hit_count = 0
    threat_count = 0
    for r in range(1, 21):
        if hit_for_roll(r):
            hit_count += 1
            if r >= threshold:
                threat_count += 1
    hit_prob = hit_count / 20
    threat_prob = threat_count / 20

    confirm_count = 0
    for r in range(1, 21):
        if hit_for_roll(r):
            confirm_count += 1
    confirm_prob = confirm_count / 20

    extra_on_crit = mean_crit - mean_normal
    expected = hit_prob * mean_normal + threat_prob * confirm_prob * extra_on_crit
    return expected


def expected_full_attack(
    tavist: Tavist, ac: int, two_handed: bool, attacks: list[int], attack_names: list[str]
) -> float:
    prev_two = tavist.two_handed_mode
    prev_pa = tavist.power_attack_value
    prev_bab = tavist.bab.bonus

    tavist.set_two_handed(two_handed)
    total = 0.0

    for idx, bonus in enumerate(attacks):
        tavist.bab.bonus = bonus
        total += expected_attack_damage(tavist.katana_attack_action, ac)

    if not two_handed:
        tavist.bab.bonus = 12
        total += expected_attack_damage(tavist.wakasashi_attack_action, ac)

    tavist.set_two_handed(prev_two)
    tavist.set_power_attack(prev_pa)
    tavist.bab.bonus = prev_bab
    return total


def recommend_setup(
    tavist: Tavist, ac: int, attacks: list[int], attack_names: list[str]
) -> tuple[int, bool]:
    orig_pa = tavist.power_attack_value
    orig_two = tavist.two_handed_mode
    best = (0.0, 0, False)
    for two_handed in (False, True):
        pa_max = 12 if not two_handed else 12
        for pa in range(0, pa_max + 1):
            tavist.set_power_attack(pa)
            dpr = expected_full_attack(tavist, ac, two_handed, attacks, attack_names)
            if dpr > best[0]:
                best = (dpr, pa, two_handed)
    tavist.set_two_handed(orig_two)
    tavist.set_power_attack(orig_pa)
    return best[1], best[2]

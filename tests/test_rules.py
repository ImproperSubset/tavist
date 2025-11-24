import builtins

import pytest

import main


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
    monkeypatch.setattr(main, "randint", make_randint([19, 15, 3, 2]))
    attack = main.AttackRoll(bonuses=[main.Bonus(5, main.BonusType.BAB)], critical_threshold=19)
    damage = main.DamageRoll(
        type=main.DamageType.SLASHING,
        dice=[main.WeaponDamageDice(d=6, label="weapon"), main.DamageDice(d=6, label="holy")],
        bonuses=[main.Bonus(2, main.BonusType.ENHANCEMENT)],
    )
    action = main.AttackAction(label="test", attack=attack, damage=damage)

    result = action.do_attack()

    assert result["attack_die"] == 19
    assert result["attack_total"] == 24  # 19 + BAB 5
    assert result["confirm_total"] == 20  # 15 + BAB 5
    assert result["damage_normal"] == 7  # 3+2+2
    assert result["damage_critical"] == 12  # weapon doubled + bonus doubled
    assert result["threat"] is True


def test_offhand_and_twohand_scaling():
    tavist = main.Tavist()
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
    monkeypatch.setattr(main, "randint", make_randint([15, 2]))
    attack = main.AttackRoll(bonuses=[main.Bonus(5)], critical_threshold=20)
    damage = main.DamageRoll(
        type=main.DamageType.SLASHING,
        dice=[main.WeaponDamageDice(d=6, label="weapon")],
        bonuses=[
            main.Bonus(4, main.BonusType.ABILITY),
            main.Bonus(4, main.BonusType.POWER_ATTACK),
        ],
    )
    action = main.AttackAction(label="slashing-test", attack=attack, damage=damage)
    result = action.do_attack()
    assert result["breakdown_normal"] == {"slashing": 10}
    assert result["breakdown_critical"]["slashing"] == 20  # weapon die doubled, bonuses doubled


def test_expected_full_attack_prefers_two_hand_at_ac_22():
    tavist = main.Tavist()
    attacks = [12, 12, 7, 2]
    names = ["first", "speed", "second", "third"]

    dpr_dual = main.expected_full_attack(tavist, 22, False, attacks, names)
    dpr_two = main.expected_full_attack(tavist, 22, True, attacks, names)

    assert dpr_two > dpr_dual


def test_recommend_setup_returns_expected_mode():
    tavist = main.Tavist()
    attacks = [12, 12, 7, 2]
    names = ["first", "speed", "second", "third"]
    pa, two = main.recommend_setup(tavist, 22, attacks, names)

    assert two is True
    assert pa >= 0


def test_weapon_crit_ranges():
    tavist = main.Tavist()
    assert tavist.katana_attack.critical_threshold == 17
    assert tavist.wakasashi_attack.critical_threshold == 19

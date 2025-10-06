# -*- coding: utf-8 -*-
"""
Моделі Player/Enemy та допоміжне.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Tuple, Optional, List
import random
from .config import DURABILITY_MAX, CRIT_CHANCE, CRIT_MULTIPLIER

@dataclass
class Item:
    name: str
    rarity: str = "common"           # common/uncommon/rare/epic/legendary
    title: str = ""
    emoji: str = "⚪"
    type: str = "misc"               # weapon/armor/accessory/misc
    atk: int = 0
    defense: int = 0
    price: int = 10
    equipped: bool = False
    durability: int = DURABILITY_MAX
    set_id: Optional[str] = None     # для сет-бонусів
    perks: List[str] = field(default_factory=list)  # для легендарок

    def is_equippable(self) -> bool:
        return self.type in ("weapon", "armor", "accessory")

@dataclass
class Player:
    name: str = "Мандрівник"
    level: int = 1
    exp: int = 0
    hp: int = 30
    max_hp: int = 30
    atk: int = 6
    defense: int = 2
    potions: int = 2
    gold: int = 0

    # прогрес/інвентар/екіп
    inventory: list = field(default_factory=list)  # list[dict] (Item as dict)
    equipment: dict = field(default_factory=lambda: {"weapon": None, "armor": None, "accessory": None})
    upgrades: dict = field(default_factory=dict)

    # реєстрація
    class_name: str = ""
    backstory: str = ""
    registered: bool = False

    # боївка
    status: dict = field(default_factory=dict)   # {"bleed": turns_left, "stun": turns_left}
    skill_cd: dict = field(default_factory=dict) # cooldown трекер {"skill_id": turns_left}
    initiative: int = 0                          # шкала ініціативи (0..100)

    # знання вмінь і обрані у слотах (до 3)
    known_skills: list = field(default_factory=list)     # ["id_1", "id_2"...]
    slotted_skills: list = field(default_factory=list)   # max 3 активних в бою

    def is_alive(self) -> bool:
        return self.hp > 0

    def _exp_to_next(self) -> int:
        return 20 + (self.level - 1) * 10

    def gain_exp(self, amount: int) -> Tuple[int, bool]:
        self.exp += amount
        leveled = False
        while self.exp >= self._exp_to_next():
            self.exp -= self._exp_to_next()
            self.level += 1
            leveled = True
            self.max_hp += 5
            self.atk += 2
            self.defense += 1
            self.hp = self.max_hp
        return self.level, leveled

    def heal(self) -> int:
        if self.potions <= 0:
            return 0
        self.potions -= 1
        healed = min(12, self.max_hp - self.hp)
        self.hp += healed
        return healed

    def roll_player_attack(self, enemy_def: int) -> tuple[int, bool]:
        base = max(1, self.atk - enemy_def + random.randint(-2, 2))
        crit = (random.random() < CRIT_CHANCE)
        dmg = int(base * (CRIT_MULTIPLIER if crit else 1.0))
        return dmg, crit

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    atk: int
    defense: int
    exp_reward: int
    gold_reward: int
    status: dict = field(default_factory=dict)  # bleed/stun
    initiative: int = 0

    def is_alive(self) -> bool:
        return self.hp > 0

def ensure_player_ud(user_data: Dict[str, Any]) -> Player:
    """Створити гравця в user_data при потребі, повертати як Player."""
    if "player" not in user_data:
        user_data["player"] = Player().asdict()
    p = Player(**user_data["player"])
    user_data["player"] = p.asdict()
    return p

def dict_to_enemy(d: Dict[str, Any]) -> Enemy:
    return Enemy(**d)

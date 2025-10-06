# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Tuple, List


@dataclass
class Player:
    # Базові
    name: str = "Мандрівник"
    level: int = 1
    exp: int = 0
    hp: int = 30
    max_hp: int = 30
    atk: int = 6
    defense: int = 2
    potions: int = 2
    gold: int = 0

    # Прогрес/реєстрація
    class_name: str = ""
    backstory: str = ""
    registered: bool = False

    # Інвентар/апгрейди/екіп
    inventory: list = field(default_factory=list)
    upgrades: dict = field(default_factory=dict)
    equipment: dict = field(default_factory=lambda: {"weapon": None, "armor": None, "accessory": None})

    # Вміння
    skills_known: List[str] = field(default_factory=list)      # усі вивчені
    skills_loadout: List[str] = field(default_factory=list)    # активні у бою (до N)
    pending_skill_choice: bool = False                         # прапорець “є нове вміння на вибір”

    # Технічне
    def asdict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_alive(self) -> bool:
        return self.hp > 0

    def heal(self) -> int:
        if self.potions <= 0:
            return 0
        self.potions -= 1
        healed = min(12, self.max_hp - self.hp)
        self.hp += healed
        return healed

    def gain_exp(self, amount: int) -> Tuple[int, bool]:
        from .config import SKILL_SELECT_INTERVAL
        self.exp += amount
        leveled = False
        while self.exp >= self._exp_to_next():
            self.exp -= self._exp_to_next()
            self.level += 1
            leveled = True
            # Прирости характеристик
            self.max_hp += 5
            self.atk += 2
            self.defense += 1
            self.hp = self.max_hp
            # Кожні N рівнів — пропозиція вміння
            if self.level % SKILL_SELECT_INTERVAL == 0:
                self.pending_skill_choice = True
        return self.level, leveled

    def _exp_to_next(self) -> int:
        return 20 + (self.level - 1) * 10


@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    atk: int
    defense: int
    exp_reward: int
    gold_reward: int

    def is_alive(self) -> bool:
        return self.hp > 0


# ----- Хелпери стану користувача -----

def ensure_player_ud(user_data: Dict[str, Any]) -> Player:
    if "player" not in user_data:
        user_data["player"] = Player().asdict()
    p = dict_to_player(user_data["player"])
    user_data["player"] = p.asdict()
    return p

def dict_to_player(d: Dict[str, Any]) -> Player:
    return Player(**d)

def dict_to_enemy(d: Dict[str, Any]) -> Enemy:
    return Enemy(**d)

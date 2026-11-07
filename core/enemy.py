class Enemy:
    """A simple class to represent an enemy."""
    def __init__(self, name, hp, armor_class, attacks, speed=6, actions_per_turn=1, initiative=0, notes=""):
        self.name = name
        self.hp = hp
        self.armor_class = armor_class
        from copy import deepcopy
        self.attacks = deepcopy(attacks)
        self.speed = speed
        self.actions_per_turn = actions_per_turn
        self.initiative = initiative
        self.notes = notes

    def to_dict(self):
        """Serializes the enemy object to a dictionary."""
        return {
            "name": self.name,
            "hp": self.hp,
            "ac": self.armor_class, # Keep 'ac' for backward compatibility in saves
            "armor_class": self.armor_class,
            "attacks": self.attacks,
            "speed": self.speed,
            "actions_per_turn": self.actions_per_turn,
            "initiative": self.initiative,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an Enemy from a dict using a whitelist of fields and bounded numbers."""
        if not isinstance(data, dict):
            raise ValueError('Enemy data must be a dict')
        attacks = []
        raw = data.get('attacks', [])
        if isinstance(raw, (list, tuple)):
            for a in raw:
                if isinstance(a, dict):
                    attacks.append(dict(a))
                elif isinstance(a, str) and a.strip():
                    if ':' in a:
                        n, _, d = a.partition(':')
                        attacks.append({'name': n.strip() or 'Angriff', 'damage': d.strip()})
                    else:
                        attacks.append({'name': 'Angriff', 'damage': a.strip()})
        ac = data.get('armor_class', data.get('ac', 10))
        return cls(
            name=str(data.get('name', 'Unknown'))[:100],
            hp=cls._num(data.get('hp', 10), 10, -10000, 10000),
            armor_class=cls._num(ac, 10, 0, 100),
            attacks=attacks,
            speed=cls._num(data.get('speed', 6), 6, 0, 1000),
            actions_per_turn=cls._num(data.get('actions_per_turn', 1), 1, 0, 20),
            initiative=cls._num(data.get('initiative', 0), 0, -50, 50),
            notes=str(data.get('notes', '')),
        )
    @staticmethod
    def _num(value, default, lo, hi):
        if isinstance(value, bool):
            return default
        try:
            n = int(float(value))
        except (TypeError, ValueError, OverflowError):
            return default
        return max(lo, min(hi, n))

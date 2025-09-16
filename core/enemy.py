class Enemy:
    """A simple class to represent an enemy."""
    def __init__(self, name, hp, armor_class, attacks, speed=6, actions_per_turn=1, initiative=0, notes=""):
        self.name = name
        self.hp = hp
        self.armor_class = armor_class
        self.attacks = attacks # Should be a list of attack dicts
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
        """Creates an Enemy object from a dictionary."""
        # Handles both 'ac' and 'armor_class' for loading old and new data.
        armor_class = data.get("armor_class", data.get("ac", 10))
        return cls(
            name=data.get("name", "Unknown"),
            hp=data.get("hp", 10),
            armor_class=armor_class,
            attacks=data.get("attacks", []),
            speed=data.get("speed", 6),
            actions_per_turn=data.get("actions_per_turn", 1),
            initiative=data.get("initiative", 0),
            notes=data.get("notes", ""),
        )

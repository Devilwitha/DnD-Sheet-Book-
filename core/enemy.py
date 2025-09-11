class Enemy:
    """A simple class to represent an enemy."""
    def __init__(self, name, hp, ac, attacks, initiative=0, notes=""):
        self.name = name
        self.hp = hp
        self.ac = ac
        self.attacks = attacks # Should be a list of attack dicts
        self.initiative = initiative
        self.notes = notes

    def to_dict(self):
        """Serializes the enemy object to a dictionary."""
        return {
            "name": self.name,
            "hp": self.hp,
            "ac": self.ac,
            "attacks": self.attacks,
            "initiative": self.initiative,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data):
        """Creates an Enemy object from a dictionary."""
        return cls(
            name=data.get("name", "Unknown"),
            hp=data.get("hp", 10),
            ac=data.get("ac", 10),
            attacks=data.get("attacks", []),
            initiative=data.get("initiative", 0),
            notes=data.get("notes", ""),
        )

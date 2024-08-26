from dataclasses import dataclass, field


@dataclass
class PoEReq:
    level: int = 0
    dex: int = 0
    str: int = 0
    int: int = 0


@dataclass
class PoESocket:
    short: str


@dataclass
class PoEEffect:
    # Examples:
    # +25(24-28) to maximum Life
    # 32% reduced Attribute Requirements
    # Adds 20(20-26) to 47(40-47) Physical Damage
    actual_stats: list[int]
    ranges: list[list[int, int]]
    description: str
    comment_lines: list[str]


@dataclass
class PoEMod:
    category: str
    title: str
    tier: int
    tags: list[str]
    effects: list[PoEEffect]
    doubled: list[list[int, int]] = field(default_factory=lambda: []) # Populated later after initial import - points at PoEEffect idx in parent.mods and other.mods
    kept: list[list[int, int]] = field(default_factory=lambda: []) # Same as doubled, but for self idx -> output idx
    requirements: list[str] = None # Used by planner to indicate what bases are required to keep said mod

    def getSlot(self):
        known_slots = ['Implicit', 'Prefix', 'Suffix']
        for k in known_slots:
            if k in self.category:
                return k

    def stringDescription(self):
        return '\n'.join([e.description for e in self.effects])

    def __hash__(self):
        return hash(self.stringDescription())


# Unused
@dataclass
class PoEModList:
    implicits: list[PoEMod]
    prefixes: list[PoEMod]
    suffixes: list[PoEMod]


@dataclass
class PoEItem:
    iclass: str
    rarity: str
    name: str
    base: str
    traits: dict[str, float]
    req: PoEReq
    sockets: PoESocket
    ilvl: int
    mods: list[PoEMod]
    special_types: list[str] = None

    def getPrefixes(self):
        return [m for m in self.mods if m.getSlot() == 'Prefix']
    def getSuffixes(self):
        return [m for m in self.mods if m.getSlot() == 'Suffix']
    def getAffixes(self):
        return [m for m in self.mods if m.getSlot() in {'Prefix', 'Suffix'}]
    def getValuableCount(self, valuable_mods):
        count = 0
        for m in self.mods:
            for vm in valuable_mods:
                if m.stringDescription() == vm.description and m.tier <= vm.min_tier:
                    count += 1
        return count
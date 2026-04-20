VALID_COMPANIES = frozenset({
    "novo",
    "browning",
    "cholla",
    "moriah",
    "point",
    "sogc",
    "stephens",
    "trp",
    "upwing",
    "chord",
    "cpx",
    "crownquest",
    "permian",
    "akakus",
    "blackbeard",
    "cop",
    "firebird",
    "endeavor",
    "sirteoil",
    "titus",
    "mewbourne",
    "vital",
    "doubleeagle",
    "sixess",
    "rockport",
    "apache",
    "vfpetroleum",
    "fourpoint",
    "coterra",
    "ironorchard",
    "waha",
    "bluearrow",
})


def normalize_company(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def is_valid_company(name: str) -> bool:
    return normalize_company(name) in VALID_COMPANIES

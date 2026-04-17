DEFAULT_WEIGHTS = {
    "spec": 0.40,
    "compliance": 0.25,
    "price": 0.15,
    "lead_time": 0.10,
    "quality": 0.10,
}

WEIGHT_PRESETS = {
    "default": {
        "spec": 0.40, "compliance": 0.25, "price": 0.15,
        "lead_time": 0.10, "quality": 0.10,
    },
    "cost_focused": {
        "spec": 0.30, "compliance": 0.20, "price": 0.35,
        "lead_time": 0.05, "quality": 0.10,
    },
    "availability_focused": {
        "spec": 0.30, "compliance": 0.20, "price": 0.10,
        "lead_time": 0.30, "quality": 0.10,
    },
    "quality_focused": {
        "spec": 0.35, "compliance": 0.25, "price": 0.10,
        "lead_time": 0.05, "quality": 0.25,
    },
}

MAX_KNOCKOUT_CANDIDATES = 15
DEFAULT_TOP_N = 5
DEFAULT_DESTINATION_COUNTRY = "DE"
DEFAULT_MAX_PRICE_MULTIPLIER = 2.0

COUNTRY_BLACKLIST = {
    "DE": ["KP", "IR", "SY"],
    "US": ["KP", "IR", "CU", "RU"],
    "EU": ["KP", "IR", "SY"],
}

INCOTERM_ADJUSTMENTS = {
    "EXW": {"cost_adder": 0.15, "time_adder": 7,  "description": "Ex Works"},
    "FOB": {"cost_adder": 0.08, "time_adder": 3,  "description": "Free On Board"},
    "CIF": {"cost_adder": 0.05, "time_adder": 2,  "description": "Cost Insurance Freight"},
    "DDP": {"cost_adder": 0.00, "time_adder": 0,  "description": "Delivered Duty Paid"},
}

TARIFF_RATES = {
    ("CN", "DE"): 0.12,
    ("CN", "US"): 0.25,
    ("VN", "DE"): 0.05,
    ("IN", "DE"): 0.08,
    ("DE", "DE"): 0.00,
    ("EU", "DE"): 0.00,
    ("US", "DE"): 0.05,
}

PROPERTY_RANGES = {
    "zugfestigkeit":        {"min": 1,     "max": 2000,   "unit": "MPa"},
    "dichte":               {"min": 0.1,   "max": 25.0,   "unit": "g/cm³"},
    "e_modul":              {"min": 100,   "max": 500000, "unit": "MPa"},
    "schmelzpunkt":         {"min": 50,    "max": 3500,   "unit": "°C"},
    "biegefestigkeit":      {"min": 1,     "max": 1000,   "unit": "MPa"},
    "haerte":               {"min": 1,     "max": 100,    "unit": "HRC"},
    "waermeleitfaehigkeit": {"min": 0.01,  "max": 500,    "unit": "W/mK"},
    "bruchdehnung":         {"min": 0,     "max": 100,    "unit": "%"},
    # Food / sweetener scenario properties (tests/scoring/data/gesamt_materials.csv)
    "sweetness_index":      {"min": 0.1,   "max": 2.5,    "unit": "rel_sucrose"},
    "glycemic_index":       {"min": 0,     "max": 120,    "unit": "GI"},
    "moisture":             {"min": 0.0,   "max": 12.0,   "unit": "%"},
    "bulk_density":         {"min": 0.3,   "max": 1.1,    "unit": "g/mL"},
    "particle_size":        {"min": 20,    "max": 2000,   "unit": "um"},
    "purity":               {"min": 80.0,  "max": 100.0,  "unit": "%"},
}

CERTIFICATION_VERIFICATION = {
    "RoHS": {
        "verification_sources": ["rohs-db.eu", "echa.europa.eu"],
        "self_declaration": True,
        "expiry_check": False,
    },
    "FDA": {
        "verification_sources": ["fda.gov/registration"],
        "self_declaration": False,
        "expiry_check": True,
    },
    "ISO9001": {
        "verification_sources": ["iso.org/certcheck"],
        "self_declaration": False,
        "expiry_check": True,
        "max_age_months": 36,
    },
    "REACH": {
        "verification_sources": ["echa.europa.eu/reach"],
        "self_declaration": True,
        "expiry_check": False,
    },
    "CE": {
        "verification_sources": ["ec.europa.eu/growth/tools-databases/nando"],
        "self_declaration": True,
        "expiry_check": False,
    },
}

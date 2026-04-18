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

# CLAUDE.md — Crawling Modul

## Überblick

Dieses Modul ist verantwortlich für das Abrufen von Materialdaten von der Agnes API (Spherecast) und die Normalisierung in ein einheitliches Format für das Scoring-Modul.

## Input und Output

### Input

```python
original_material: MaterialQuery      # Das zu ersetzende Material (User-Input)
search_criteria: SearchCriteria       # Suchparameter (Kategorie, Anwendung, etc.)
user_preferences: UserPreferences     # Ontologie-spezifische Properties
```

### Output (für Scoring-Modul)

```python
list[CrawledMaterial]                 # Normalisierte Materialdaten
```

Das Output-Format ist in shared/schemas.py definiert und MUSS exakt eingehalten werden, damit das Scoring-Modul die Daten verarbeiten kann.

## Dateistruktur

```
src/crawling/
├── CLAUDE.md                  # Diese Datei
├── __init__.py                # Exports
├── agnes_connector.py         # Agnes API Anbindung
├── data_normalizer.py         # Response zu CrawledMaterial
├── unit_converter.py          # Einheiten-Konvertierung
├── property_mapper.py         # Property-Namen Mapping
├── enrichment.py              # Datenanreicherung (Tariffs, etc.)
└── validators.py              # Datenvalidierung
```

## Architektur

```
USER INPUT                                          
(Original-Material, Suchkriterien)                  
            │                                       
            ▼                                       
┌───────────────────────────────────────────────────────────────────┐
│ AGNES CONNECTOR (agnes_connector.py)                              │
│                                                                   │
│ • Authentifizierung                                               │
│ • API-Calls                                                       │
│ • Pagination                                                      │
│ • Rate Limiting                                                   │
│ • Error Handling                                                  │
│                                                                   │
│ Output: list[AgnesResponse]                                       │
└───────────────────────────────────────────────────────────────────┘
            │                                       
            ▼                                       
┌───────────────────────────────────────────────────────────────────┐
│ DATA NORMALIZER (data_normalizer.py)                              │
│                                                                   │
│ • Agnes-Format zu CrawledMaterial                                 │
│ • Unit Conversion (alles in SI)                                   │
│ • Property Mapping                                                │
│ • Default-Werte für fehlende Felder                               │
│ • Validierung                                                     │
│                                                                   │
│ Output: list[CrawledMaterial]                                     │
└───────────────────────────────────────────────────────────────────┘
            │                                       
            ▼                                       
┌───────────────────────────────────────────────────────────────────┐
│ ENRICHMENT (enrichment.py)                                        │
│                                                                   │
│ • Tariff-Raten hinzufügen                                         │
│ • Incoterm-Adjustments berechnen                                  │
│ • Quality-Daten anreichern                                        │
│                                                                   │
│ Output: list[CrawledMaterial] (angereichert)                      │
└───────────────────────────────────────────────────────────────────┘
            │                                       
            ▼                                       
OUTPUT: list[CrawledMaterial] für Scoring-Modul                     
```

## Agnes API Connector

Datei: agnes_connector.py

### Zweck

Kommunikation mit der Agnes/Spherecast API für Materialsuche und Datenabfrage.

### Authentifizierung

```python
class AgnesConnector:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.spherecast.com/v1",
        timeout: int = 30
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        return session
```

### Hauptfunktionen

```python
def search_materials(
    self,
    query: MaterialQuery,
    criteria: SearchCriteria,
    max_results: int = 50
) -> list[AgnesResponse]:
    """
    Sucht nach Materialien basierend auf Query und Kriterien.
    
    Args:
        query: Suchanfrage (Materialname, Kategorie, etc.)
        criteria: Filter und Einschränkungen
        max_results: Maximale Anzahl Ergebnisse
        
    Returns:
        Liste von Agnes API Responses
    """

def get_material_details(
    self,
    material_id: str
) -> AgnesResponse:
    """
    Ruft detaillierte Informationen zu einem Material ab.
    """

def get_supplier_info(
    self,
    supplier_id: str
) -> SupplierResponse:
    """
    Ruft Lieferanten-Informationen ab (für Quality Signals).
    """
```

### Pagination

```python
def _paginated_request(
    self,
    endpoint: str,
    params: dict,
    max_results: int
) -> list[dict]:
    """
    Handhabt Pagination für große Ergebnismengen.
    """
    results = []
    page = 1
    per_page = min(50, max_results)
    
    while len(results) < max_results:
        params["page"] = page
        params["per_page"] = per_page
        
        response = self._make_request(endpoint, params)
        
        if not response.get("data"):
            break
            
        results.extend(response["data"])
        
        if len(response["data"]) < per_page:
            break
            
        page += 1
    
    return results[:max_results]
```

### Rate Limiting

```python
from ratelimit import limits, sleep_and_retry

class AgnesConnector:
    
    @sleep_and_retry
    @limits(calls=100, period=60)  # 100 calls pro Minute
    def _make_request(self, endpoint: str, params: dict) -> dict:
        """
        Führt API-Request mit Rate Limiting aus.
        """
        url = f"{self.base_url}/{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
```

### Error Handling

```python
class AgnesAPIError(Exception):
    """Base exception für Agnes API Fehler."""
    pass

class AgnesAuthError(AgnesAPIError):
    """Authentifizierungsfehler."""
    pass

class AgnesRateLimitError(AgnesAPIError):
    """Rate Limit erreicht."""
    pass

class AgnesNotFoundError(AgnesAPIError):
    """Material/Resource nicht gefunden."""
    pass

def _handle_response(self, response: requests.Response) -> dict:
    """
    Verarbeitet API Response und wirft passende Exceptions.
    """
    if response.status_code == 401:
        raise AgnesAuthError("Invalid API key")
    elif response.status_code == 429:
        retry_after = response.headers.get("Retry-After", 60)
        raise AgnesRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")
    elif response.status_code == 404:
        raise AgnesNotFoundError("Resource not found")
    elif response.status_code >= 400:
        raise AgnesAPIError(f"API error: {response.status_code} - {response.text}")
    
    return response.json()
```

## Agnes Response Format

Das erwartete Format der Agnes API Response (anzupassen an tatsächliche API):

```python
@dataclass
class AgnesResponse:
    id: str
    name: str
    category: str
    manufacturer: str | None
    
    # Properties kommen als Liste von Key-Value-Pairs
    properties: list[dict]          # [{"name": "Tensile Strength", "value": 310, "unit": "MPa"}]
    
    # Compliance als Liste
    certifications: list[str]       # ["RoHS", "REACH"]
    
    # Pricing
    price: dict                     # {"value": 3.50, "currency": "EUR", "unit": "kg"}
    price_tiers: list[dict] | None  # [{"min_qty": 100, "price": 3.20}, ...]
    
    # Availability
    lead_time_days: int | None
    stock_quantity: int | None
    moq: int | None
    
    # Supplier
    supplier: dict                  # {"id": "sup_123", "name": "...", "rating": 4.5}
    
    # Origin
    country_of_origin: str | None
    incoterm: str | None
    
    # Metadata
    last_updated: str | None
    source_url: str | None
```

## Data Normalizer

Datei: data_normalizer.py

### Zweck

Konvertiert Agnes API Responses in das standardisierte CrawledMaterial Format.

### Hauptfunktion

```python
def normalize_materials(
    agnes_responses: list[AgnesResponse],
    user_preferences: UserPreferences = None
) -> list[CrawledMaterial]:
    """
    Konvertiert Agnes Responses zu CrawledMaterial Objekten.
    
    Args:
        agnes_responses: Rohe API Responses
        user_preferences: Optional, für Property-Filterung
        
    Returns:
        Liste normalisierter CrawledMaterial Objekte
    """
    normalized = []
    
    for response in agnes_responses:
        try:
            material = _normalize_single(response, user_preferences)
            if _validate_material(material):
                normalized.append(material)
        except NormalizationError as e:
            logger.warning(f"Failed to normalize {response.id}: {e}")
            continue
    
    return normalized
```

### Normalisierung einzelner Materialien

```python
def _normalize_single(
    response: AgnesResponse,
    user_preferences: UserPreferences = None
) -> CrawledMaterial:
    """
    Normalisiert eine einzelne Agnes Response.
    """
    
    return CrawledMaterial(
        id=response.id,
        name=response.name,
        properties=_normalize_properties(response.properties),
        certifications=_normalize_certifications(response.certifications),
        price=_normalize_price(response.price, response.price_tiers),
        lead_time=_normalize_lead_time(response),
        quality=_normalize_quality(response.supplier),
        moq=response.moq or 1,
        country_of_origin=_normalize_country(response.country_of_origin),
        incoterm=_normalize_incoterm(response.incoterm),
        source_url=response.source_url
    )
```

## Property Normalisierung

Datei: property_mapper.py

### Zweck

Mappt verschiedene Property-Namen auf standardisierte Namen und konvertiert Einheiten.

### Property Name Mapping

```python
PROPERTY_NAME_MAP = {
    # Zugfestigkeit
    "tensile strength": "zugfestigkeit",
    "tensile_strength": "zugfestigkeit",
    "ultimate tensile strength": "zugfestigkeit",
    "uts": "zugfestigkeit",
    "rm": "zugfestigkeit",
    
    # Dichte
    "density": "dichte",
    "specific gravity": "dichte",
    "mass density": "dichte",
    
    # E-Modul
    "elastic modulus": "e_modul",
    "young's modulus": "e_modul",
    "youngs modulus": "e_modul",
    "modulus of elasticity": "e_modul",
    "e-modulus": "e_modul",
    
    # Schmelzpunkt
    "melting point": "schmelzpunkt",
    "melting temperature": "schmelzpunkt",
    "tm": "schmelzpunkt",
    
    # Biegefestigkeit
    "flexural strength": "biegefestigkeit",
    "bending strength": "biegefestigkeit",
    
    # Härte
    "hardness": "haerte",
    "rockwell hardness": "haerte",
    "brinell hardness": "haerte",
    "vickers hardness": "haerte",
    
    # Wärmeleitfähigkeit
    "thermal conductivity": "waermeleitfaehigkeit",
    "heat conductivity": "waermeleitfaehigkeit",
    
    # Bruchdehnung
    "elongation at break": "bruchdehnung",
    "elongation": "bruchdehnung",
    "strain at break": "bruchdehnung",
    
    # Streckgrenze
    "yield strength": "streckgrenze",
    "yield stress": "streckgrenze",
    "rp02": "streckgrenze",
    
    # Schlagzähigkeit
    "impact strength": "schlagzaehigkeit",
    "charpy impact": "schlagzaehigkeit",
    "izod impact": "schlagzaehigkeit",
}

def map_property_name(raw_name: str) -> str:
    """
    Mappt einen Property-Namen auf den standardisierten Namen.
    """
    normalized = raw_name.lower().strip()
    return PROPERTY_NAME_MAP.get(normalized, normalized.replace(" ", "_"))
```

### Property-Normalisierung

```python
def _normalize_properties(
    raw_properties: list[dict]
) -> dict[str, MaterialProperty]:
    """
    Normalisiert alle Properties eines Materials.
    """
    normalized = {}
    
    for prop in raw_properties:
        name = prop.get("name")
        value = prop.get("value")
        unit = prop.get("unit")
        
        if name is None or value is None:
            continue
        
        # Name mappen
        std_name = map_property_name(name)
        
        # Einheit konvertieren
        std_value, std_unit = convert_unit(value, unit, std_name)
        
        normalized[std_name] = MaterialProperty(
            value=std_value,
            unit=std_unit
        )
    
    return normalized
```

## Unit Converter

Datei: unit_converter.py

### Zweck

Konvertiert alle Einheiten in SI-Standard für Vergleichbarkeit.

### Standard-Einheiten

```python
STANDARD_UNITS = {
    "zugfestigkeit": "MPa",
    "dichte": "g/cm³",
    "e_modul": "MPa",
    "schmelzpunkt": "°C",
    "biegefestigkeit": "MPa",
    "haerte": "HRC",
    "waermeleitfaehigkeit": "W/mK",
    "bruchdehnung": "%",
    "streckgrenze": "MPa",
    "schlagzaehigkeit": "kJ/m²",
}
```

### Konversions-Tabellen

```python
UNIT_CONVERSIONS = {
    # Druck/Festigkeit
    ("psi", "MPa"): lambda x: x * 0.00689476,
    ("ksi", "MPa"): lambda x: x * 6.89476,
    ("GPa", "MPa"): lambda x: x * 1000,
    ("N/mm²", "MPa"): lambda x: x,
    ("bar", "MPa"): lambda x: x * 0.1,
    
    # Dichte
    ("kg/m³", "g/cm³"): lambda x: x / 1000,
    ("lb/in³", "g/cm³"): lambda x: x * 27.68,
    ("g/ml", "g/cm³"): lambda x: x,
    
    # Temperatur
    ("°F", "°C"): lambda x: (x - 32) * 5/9,
    ("K", "°C"): lambda x: x - 273.15,
    
    # Länge (für andere Properties)
    ("mm", "m"): lambda x: x / 1000,
    ("in", "m"): lambda x: x * 0.0254,
    
    # Wärmeleitfähigkeit
    ("BTU/hr·ft·°F", "W/mK"): lambda x: x * 1.731,
}

def convert_unit(
    value: float,
    from_unit: str,
    property_name: str
) -> tuple[float, str]:
    """
    Konvertiert einen Wert in die Standard-Einheit.
    
    Returns:
        (konvertierter_wert, standard_einheit)
    """
    target_unit = STANDARD_UNITS.get(property_name)
    
    if target_unit is None:
        return value, from_unit
    
    if from_unit == target_unit:
        return value, target_unit
    
    conversion_key = (from_unit, target_unit)
    
    if conversion_key in UNIT_CONVERSIONS:
        converted = UNIT_CONVERSIONS[conversion_key](value)
        return converted, target_unit
    
    # Keine Konversion gefunden, Original zurückgeben mit Warning
    logger.warning(f"No conversion from {from_unit} to {target_unit} for {property_name}")
    return value, from_unit
```

## Certification Normalisierung

```python
CERTIFICATION_MAP = {
    # RoHS Varianten
    "rohs": "RoHS",
    "rohs compliant": "RoHS",
    "rohs 2": "RoHS",
    "rohs 3": "RoHS",
    "rohs ii": "RoHS",
    
    # REACH Varianten
    "reach": "REACH",
    "reach compliant": "REACH",
    "reach svhc": "REACH",
    
    # UL94 Varianten
    "ul94 v-0": "UL94-V0",
    "ul94 v0": "UL94-V0",
    "ul 94 v-0": "UL94-V0",
    "ul94 v-1": "UL94-V1",
    "ul94 v-2": "UL94-V2",
    "ul94 hb": "UL94-HB",
    
    # FDA
    "fda": "FDA",
    "fda compliant": "FDA",
    "fda approved": "FDA",
    "fda 21 cfr": "FDA",
    
    # ISO
    "iso 9001": "ISO9001",
    "iso9001": "ISO9001",
    "iso 14001": "ISO14001",
    "iso14001": "ISO14001",
    
    # Automotive
    "iatf 16949": "IATF16949",
    "iatf16949": "IATF16949",
    "ts 16949": "IATF16949",
    "ppap": "PPAP",
}

def _normalize_certifications(raw_certs: list[str]) -> list[str]:
    """
    Normalisiert Zertifikat-Namen.
    """
    normalized = set()
    
    for cert in raw_certs:
        cert_lower = cert.lower().strip()
        std_cert = CERTIFICATION_MAP.get(cert_lower, cert.upper())
        normalized.add(std_cert)
    
    return sorted(list(normalized))
```

## Price Normalisierung

```python
CURRENCY_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
    "CHF": 1.04,
    "CNY": 0.13,
    "JPY": 0.0061,
}

def _normalize_price(
    raw_price: dict,
    price_tiers: list[dict] | None
) -> PriceInfo:
    """
    Normalisiert Preisinformationen.
    """
    value = raw_price.get("value", 0)
    currency = raw_price.get("currency", "EUR")
    unit = raw_price.get("unit", "kg")
    
    # Währung konvertieren
    if currency != "EUR":
        conversion_rate = CURRENCY_TO_EUR.get(currency, 1.0)
        value = value * conversion_rate
    
    # Einheit normalisieren (alles auf €/kg)
    value = _normalize_price_unit(value, unit)
    
    # Price Tiers normalisieren
    normalized_tiers = None
    if price_tiers:
        normalized_tiers = [
            {
                "min_qty": tier.get("min_qty", 1),
                "max_qty": tier.get("max_qty"),
                "price": tier.get("price", value) * CURRENCY_TO_EUR.get(currency, 1.0)
            }
            for tier in price_tiers
        ]
    
    return PriceInfo(
        value=round(value, 4),
        unit="€/kg",
        tiers=normalized_tiers
    )

def _normalize_price_unit(value: float, unit: str) -> float:
    """
    Konvertiert Preis auf €/kg.
    """
    unit_lower = unit.lower()
    
    if unit_lower in ["kg", "kilo", "kilogram"]:
        return value
    elif unit_lower in ["g", "gram"]:
        return value * 1000
    elif unit_lower in ["t", "ton", "tonne"]:
        return value / 1000
    elif unit_lower in ["lb", "pound"]:
        return value * 2.20462
    else:
        return value  # Assume kg
```

## Lead Time Normalisierung

```python
def _normalize_lead_time(response: AgnesResponse) -> LeadTimeInfo:
    """
    Normalisiert Lead Time Informationen.
    """
    days = response.lead_time_days
    stock = response.stock_quantity or 0
    
    # Wenn Stock verfügbar, Lead Time reduzieren
    if stock > 0:
        lead_time_type = "stock"
        days = min(days or 3, 3)  # Max 3 Tage bei Stock
    elif days is None:
        lead_time_type = "unknown"
        days = 14  # Default: 2 Wochen
    elif days <= 7:
        lead_time_type = "express"
    else:
        lead_time_type = "standard"
    
    # Reliability aus Supplier-Daten wenn verfügbar
    reliability = 1.0
    if response.supplier:
        supplier_rating = response.supplier.get("rating")
        if supplier_rating:
            # Rating 1-5 zu Reliability 0.6-1.0 mappen
            reliability = 0.6 + (supplier_rating / 5) * 0.4
    
    return LeadTimeInfo(
        days=days,
        reliability=round(reliability, 2),
        type=lead_time_type
    )
```

## Quality Normalisierung

```python
def _normalize_quality(supplier: dict | None) -> QualityInfo:
    """
    Normalisiert Quality-Informationen aus Supplier-Daten.
    """
    if not supplier:
        return QualityInfo()
    
    quality = QualityInfo()
    
    # Supplier Rating
    if "rating" in supplier:
        quality.supplier_rating = {
            "value": supplier["rating"],
            "review_count": supplier.get("review_count", 0),
            "source": supplier.get("platform", "unknown")
        }
    
    # Defect Rate (wenn verfügbar)
    if "defect_rate" in supplier:
        quality.defect_rate = {
            "value": supplier["defect_rate"],
            "sample_size": supplier.get("sample_size", 0),
            "period": supplier.get("period", "unknown")
        }
    
    # On-Time Delivery
    if "on_time_delivery" in supplier:
        quality.on_time_delivery = {
            "value": supplier["on_time_delivery"],
            "sample_size": supplier.get("delivery_sample_size", 0)
        }
    
    # Years in Business
    if "established_year" in supplier:
        from datetime import datetime
        current_year = datetime.now().year
        quality.years_in_business = current_year - supplier["established_year"]
    elif "years_in_business" in supplier:
        quality.years_in_business = supplier["years_in_business"]
    
    # Audit Score
    if "audit_score" in supplier:
        quality.audit_score = {
            "value": supplier["audit_score"],
            "auditor": supplier.get("auditor", "unknown"),
            "date": supplier.get("audit_date")
        }
    
    return quality
```

## Country Code Normalisierung

```python
COUNTRY_CODE_MAP = {
    # Volle Namen zu ISO Codes
    "germany": "DE",
    "deutschland": "DE",
    "china": "CN",
    "people's republic of china": "CN",
    "prc": "CN",
    "united states": "US",
    "usa": "US",
    "united states of america": "US",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "taiwan": "TW",
    "vietnam": "VN",
    "india": "IN",
    "italy": "IT",
    "france": "FR",
    "united kingdom": "GB",
    "uk": "GB",
    "spain": "ES",
    "netherlands": "NL",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "austria": "AT",
    "switzerland": "CH",
    "sweden": "SE",
    "mexico": "MX",
    "canada": "CA",
    "brazil": "BR",
    "turkey": "TR",
    "thailand": "TH",
    "malaysia": "MY",
    "indonesia": "ID",
    "philippines": "PH",
}

def _normalize_country(raw_country: str | None) -> str:
    """
    Normalisiert Country of Origin zu ISO 3166-1 alpha-2 Code.
    """
    if not raw_country:
        return "XX"  # Unknown
    
    country_lower = raw_country.lower().strip()
    
    # Bereits ein ISO Code?
    if len(raw_country) == 2 and raw_country.isupper():
        return raw_country
    
    # Mapping verwenden
    return COUNTRY_CODE_MAP.get(country_lower, "XX")
```

## Incoterm Normalisierung

```python
VALID_INCOTERMS = ["EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]

INCOTERM_MAP = {
    "ex works": "EXW",
    "exw": "EXW",
    "free carrier": "FCA",
    "fca": "FCA",
    "free on board": "FOB",
    "fob": "FOB",
    "cost and freight": "CFR",
    "cfr": "CFR",
    "c&f": "CFR",
    "cost insurance freight": "CIF",
    "cif": "CIF",
    "delivered duty paid": "DDP",
    "ddp": "DDP",
    "delivered at place": "DAP",
    "dap": "DAP",
}

def _normalize_incoterm(raw_incoterm: str | None) -> str:
    """
    Normalisiert Incoterm.
    """
    if not raw_incoterm:
        return "EXW"  # Default: Ex Works (konservativste Annahme)
    
    incoterm_lower = raw_incoterm.lower().strip()
    
    # Bereits gültiger Code?
    if raw_incoterm.upper() in VALID_INCOTERMS:
        return raw_incoterm.upper()
    
    # Mapping verwenden
    return INCOTERM_MAP.get(incoterm_lower, "EXW")
```

## Enrichment

Datei: enrichment.py

### Zweck

Reichert normalisierte Daten mit zusätzlichen Informationen an (Tariffs, berechnete Felder).

### Tariff-Anreicherung

```python
TARIFF_RATES = {
    ("CN", "DE"): 0.12,
    ("CN", "US"): 0.25,
    ("VN", "DE"): 0.05,
    ("VN", "US"): 0.10,
    ("IN", "DE"): 0.08,
    ("IN", "US"): 0.06,
    ("TW", "DE"): 0.04,
    ("TW", "US"): 0.03,
    ("JP", "DE"): 0.00,
    ("JP", "US"): 0.02,
    ("KR", "DE"): 0.00,
    ("KR", "US"): 0.02,
    ("MX", "US"): 0.00,
    ("CA", "US"): 0.00,
    # EU-intern
    ("DE", "DE"): 0.00,
    ("IT", "DE"): 0.00,
    ("FR", "DE"): 0.00,
    ("PL", "DE"): 0.00,
    ("CZ", "DE"): 0.00,
    ("AT", "DE"): 0.00,
    ("NL", "DE"): 0.00,
}

def enrich_with_tariffs(
    materials: list[CrawledMaterial],
    destination_country: str = "DE"
) -> list[CrawledMaterial]:
    """
    Reichert Materialien mit Tariff-Informationen an.
    """
    for material in materials:
        origin = material.country_of_origin
        tariff_key = (origin, destination_country)
        
        tariff_rate = TARIFF_RATES.get(tariff_key, 0.05)  # Default 5%
        
        # Tariff in Metadata speichern
        if not hasattr(material, 'metadata'):
            material.metadata = {}
        
        material.metadata['tariff_rate'] = tariff_rate
        material.metadata['tariff_adjusted_price'] = material.price.value * (1 + tariff_rate)
    
    return materials
```

## Validators

Datei: validators.py

### Zweck

Validiert normalisierte Daten auf Vollständigkeit und Konsistenz.

```python
def _validate_material(material: CrawledMaterial) -> bool:
    """
    Validiert ein CrawledMaterial auf Mindestanforderungen.
    
    Returns:
        True wenn Material gültig, False wenn es verworfen werden soll
    """
    
    # Pflichtfelder
    if not material.id:
        logger.warning("Material without ID")
        return False
    
    if not material.name:
        logger.warning(f"Material {material.id} without name")
        return False
    
    # Mindestens eine Property
    if not material.properties or len(material.properties) == 0:
        logger.warning(f"Material {material.id} has no properties")
        return False
    
    # Preis muss positiv sein
    if material.price.value <= 0:
        logger.warning(f"Material {material.id} has invalid price: {material.price.value}")
        return False
    
    # Lead Time muss nicht-negativ sein
    if material.lead_time.days < 0:
        logger.warning(f"Material {material.id} has negative lead time")
        return False
    
    # MOQ muss positiv sein
    if material.moq <= 0:
        material.moq = 1  # Auto-korrigieren
    
    return True

def validate_batch(materials: list[CrawledMaterial]) -> ValidationResult:
    """
    Validiert eine Liste von Materialien.
    
    Returns:
        ValidationResult mit valid, invalid, und Statistiken
    """
    valid = []
    invalid = []
    
    for material in materials:
        if _validate_material(material):
            valid.append(material)
        else:
            invalid.append(material)
    
    return ValidationResult(
        valid=valid,
        invalid=invalid,
        total=len(materials),
        valid_count=len(valid),
        invalid_count=len(invalid)
    )
```

## Haupt-Pipeline

```python
def crawl_materials(
    original: MaterialQuery,
    search_criteria: SearchCriteria,
    user_preferences: UserPreferences = None,
    destination_country: str = "DE",
    max_results: int = 50
) -> list[CrawledMaterial]:
    """
    Vollständige Crawling-Pipeline.
    
    Args:
        original: Das zu ersetzende Material
        search_criteria: Suchparameter
        user_preferences: Ontologie-spezifische Präferenzen
        destination_country: Zielland für Tariff-Berechnung
        max_results: Maximale Ergebnisse
        
    Returns:
        Liste normalisierter und angereicherter CrawledMaterial Objekte
    """
    
    # 1. Agnes API aufrufen
    connector = AgnesConnector(api_key=get_api_key())
    agnes_responses = connector.search_materials(
        query=original,
        criteria=search_criteria,
        max_results=max_results
    )
    
    # 2. Normalisieren
    normalized = normalize_materials(agnes_responses, user_preferences)
    
    # 3. Validieren
    validation = validate_batch(normalized)
    logger.info(f"Validated {validation.valid_count}/{validation.total} materials")
    
    # 4. Anreichern
    enriched = enrich_with_tariffs(validation.valid, destination_country)
    
    return enriched
```

## Output Format (Schnittstelle zu Scoring)

Das Scoring-Modul erwartet exakt dieses Format:

```python
CrawledMaterial(
    id="mat_12345",
    name="Aluminium 6061-T6",
    properties={
        "zugfestigkeit": MaterialProperty(value=310.0, unit="MPa"),
        "dichte": MaterialProperty(value=2.7, unit="g/cm³"),
        "e_modul": MaterialProperty(value=68900.0, unit="MPa"),
        "bruchdehnung": MaterialProperty(value=12.0, unit="%"),
    },
    certifications=["RoHS", "REACH", "ISO9001"],
    price=PriceInfo(
        value=3.50,
        unit="€/kg",
        tiers=[
            {"min_qty": 1, "max_qty": 99, "price": 3.50},
            {"min_qty": 100, "max_qty": 499, "price": 3.20},
            {"min_qty": 500, "max_qty": None, "price": 2.90},
        ]
    ),
    lead_time=LeadTimeInfo(
        days=14,
        reliability=0.92,
        type="standard"
    ),
    quality=QualityInfo(
        supplier_rating={"value": 4.5, "review_count": 234, "source": "alibaba"},
        defect_rate={"value": 0.3, "sample_size": 10000, "period": "12_months"},
        on_time_delivery={"value": 96, "sample_size": 150},
        years_in_business=15,
        audit_score={"value": 88, "auditor": "TÜV", "date": "2024-06"}
    ),
    moq=100,
    country_of_origin="DE",
    incoterm="DDP",
    source_url="https://spherecast.com/materials/mat_12345"
)
```

## Testing

### Teststruktur

```
tests/crawling/
├── conftest.py                 # Fixtures, Mock Agnes Responses
├── test_agnes_connector.py     # API-Calls (mit Mocks)
├── test_data_normalizer.py     # Normalisierung
├── test_unit_converter.py      # Einheiten-Konvertierung
├── test_property_mapper.py     # Property-Mapping
├── test_enrichment.py          # Tariff-Anreicherung
├── test_validators.py          # Validierung
└── test_pipeline.py            # Integration
```

### Wichtige Test-Szenarien

Agnes Connector:
- Erfolgreiche Suche
- Authentifizierungsfehler
- Rate Limiting
- Timeout
- Leere Ergebnisse
- Pagination

Normalizer:
- Vollständige Response
- Fehlende Felder (Defaults testen)
- Verschiedene Property-Namen
- Verschiedene Einheiten
- Ungültige Daten

Unit Converter:
- Alle bekannten Konversionen
- Unbekannte Einheiten
- Edge Cases (0, negative Werte)

Validators:
- Gültige Materialien
- Fehlende Pflichtfelder
- Ungültige Werte

## Error Handling

```python
class CrawlingError(Exception):
    """Base exception für Crawling-Fehler."""
    pass

class NormalizationError(CrawlingError):
    """Fehler bei der Daten-Normalisierung."""
    pass

class ValidationError(CrawlingError):
    """Fehler bei der Validierung."""
    pass
```

## Dependencies

```
requests        # HTTP Client
ratelimit       # Rate Limiting
pydantic        # Datenvalidierung (optional)
```

## Konfiguration

```python
# config.py oder .env

AGNES_API_KEY = "..."
AGNES_BASE_URL = "https://api.spherecast.com/v1"
AGNES_TIMEOUT = 30
AGNES_MAX_RETRIES = 3
AGNES_RATE_LIMIT_CALLS = 100
AGNES_RATE_LIMIT_PERIOD = 60
```
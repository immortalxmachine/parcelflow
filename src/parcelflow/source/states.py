"""Reference data: the 27 Brazilian federative units (the "hubs").

In ParcelFlow a **hub = a Brazilian customer state** (the ``customer_state``
field of the Olist dataset). Every order is grouped to the state it was shipped
to, so the warehouse's ``dim_hub`` is really a dimension of Brazilian states.

All attributes here are **real**: the official two-letter state code, the state
name, its capital city, its macro-region (one of Brazil's five official
regions), and the capital's latitude/longitude. Nothing is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    code: str      # official UF code, e.g. "SP" (this is the hub_code)
    name: str      # state name, e.g. "São Paulo"
    capital: str   # capital city
    region: str    # Brazilian macro-region
    lat: float     # capital latitude
    lng: float     # capital longitude


# The 27 federative units (26 states + the Federal District), with their
# capitals and official macro-regions. Coordinates are the capital cities'.
STATES: list[State] = [
    # North
    State("AC", "Acre", "Rio Branco", "North", -9.9754, -67.8249),
    State("AP", "Amapá", "Macapá", "North", 0.0349, -51.0694),
    State("AM", "Amazonas", "Manaus", "North", -3.1190, -60.0217),
    State("PA", "Pará", "Belém", "North", -1.4558, -48.5039),
    State("RO", "Rondônia", "Porto Velho", "North", -8.7619, -63.9039),
    State("RR", "Roraima", "Boa Vista", "North", 2.8238, -60.6753),
    State("TO", "Tocantins", "Palmas", "North", -10.1844, -48.3336),
    # Northeast
    State("AL", "Alagoas", "Maceió", "Northeast", -9.6498, -35.7089),
    State("BA", "Bahia", "Salvador", "Northeast", -12.9777, -38.5016),
    State("CE", "Ceará", "Fortaleza", "Northeast", -3.7319, -38.5267),
    State("MA", "Maranhão", "São Luís", "Northeast", -2.5307, -44.3068),
    State("PB", "Paraíba", "João Pessoa", "Northeast", -7.1195, -34.8450),
    State("PE", "Pernambuco", "Recife", "Northeast", -8.0476, -34.8770),
    State("PI", "Piauí", "Teresina", "Northeast", -5.0892, -42.8019),
    State("RN", "Rio Grande do Norte", "Natal", "Northeast", -5.7945, -35.2110),
    State("SE", "Sergipe", "Aracaju", "Northeast", -10.9472, -37.0731),
    # Central-West
    State("DF", "Distrito Federal", "Brasília", "Central-West", -15.7939, -47.8828),
    State("GO", "Goiás", "Goiânia", "Central-West", -16.6869, -49.2648),
    State("MT", "Mato Grosso", "Cuiabá", "Central-West", -15.6014, -56.0979),
    State("MS", "Mato Grosso do Sul", "Campo Grande", "Central-West", -20.4697, -54.6201),
    # Southeast
    State("ES", "Espírito Santo", "Vitória", "Southeast", -20.3155, -40.3128),
    State("MG", "Minas Gerais", "Belo Horizonte", "Southeast", -19.9167, -43.9345),
    State("RJ", "Rio de Janeiro", "Rio de Janeiro", "Southeast", -22.9068, -43.1729),
    State("SP", "São Paulo", "São Paulo", "Southeast", -23.5505, -46.6333),
    # South
    State("PR", "Paraná", "Curitiba", "South", -25.4284, -49.2733),
    State("RS", "Rio Grande do Sul", "Porto Alegre", "South", -30.0346, -51.2177),
    State("SC", "Santa Catarina", "Florianópolis", "South", -27.5954, -48.5480),
]

STATES_BY_CODE = {s.code: s for s in STATES}
STATE_CODES = set(STATES_BY_CODE)

# Brazil's five official macro-regions (used for colouring / grouping).
REGIONS = ["North", "Northeast", "Central-West", "Southeast", "South"]

# The order lifecycle statuses present in the Olist orders table. Each order
# has exactly one status, so this is a clean conformed dimension.
ORDER_STATUSES = [
    "delivered",
    "shipped",
    "canceled",
    "unavailable",
    "invoiced",
    "processing",
    "created",
    "approved",
]

"""Reference data: 15 Indian logistics hubs.

Kept in one place so the generator, the warehouse dimension and the dashboard
all agree on the same hub universe. Coordinates are approximate real city
locations; everything else about the data is synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hub:
    code: str          # short stable key, e.g. "CHN"
    name: str          # human-readable hub name
    city: str
    region: str        # coarse zone, handy for grouping in analytics
    lat: float
    lng: float
    base_volume: int   # typical parcels/day before seasonal effects


# 15 hubs across India. ``base_volume`` gives each hub a distinct scale so the
# dashboard's hub comparison is interesting.
HUBS: list[Hub] = [
    Hub("CHN", "Chennai Hub", "Chennai", "South", 13.0827, 80.2707, 4200),
    Hub("BLR", "Bengaluru Hub", "Bengaluru", "South", 12.9716, 77.5946, 5200),
    Hub("HYD", "Hyderabad Hub", "Hyderabad", "South", 17.3850, 78.4867, 3800),
    Hub("COK", "Kochi Hub", "Kochi", "South", 9.9312, 76.2673, 1600),
    Hub("MUM", "Mumbai Hub", "Mumbai", "West", 19.0760, 72.8777, 6100),
    Hub("PUN", "Pune Hub", "Pune", "West", 18.5204, 73.8567, 3100),
    Hub("AMD", "Ahmedabad Hub", "Ahmedabad", "West", 23.0225, 72.5714, 2600),
    Hub("DEL", "Delhi Hub", "Delhi", "North", 28.7041, 77.1025, 6400),
    Hub("JAI", "Jaipur Hub", "Jaipur", "North", 26.9124, 75.7873, 1900),
    Hub("LKO", "Lucknow Hub", "Lucknow", "North", 26.8467, 80.9462, 1700),
    Hub("CHD", "Chandigarh Hub", "Chandigarh", "North", 30.7333, 76.7794, 1400),
    Hub("KOL", "Kolkata Hub", "Kolkata", "East", 22.5726, 88.3639, 4300),
    Hub("PAT", "Patna Hub", "Patna", "East", 25.5941, 85.1376, 1500),
    Hub("GUW", "Guwahati Hub", "Guwahati", "East", 26.1445, 91.7362, 1200),
    Hub("NAG", "Nagpur Hub", "Nagpur", "Central", 21.1458, 79.0882, 2200),
]

HUBS_BY_CODE = {h.code: h for h in HUBS}

# Service types and their relative share of volume.
SERVICE_TYPES = ["EXPRESS", "STANDARD", "ECONOMY"]
SERVICE_MIX = [0.30, 0.50, 0.20]

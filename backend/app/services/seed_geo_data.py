"""Idempotent seed data: real APMC mandis + agri-input vendors with coordinates.

Runs at startup (local SQLite) or via `python -m app.services.seed_geo_data`.
Coordinates are real APMC/industrial locations so distance math and maps work.
"""
import logging

from sqlalchemy.orm import Session

from app.models.mandi import Mandi, Vendor

logger = logging.getLogger("app.seed")

# ---- Real APMC markets (name, city, district, state, lat, lon, major crops) ----
MANDIS = [
    ("Lasalgaon APMC", "Lasalgaon", "Nashik", "Maharashtra", 20.1505, 74.2270, ["onion"]),
    ("Pimpalgaon APMC", "Pimpalgaon", "Nashik", "Maharashtra", 20.2300, 73.9930, ["onion", "tomato", "grapes"]),
    ("Chandwad APMC", "Chandwad", "Nashik", "Maharashtra", 20.3300, 74.2430, ["onion", "bajra"]),
    ("Yeola APMC", "Yeola", "Nashik", "Maharashtra", 20.0430, 74.4860, ["onion", "cotton"]),
    ("Nashik APMC", "Nashik", "Nashik", "Maharashtra", 19.9830, 73.8140, ["grapes", "onion", "tomato"]),
    ("Malegaon APMC", "Malegaon", "Nashik", "Maharashtra", 20.5530, 74.5280, ["onion", "bajra", "cotton"]),
    ("Indore APMC", "Indore", "Indore", "Madhya Pradesh", 22.7196, 75.8577, ["soybean", "wheat", "gram"]),
    ("Khargone APMC", "Khargone", "Khargone", "Madhya Pradesh", 21.8243, 75.6107, ["cotton", "chilli"]),
    ("Kota APMC", "Kota", "Kota", "Rajasthan", 25.2138, 75.8648, ["soybean", "mustard", "coriander"]),
    ("Hanamkonda APMC", "Hanamkonda", "Warangal", "Telangana", 17.9689, 79.4900, ["cotton", "chilli", "rice"]),
    ("Warangal APMC", "Warangal", "Warangal", "Telangana", 17.9689, 79.5941, ["cotton", "rice"]),
    ("Khammam APMC", "Khammam", "Khammam", "Telangana", 17.2473, 80.1514, ["chilli", "cotton", "maize"]),
    ("Guntur APMC", "Guntur", "Guntur", "Andhra Pradesh", 16.3067, 80.4365, ["chilli", "cotton", "tobacco"]),
    ("Kurnool APMC", "Kurnool", "Kurnool", "Andhra Pradesh", 15.8281, 78.0373, ["groundnut", "cotton", "sunflower"]),
    ("Tiptur APMC", "Tiptur", "Tumkur", "Karnataka", 13.2560, 76.4770, ["coconut", "areca"]),
    ("Hubli APMC", "Hubli", "Dharwad", "Karnataka", 15.3647, 75.1240, ["chilli", "onion", "cotton"]),
    ("Raichur APMC", "Raichur", "Raichur", "Karnataka", 15.9129, 77.0290, ["rice", "groundnut", "cotton"]),
    ("Hosur APMC", "Hosur", "Krishnagiri", "Tamil Nadu", 12.7400, 77.8260, ["tomato", "mango", "flowers"]),
    ("Ahmedabad APMC", "Ahmedabad", "Ahmedabad", "Gujarat", 22.9960, 72.6020, ["cotton", "groundnut", "bajra"]),
    ("Rajkot APMC", "Rajkot", "Rajkot", "Gujarat", 22.3039, 70.8022, ["groundnut", "cotton", "wheat"]),
    ("Ludhiana APMC", "Ludhiana", "Ludhiana", "Punjab", 30.9010, 75.8573, ["wheat", "rice", "maize"]),
    ("Indi APMC", "Indi", "Sangli", "Maharashtra", 17.3260, 75.5560, ["sugarcane", "turmeric", "grapes"]),
    ("Sangli APMC", "Sangli", "Sangli", "Maharashtra", 16.8524, 74.5815, ["turmeric", "grapes", "sugarcane"]),
    ("Shrirampur APMC", "Shrirampur", "Ahmednagar", "Maharashtra", 19.6160, 74.6630, ["onion", "sugarcane", "banana"]),
    ("Kopargaon APMC", "Kopargaon", "Ahmednagar", "Maharashtra", 19.8850, 74.4780, ["onion", "sugarcane"]),
    ("Pandharpur APMC", "Pandharpur", "Solapur", "Maharashtra", 17.6790, 75.3290, ["sugarcane", "jowar", "tur"]),
    ("Solapur APMC", "Solapur", "Solapur", "Maharashtra", 17.6599, 75.9064, ["jowar", "tur", "cotton"]),
    ("Pune (Hadapsar) APMC", "Pune", "Pune", "Maharashtra", 18.5010, 73.9280, ["onion", "tomato", "potato"]),
    ("Baramati APMC", "Baramati", "Pune", "Maharashtra", 18.1510, 74.5780, ["sugarcane", "grapes", "jowar"]),
    ("Jalgaon APMC", "Jalgaon", "Jalgaon", "Maharashtra", 21.0070, 75.5630, ["banana", "cotton", "gram"]),
    ("Amravati APMC", "Amravati", "Amravati", "Maharashtra", 20.9370, 77.7870, ["cotton", "soybean", "gram"]),
    ("Yavatmal APMC", "Yavatmal", "Yavatmal", "Maharashtra", 20.3930, 78.1330, ["cotton", "soybean"]),
    ("Akola APMC", "Akola", "Akola", "Maharashtra", 20.7000, 77.0080, ["cotton", "gram", "soybean"]),
    ("Parbhani APMC", "Parbhani", "Parbhani", "Maharashtra", 19.2680, 76.7750, ["cotton", "soybean", "tur"]),
    ("Latur APMC", "Latur", "Latur", "Maharashtra", 18.4040, 76.5800, ["tur", "soybean", "grapes"]),
    ("Gondia APMC", "Gondia", "Gondia", "Maharashtra", 21.4600, 80.1920, ["rice", "pigeon pea"]),
    ("Bhandara APMC", "Bhandara", "Bhandara", "Maharashtra", 21.1660, 79.6500, ["rice", "wheat"]),
    ("Nagpur APMC", "Nagpur", "Nagpur", "Maharashtra", 21.1458, 79.0882, ["oranges", "cotton", "soybean"]),
    ("Katol APMC", "Katol", "Nagpur", "Maharashtra", 21.2670, 78.5870, ["oranges", "cotton"]),
    ("Bijnor APMC", "Bijnor", "Bijnor", "Uttar Pradesh", 29.3720, 78.1290, ["sugarcane", "wheat", "rice"]),
    ("Meerut APMC", "Meerut", "Meerut", "Uttar Pradesh", 28.9850, 77.7060, ["sugarcane", "wheat", "potato"]),
    ("Kanpur APMC", "Kanpur", "Kanpur", "Uttar Pradesh", 26.4499, 80.3319, ["wheat", "rice", "potato"]),
    ("Varanasi APMC", "Varanasi", "Varanasi", "Uttar Pradesh", 25.3176, 82.9739, ["rice", "wheat", "vegetables"]),
    ("Bhopal APMC", "Bhopal", "Bhopal", "Madhya Pradesh", 23.2599, 77.4126, ["wheat", "soybean", "gram"]),
    ("Hoshangabad APMC", "Hoshangabad", "Narmadapuram", "Madhya Pradesh", 22.7490, 77.7200, ["wheat", "soybean", "gram"]),
    ("Jaipur APMC", "Jaipur", "Jaipur", "Rajasthan", 26.9124, 75.7873, ["bajra", "mustard", "gram"]),
    ("Ganganagar APMC", "Sri Ganganagar", "Ganganagar", "Rajasthan", 29.9030, 73.8770, ["wheat", "mustard", "cotton"]),
    ("Patna APMC", "Patna", "Patna", "Bihar", 25.5941, 85.1376, ["rice", "wheat", "maize"]),
    ("Begusarai APMC", "Begusarai", "Begusarai", "Bihar", 25.4180, 86.1290, ["rice", "maize", "mustard"]),
    ("Jalpaiguri APMC", "Jalpaiguri", "Jalpaiguri", "West Bengal", 26.5210, 88.7270, ["rice", "jute", "tea"]),
]

# ---- Agri-input vendors / produce buyers (name, category, description, phone,
#      address, city, district, state, lat, lon, crops) ----
VENDORS = [
    ("Nashik Seed Center", "seeds", "Bt cotton, soybean, onion and vegetable seeds; major brand dealer", "+91 98220 11223", "Dwarka, Nashik", "Nashik", "Nashik", "Maharashtra", 19.9970, 73.7890, ["cotton", "soybean", "onion"]),
    ("Kisan Agro Fertilizers", "fertilizer", "Urea, DAP, potash, micronutrients; soil-test based recommendations", "+91 98220 33445", "Trimbak Road, Nashik", "Nashik", "Nashik", "Maharashtra", 19.9900, 73.7800, []),
    ("Sharayu Farm Equipment", "equipment", "Tractors, rotavators, seed drills; new and rental", "+91 98220 55667", "Gangapur Road, Nashik", "Nashik", "Nashik", "Maharashtra", 20.0130, 73.7310, []),
    ("Warangal Chilli Supplies", "pesticide", "Chilli and cotton plant protection; bollworm specialist advice", "+91 98480 22110", "Kakatiya Colony, Hanamkonda", "Hanamkonda", "Warangal", "Telangana", 17.9700, 79.4930, ["chilli", "cotton"]),
    ("Telangana Seed House", "seeds", "Cotton, maize, paddy seeds; dealer day-limited offers", "+91 98480 33221", "Market Road, Warangal", "Warangal", "Warangal", "Telangana", 17.9690, 79.5950, ["cotton", "maize", "rice"]),
    ("Guntur Spices Buying Co.", "produce_buyer", "Direct chilli procurement at farm-gate; graded lots", "+91 98480 44332", "Guntur APMC Road", "Guntur", "Guntur", "Andhra Pradesh", 16.3070, 80.4370, ["chilli"]),
    ("Malwa Soybean Traders", "produce_buyer", "Soybean and gram procurement; mandi-linked rates", "+91 98260 55443", "Scheme 78, Indore", "Indore", "Indore", "Madhya Pradesh", 22.7200, 75.8600, ["soybean", "gram"]),
    ("Deccan Drip Systems", "equipment", "Drip and sprinkler irrigation; subsidy paperwork assistance", "+91 98220 66554", "MIDC, Nashik", "Nashik", "Nashik", "Maharashtra", 19.9500, 73.8390, []),
    ("Marathwada Cotton Ginning Co.", "produce_buyer", "Kapas procurement, ginning; seasonal contracts", "+91 98220 77665", "Bidkin Industrial Area", "Paithan", "Chhatrapati Sambhajinagar", "Maharashtra", 19.6800, 75.3800, ["cotton"]),
    ("Konkan Grape Buyers", "produce_buyer", "Table grape export procurement; cold-chain pickup", "+91 98220 88776", "Pimpalgaon, Nashik", "Pimpalgaon", "Nashik", "Maharashtra", 20.2310, 73.9940, ["grapes"]),
    ("Punjab Mechanization Works", "equipment", "Laser levelers, straw balers; custom-hiring center", "+91 98760 11224", "Focal Point, Ludhiana", "Ludhiana", "Ludhiana", "Punjab", 30.8300, 75.8700, []),
    ("Karnataka Vegetable Aggregators", "produce_buyer", "Tomato/onion collection centers; daily farm-gate price", "+91 98800 22331", "Hosur Road, Bengaluru", "Bengaluru", "Bengaluru Urban", "Karnataka", 12.8400, 77.6600, ["tomato", "onion"]),
    ("Saurashtra Groundnut Oil Mills", "produce_buyer", "Groundnut procurement for oil crushing; quality premium", "+91 98250 33442", "Kuvadva Road, Rajkot", "Rajkot", "Rajkot", "Gujarat", 22.2700, 70.8300, ["groundnut"]),
    ("Kaveri Delta Paddy Buyers", "produce_buyer", "Paddy procurement linked to MSP; moisture-tested lots", "+91 98400 44553", "Thanjavur", "Thanjavur", "Thanjavur", "Tamil Nadu", 10.7900, 79.1300, ["rice"]),
    ("Vidarbha Beekeeping Supplies", "equipment", "Bee boxes, colonies, honey extraction for orchard pollination", "+91 98220 99887", "Katol Road, Nagpur", "Nagpur", "Nagpur", "Maharashtra", 21.2000, 79.0600, ["oranges"]),
    ("Bio Pest Solutions", "pesticide", "Neem, Trichoderma, pheromone traps; organic-certified inputs", "+91 98220 11990", "Satara MIDC", "Satara", "Satara", "Maharashtra", 17.6800, 74.0100, []),
    ("Adilabad Tractor Spares", "equipment", "Genuine spares, tyres, batteries; field service van", "+91 98480 55662", "NH-44, Adilabad", "Adilabad", "Adilabad", "Telangana", 19.6700, 78.5300, []),
    ("Ganga Greenhouse Supplies", "equipment", "Polyhouse structures, shade nets, mulch film", "+91 98730 22119", "Meerut Road, Ghaziabad", "Ghaziabad", "Ghaziabad", "Uttar Pradesh", 28.6800, 77.4500, ["tomato", "flowers"]),
    ("Bihar Mango Orchard Buyers", "produce_buyer", "Mango procurement at orchard; carton-grade sorting", "+91 98350 33228", "Bhagalpur", "Bhagalpur", "Bhagalpur", "Bihar", 25.2400, 86.9800, ["mango"]),
    ("Coastal Coconut Traders", "produce_buyer", "Coconut and arecanut procurement; tender-coconut supply chain", "+91 94480 44337", "Tiptur", "Tumkur", "Tumkur", "Karnataka", 13.2570, 76.4780, ["coconut", "areca"]),
]


def seed_geo_data(db: Session) -> dict[str, int]:
    """Insert missing mandis/vendors by name. Safe to run on every startup."""
    existing_m = {m.name for m in db.query(Mandi).all()}
    added_m = 0
    for row in MANDIS:
        name, city, district, state, lat, lon, crops = row
        if name in existing_m:
            continue
        db.add(
            Mandi(
                name=name, city=city, district=district, state=state,
                latitude=lat, longitude=lon, major_crops=crops,
            )
        )
        added_m += 1

    existing_v = {v.name for v in db.query(Vendor).all()}
    added_v = 0
    for row in VENDORS:
        name, category, desc, phone, addr, city, district, state, lat, lon, crops = row
        if name in existing_v:
            continue
        db.add(
            Vendor(
                name=name, category=category, description=desc, phone=phone, address=addr,
                city=city, district=district, state=state, latitude=lat, longitude=lon,
                crops=crops,
            )
        )
        added_v += 1

    return {"mandis_added": added_m, "vendors_added": added_v}


if __name__ == "__main__":
    from app.core.database import init_local_db, get_session_factory
    from app.models import Mandi as _M, Vendor as _V  # noqa: F401

    init_local_db()
    db = get_session_factory()()
    try:
        print(seed_geo_data(db))
        db.commit()
    finally:
        db.close()

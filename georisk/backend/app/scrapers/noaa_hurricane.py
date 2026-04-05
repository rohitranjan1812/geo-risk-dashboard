import json
import logging
import math
from pathlib import Path

from app.config import settings
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class NOAAHurricaneScraper(BaseScraper):
    SOURCE_NAME = "noaa_hurricane"
    TIMEOUT = 120.0

    async def scrape(self) -> dict:
        response = await self.fetch_with_retry(settings.NHC_BESTTRACK_URL)
        text = response.text
        storms = self._parse_hurdat2(text)

        features = []
        for storm in storms:
            if storm["year"] < 2004:
                continue
            coords = [[p["lon"], p["lat"]] for p in storm["track_points"]]
            if len(coords) < 2:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "storm_id": storm["storm_id"],
                    "name": storm["name"],
                    "year": storm["year"],
                    "max_wind": storm["max_wind"],
                    "min_pressure": storm["min_pressure"],
                    "category": storm["category"],
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            })

        geojson = {"type": "FeatureCollection", "features": features}
        filepath = self.save_geojson(geojson, "hurricane_tracks_scraped.geojson")

        return {
            "status": "success",
            "source": self.SOURCE_NAME,
            "records": len(features),
            "file_path": str(filepath),
        }

    def _parse_hurdat2(self, text: str) -> list[dict]:
        storms = []
        current_storm = None
        lines_remaining = 0

        for line in text.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]

            if len(parts) >= 4 and parts[0].startswith(("AL", "EP", "CP")):
                storm_id = parts[0]
                name = parts[1]
                num_entries = int(parts[2])
                current_storm = {
                    "storm_id": storm_id,
                    "name": name if name != "UNNAMED" else storm_id,
                    "year": int(storm_id[4:8]) if len(storm_id) >= 8 else 0,
                    "track_points": [],
                    "max_wind": 0,
                    "min_pressure": 9999,
                    "category": 0,
                }
                lines_remaining = num_entries
                continue

            if current_storm and lines_remaining > 0:
                lines_remaining -= 1
                try:
                    lat_str = parts[4].strip()
                    lon_str = parts[5].strip()
                    lat = float(lat_str.replace("N", "").replace("S", ""))
                    if "S" in lat_str:
                        lat = -lat
                    lon = float(lon_str.replace("W", "").replace("E", ""))
                    if "W" in lon_str:
                        lon = -lon

                    wind = float(parts[6]) if len(parts) > 6 and parts[6].strip() else 0
                    pressure = float(parts[7]) if len(parts) > 7 and parts[7].strip() and parts[7].strip() != "-999" else None

                    current_storm["track_points"].append({
                        "lat": lat, "lon": lon, "wind": wind, "pressure": pressure,
                        "date": parts[0].strip(), "time": parts[1].strip(),
                    })

                    if wind > current_storm["max_wind"]:
                        current_storm["max_wind"] = wind
                    if pressure and pressure < current_storm["min_pressure"]:
                        current_storm["min_pressure"] = pressure
                except (ValueError, IndexError):
                    pass

                if lines_remaining == 0:
                    current_storm["category"] = wind_to_category(current_storm["max_wind"])
                    if current_storm["min_pressure"] == 9999:
                        current_storm["min_pressure"] = None
                    storms.append(current_storm)
                    current_storm = None

        return storms


def wind_to_category(wind_kt: float) -> int:
    if wind_kt >= 137:
        return 5
    if wind_kt >= 113:
        return 4
    if wind_kt >= 96:
        return 3
    if wind_kt >= 83:
        return 2
    if wind_kt >= 64:
        return 1
    return 0


HURRICANE_TRACKS_SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"storm_id": "AL122005", "name": "KATRINA", "year": 2005, "max_wind": 150, "category": 5, "color": "#d32f2f"},
            "geometry": {"type": "LineString", "coordinates": [
                [-75.1, 23.1], [-76.0, 23.4], [-78.4, 24.5], [-81.3, 25.3],
                [-83.2, 25.8], [-85.7, 26.0], [-87.7, 27.2], [-89.1, 28.2],
                [-89.6, 29.3], [-89.6, 30.2],
            ]},
        },
        {
            "type": "Feature",
            "properties": {"storm_id": "AL092017", "name": "IRMA", "year": 2017, "max_wind": 155, "category": 5, "color": "#d32f2f"},
            "geometry": {"type": "LineString", "coordinates": [
                [-42.0, 16.0], [-50.0, 16.5], [-57.0, 16.8], [-61.0, 17.0],
                [-64.0, 18.0], [-67.0, 18.5], [-72.0, 21.0], [-77.0, 22.0],
                [-80.0, 24.5], [-81.0, 25.5], [-81.5, 26.5], [-82.0, 28.0],
                [-83.0, 30.0], [-84.0, 32.0],
            ]},
        },
        {
            "type": "Feature",
            "properties": {"storm_id": "AL182012", "name": "SANDY", "year": 2012, "max_wind": 100, "category": 2, "color": "#f57c00"},
            "geometry": {"type": "LineString", "coordinates": [
                [-77.0, 14.3], [-78.5, 17.5], [-78.0, 19.0], [-77.5, 21.0],
                [-76.0, 24.0], [-74.5, 28.0], [-73.0, 33.0], [-74.0, 38.0],
                [-74.5, 40.0],
            ]},
        },
        {
            "type": "Feature",
            "properties": {"storm_id": "AL042008", "name": "DOLLY", "year": 2008, "max_wind": 75, "category": 1, "color": "#fbc02d"},
            "geometry": {"type": "LineString", "coordinates": [
                [-83.0, 19.5], [-85.0, 19.8], [-87.5, 20.5], [-90.0, 21.0],
                [-93.5, 22.0], [-96.0, 24.0], [-97.0, 26.5],
            ]},
        },
        {
            "type": "Feature",
            "properties": {"storm_id": "AL062018", "name": "FLORENCE", "year": 2018, "max_wind": 130, "category": 4, "color": "#e53935"},
            "geometry": {"type": "LineString", "coordinates": [
                [-22.0, 11.0], [-35.0, 14.0], [-48.0, 17.5], [-55.0, 20.0],
                [-60.0, 22.5], [-65.0, 25.0], [-70.0, 28.0], [-74.0, 31.0],
                [-76.0, 33.0], [-77.5, 34.0],
            ]},
        },
    ],
}


def get_hurricane_tracks_geojson() -> dict:
    scraped_path = settings.CATALOG_DIR / "hurricane_tracks_scraped.geojson"
    if scraped_path.exists():
        with open(scraped_path) as f:
            return json.load(f)

    filepath = settings.CATALOG_DIR / "hurricane_tracks.geojson"
    if not filepath.exists():
        with open(filepath, "w") as f:
            json.dump(HURRICANE_TRACKS_SAMPLE, f)
    else:
        with open(filepath) as f:
            return json.load(f)
    return HURRICANE_TRACKS_SAMPLE


def estimate_hurricane_risk(lat: float, lon: float) -> dict:
    coast_proximity = 1.0
    gulf_atlantic = False

    if -98 <= lon <= -80 and 25 <= lat <= 31:
        coast_proximity = 0.1
        gulf_atlantic = True
    elif -82 <= lon <= -75 and 25 <= lat <= 36:
        coast_proximity = 0.15
        gulf_atlantic = True
    elif -75 <= lon <= -70 and 35 <= lat <= 42:
        coast_proximity = 0.3
        gulf_atlantic = True
    elif -67 <= lon <= -65 and 17 <= lat <= 19:
        coast_proximity = 0.1
        gulf_atlantic = True

    if not gulf_atlantic:
        return {"max_wind_prob": 5.0, "track_density": 0, "distance_factor": 1.0, "source": "Outside hurricane belt"}

    track_density = 0
    for feature in HURRICANE_TRACKS_SAMPLE["features"]:
        coords = feature["geometry"]["coordinates"]
        for c in coords:
            dist = math.sqrt((c[0] - lon) ** 2 + (c[1] - lat) ** 2)
            if dist < 3.0:
                track_density += 1

    wind_prob = min(95, max(5, (1 - coast_proximity) * 60 + track_density * 5))

    return {
        "max_wind_prob": round(wind_prob, 1),
        "track_density": track_density,
        "distance_factor": round(coast_proximity, 2),
        "source": "Historical track analysis",
    }

import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def geocode_address(address: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params = {
                "address": address,
                "benchmark": "Public_AR_Current",
                "format": "json",
            }
            response = await client.get(settings.CENSUS_GEOCODER_API, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("result", {}).get("addressMatches", [])
            if not results:
                logger.warning("No geocoding match for: %s", address)
                return None

            match = results[0]
            coords = match["coordinates"]

            return {
                "latitude": coords["y"],
                "longitude": coords["x"],
                "matched_address": match["matchedAddress"],
                "input_address": address,
            }
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.error("Geocoding error for '%s': %s", address, e)
        return None


async def batch_geocode(addresses: list[str]) -> list[dict | None]:
    results = []
    for addr in addresses:
        result = await geocode_address(addr)
        results.append(result)
    return results

import math
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.location import Location


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in meters

    Uses the Haversine formula.
    """
    # Earth mean radius in meters
    EARTH_RADIUS_METERS = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c


def find_nearest_location(
    db: Session,
    latitude: float,
    longitude: float,
    threshold_meters: float = 15.0,
) -> Optional[Tuple[Location, float]]:
    """Query all locations and find the closest one within the given threshold distance in meters.

    Returns:
        A tuple of (Location, distance_in_meters) if within threshold, otherwise None.
    """
    locations = db.query(Location).all()
    if not locations:
        return None

    nearest_loc: Optional[Location] = None
    min_dist = float("inf")

    for loc in locations:
        dist = haversine_distance(latitude, longitude, loc.latitude, loc.longitude)
        if dist < min_dist:
            min_dist = dist
            nearest_loc = loc

    if nearest_loc is not None and min_dist <= threshold_meters:
        return nearest_loc, min_dist

    return None

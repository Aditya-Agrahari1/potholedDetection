import pytest
from app.models.location import Location
from app.services.matcher import haversine_distance, find_nearest_location


def test_haversine_same_point():
    """Distance between identical coordinates must be 0 meters."""
    dist = haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
    assert dist == pytest.approx(0.0, abs=1e-3)


def test_haversine_short_distance():
    """Test small displacement (~11 meters latitude difference)."""
    # 0.0001 degrees latitude is approximately 11.1 meters
    lat1, lon1 = 37.774900, -122.419400
    lat2, lon2 = 37.774999, -122.419400
    dist = haversine_distance(lat1, lon1, lat2, lon2)
    assert 10.0 <= dist <= 12.0


def test_haversine_large_distance():
    """San Francisco to New York is approximately 4,130 km."""
    sf_lat, sf_lon = 37.7749, -122.4194
    ny_lat, ny_lon = 40.7128, -74.0060
    dist = haversine_distance(sf_lat, sf_lon, ny_lat, ny_lon)
    # Between 4,100 km and 4,200 km
    assert 4_100_000 <= dist <= 4_200_000


def test_find_nearest_location_within_threshold(test_db_session):
    """Find location when distance is under 15 meters."""
    loc = Location(latitude=37.774900, longitude=-122.419400)
    test_db_session.add(loc)
    test_db_session.commit()

    # Query point ~6 meters away (0.00005 deg lat)
    result = find_nearest_location(
        test_db_session,
        latitude=37.774950,
        longitude=-122.419400,
        threshold_meters=15.0,
    )
    assert result is not None
    matched_loc, dist = result
    assert matched_loc.id == loc.id
    assert dist < 15.0


def test_find_nearest_location_exceeds_threshold(test_db_session):
    """Return None when nearest location is further than threshold."""
    loc = Location(latitude=37.774900, longitude=-122.419400)
    test_db_session.add(loc)
    test_db_session.commit()

    # Query point ~55 meters away (0.0005 deg lat)
    result = find_nearest_location(
        test_db_session,
        latitude=37.775400,
        longitude=-122.419400,
        threshold_meters=15.0,
    )
    assert result is None


def test_find_nearest_location_empty_database(test_db_session):
    """Return None when database has no locations."""
    result = find_nearest_location(
        test_db_session,
        latitude=37.774900,
        longitude=-122.419400,
        threshold_meters=15.0,
    )
    assert result is None

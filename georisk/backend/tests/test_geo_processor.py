"""Tests for app.services.geo_processor – spatial utilities."""
import pytest

from app.services.geo_processor import (
    hexbin_accumulation,
    properties_to_geodataframe,
)


class TestHexbinAccumulation:
    def test_empty_returns_empty(self):
        assert hexbin_accumulation([]) == []

    def test_single_property(self):
        props = [{"id": 1, "latitude": 37.77, "longitude": -122.42, "tiv": 1_000_000}]
        result = hexbin_accumulation(props)
        assert len(result) == 1
        assert result[0]["count"] == 1
        assert result[0]["total_tiv"] == 1_000_000

    def test_colocated_properties(self):
        props = [
            {"id": 1, "latitude": 37.77, "longitude": -122.42, "tiv": 100},
            {"id": 2, "latitude": 37.77, "longitude": -122.42, "tiv": 200},
        ]
        result = hexbin_accumulation(props)
        assert len(result) == 1
        assert result[0]["count"] == 2
        assert result[0]["total_tiv"] == 300

    def test_distant_properties(self):
        props = [
            {"id": 1, "latitude": 37.77, "longitude": -122.42, "tiv": 100},
            {"id": 2, "latitude": 25.76, "longitude": -80.19, "tiv": 200},
        ]
        result = hexbin_accumulation(props)
        assert len(result) == 2

    def test_sorted_by_tiv(self):
        props = [
            {"id": 1, "latitude": 37.77, "longitude": -122.42, "tiv": 100},
            {"id": 2, "latitude": 25.76, "longitude": -80.19, "tiv": 500},
        ]
        result = hexbin_accumulation(props)
        assert result[0]["total_tiv"] >= result[1]["total_tiv"]


class TestPropertiesToGeoDataFrame:
    def test_basic_conversion(self):
        props = [
            {"id": 1, "latitude": 37.77, "longitude": -122.42, "tiv": 100},
            {"id": 2, "latitude": 25.76, "longitude": -80.19, "tiv": 200},
        ]
        gdf = properties_to_geodataframe(props)
        assert len(gdf) == 2
        assert gdf.crs.to_epsg() == 4326

    def test_geometry_column_exists(self):
        props = [{"id": 1, "latitude": 30.0, "longitude": -90.0, "tiv": 0}]
        gdf = properties_to_geodataframe(props)
        assert "geometry" in gdf.columns

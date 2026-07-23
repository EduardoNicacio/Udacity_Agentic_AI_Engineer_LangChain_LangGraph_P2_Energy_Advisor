import builtins
import pytest
import os
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
from tools import (
    get_weather_forecast,
    get_electricity_prices,
    calculate_energy_savings,
    search_energy_tips,
    TOOL_KIT,
    query_energy_usage,
    query_solar_generation,
    get_recent_energy_summary,
)


EXPECTED_TOOL_NAMES = [
    "get_weather_forecast",
    "get_electricity_prices",
    "query_energy_usage",
    "query_solar_generation",
    "get_recent_energy_summary",
    "search_energy_tips",
    "calculate_energy_savings",
]


class TestGetWeatherForecast:
    def test_determinism(self):
        r1 = get_weather_forecast.invoke({"location": "San Francisco, CA", "days": 1})
        r2 = get_weather_forecast.invoke({"location": "San Francisco, CA", "days": 1})
        assert r1 == r2

    def test_output_structure(self):
        result = get_weather_forecast.invoke({"location": "Denver, CO", "days": 2})
        assert "location" in result
        assert "forecast_days" in result
        assert "current" in result
        assert "hourly" in result
        assert result["location"] == "Denver, CO"
        assert result["forecast_days"] == 2
        assert len(result["hourly"]) == 48

    def test_hourly_entry_fields(self):
        result = get_weather_forecast.invoke({"location": "Austin, TX", "days": 1})
        entry = result["hourly"][0]
        assert "hour" in entry
        assert "temperature_c" in entry
        assert "condition" in entry
        assert "solar_irradiance" in entry
        assert "humidity" in entry
        assert "wind_speed" in entry

    def test_current_is_single_entry(self):
        result = get_weather_forecast.invoke({"location": "Portland, OR", "days": 1})
        current = result["current"]
        assert isinstance(current, dict)
        assert "temperature_c" in current
        assert "condition" in current
        assert "humidity" in current

    def test_days_clamped_min(self):
        result = get_weather_forecast.invoke({"location": "Seattle, WA", "days": 0})
        assert result["forecast_days"] == 1
        assert len(result["hourly"]) == 24

    def test_days_clamped_max(self):
        result = get_weather_forecast.invoke({"location": "Boston, MA", "days": 10})
        assert result["forecast_days"] == 7
        assert len(result["hourly"]) == 168

    def test_location_base_temp_san_francisco(self):
        result = get_weather_forecast.invoke({"location": "San Francisco, CA", "days": 1})
        temp = result["current"]["temperature_c"]
        assert 10 <= temp <= 28

    def test_location_base_temp_phoenix(self):
        result = get_weather_forecast.invoke({"location": "Phoenix, AZ", "days": 1})
        temp = result["current"]["temperature_c"]
        assert 20 <= temp <= 42

    def test_location_base_temp_miami(self):
        result = get_weather_forecast.invoke({"location": "Miami, FL", "days": 1})
        temp = result["current"]["temperature_c"]
        assert 16 <= temp <= 38

    def test_location_base_temp_chicago(self):
        result = get_weather_forecast.invoke({"location": "Chicago, IL", "days": 1})
        temp = result["current"]["temperature_c"]
        assert 5 <= temp <= 25

    def test_location_base_temp_default(self):
        result = get_weather_forecast.invoke({"location": "London, UK", "days": 1})
        assert result["location"] == "London, UK"

    def test_solar_irradiance_nighttime_zero(self):
        result = get_weather_forecast.invoke({"location": "Los Angeles, CA", "days": 1})
        for entry in result["hourly"]:
            if entry["hour"] < 6 or entry["hour"] > 20:
                assert entry["solar_irradiance"] == 0

    def test_error_returns_dict(self):
        with patch("tools.random.seed", side_effect=RuntimeError("boom")):
            result = get_weather_forecast.invoke({"location": "Nowhere", "days": 1})
            assert "error" in result


class TestGetElectricityPrices:
    def test_determinism(self):
        r1 = get_electricity_prices.invoke({"date": "2026-07-23"})
        r2 = get_electricity_prices.invoke({"date": "2026-07-23"})
        assert r1 == r2

    def test_output_structure(self):
        result = get_electricity_prices.invoke({"date": "2026-07-04"})
        assert "date" in result
        assert "pricing_type" in result
        assert "currency" in result
        assert "unit" in result
        assert "hourly_rates" in result
        assert result["pricing_type"] == "time_of_use"
        assert result["currency"] == "USD"
        assert result["unit"] == "per_kWh"

    def test_24_hourly_rates(self):
        result = get_electricity_prices.invoke({"date": "2026-12-25"})
        assert len(result["hourly_rates"]) == 24

    def test_all_periods_present(self):
        result = get_electricity_prices.invoke({"date": "2026-03-15"})
        periods = {h["period"] for h in result["hourly_rates"]}
        assert periods == {"off-peak", "mid-peak", "on-peak"}

    def test_rate_entry_fields(self):
        result = get_electricity_prices.invoke({"date": "2026-01-01"})
        entry = result["hourly_rates"][0]
        assert "hour" in entry
        assert "rate" in entry
        assert "period" in entry
        assert "demand_charge" in entry

    def test_off_peak_lower_than_on_peak(self):
        result = get_electricity_prices.invoke({"date": "2026-06-15"})
        off_peak_rates = [
            h["rate"] for h in result["hourly_rates"] if h["period"] == "off-peak"
        ]
        on_peak_rates = [
            h["rate"] for h in result["hourly_rates"] if h["period"] == "on-peak"
        ]
        assert max(off_peak_rates) < min(on_peak_rates)

    def test_demand_charge_only_on_peak(self):
        result = get_electricity_prices.invoke({"date": "2026-09-01"})
        for h in result["hourly_rates"]:
            if h["period"] == "on-peak":
                assert h["demand_charge"] == 0.02
            else:
                assert h["demand_charge"] == 0.0

    def test_default_date(self):
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_electricity_prices.invoke({})
        assert result["date"] == today

    def test_error_returns_dict(self):
        with patch("tools.random.seed", side_effect=RuntimeError("boom")):
            result = get_electricity_prices.invoke({"date": "bad-date"})
            assert "error" in result


class TestCalculateEnergySavings:
    def test_basic_savings(self):
        result = calculate_energy_savings.invoke({
            "device_type": "EV",
            "current_usage_kwh": 100.0,
            "optimized_usage_kwh": 60.0,
            "price_per_kwh": 0.15
        })
        assert result["savings_kwh"] == 40.0
        assert result["savings_usd"] == 6.0
        assert result["savings_percentage"] == 40.0
        assert result["annual_savings_usd"] == 2190.0

    def test_zero_usage(self):
        result = calculate_energy_savings.invoke({
            "device_type": "HVAC",
            "current_usage_kwh": 0.0,
            "optimized_usage_kwh": 0.0,
        })
        assert result["savings_kwh"] == 0.0
        assert result["savings_usd"] == 0.0
        assert result["savings_percentage"] == 0.0

    def test_no_savings(self):
        result = calculate_energy_savings.invoke({
            "device_type": "appliance",
            "current_usage_kwh": 50.0,
            "optimized_usage_kwh": 50.0,
        })
        assert result["savings_kwh"] == 0.0
        assert result["savings_usd"] == 0.0
        assert result["savings_percentage"] == 0.0

    def test_custom_price(self):
        result = calculate_energy_savings.invoke({
            "device_type": "EV",
            "current_usage_kwh": 100.0,
            "optimized_usage_kwh": 80.0,
            "price_per_kwh": 0.30
        })
        assert result["savings_kwh"] == 20.0
        assert result["savings_usd"] == 6.0
        assert result["annual_savings_usd"] == 2190.0

    def test_default_price(self):
        result = calculate_energy_savings.invoke({
            "device_type": "solar",
            "current_usage_kwh": 200.0,
            "optimized_usage_kwh": 150.0,
        })
        assert result["price_per_kwh"] == 0.12

    def test_rounding(self):
        result = calculate_energy_savings.invoke({
            "device_type": "appliance",
            "current_usage_kwh": 33.333,
            "optimized_usage_kwh": 11.111,
        })
        assert result["savings_kwh"] == 22.22
        assert round(result["savings_percentage"], 1) == 66.7

    def test_output_keys(self):
        result = calculate_energy_savings.invoke({
            "device_type": "EV",
            "current_usage_kwh": 100.0,
            "optimized_usage_kwh": 70.0,
        })
        expected_keys = {
            "device_type", "current_usage_kwh", "optimized_usage_kwh",
            "savings_kwh", "savings_usd", "savings_percentage",
            "price_per_kwh", "annual_savings_usd"
        }
        assert set(result.keys()) == expected_keys


class TestSearchEnergyTips:
    def test_fallback_when_chromadb_unavailable(self):
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "chromadb":
                raise ImportError("chromadb not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = search_energy_tips.invoke({
                "query": "HVAC tips",
                "max_results": 3
            })
            assert result["total_results"] == 0
            assert result["tips"] == []

    def test_error_handling(self):
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "chromadb":
                raise ImportError("chromadb not available")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = search_energy_tips.invoke({
                "query": "",
                "max_results": -1
            })
            assert isinstance(result, dict)
            assert "total_results" in result

    def test_output_structure(self):
        result = search_energy_tips.invoke({
            "query": "energy saving",
            "max_results": 2
        })
        assert "query" in result
        assert "total_results" in result
        assert "tips" in result
        if result.get("error"):
            assert result["total_results"] == 0


class TestQueryEnergyUsage:
    def test_invalid_date_format(self):
        result = query_energy_usage.invoke({
            "start_date": "invalid",
            "end_date": "2026-07-23"
        })
        assert "error" in result

    def test_invalid_date_format_end(self):
        result = query_energy_usage.invoke({
            "start_date": "2026-07-01",
            "end_date": "bad-date"
        })
        assert "error" in result

    def test_output_structure_on_success(self):
        result = query_energy_usage.invoke({
            "start_date": "2026-07-01",
            "end_date": "2026-07-23"
        })
        if "error" not in result:
            assert "start_date" in result
            assert "end_date" in result
            assert "total_records" in result
            assert "total_consumption_kwh" in result
            assert "records" in result


class TestQuerySolarGeneration:
    def test_invalid_date_format(self):
        result = query_solar_generation.invoke({
            "start_date": "not-a-date",
            "end_date": "2026-07-23"
        })
        assert "error" in result

    def test_output_structure_on_success(self):
        result = query_solar_generation.invoke({
            "start_date": "2026-07-01",
            "end_date": "2026-07-23"
        })
        if "error" not in result:
            assert "total_generation_kwh" in result
            assert "average_daily_generation" in result
            assert "records" in result


class TestGetRecentEnergySummary:
    def test_output_structure(self):
        result = get_recent_energy_summary.invoke({"hours": 24})
        if "error" not in result:
            assert "time_period_hours" in result
            assert "usage" in result
            assert "generation" in result
            assert "device_breakdown" in result["usage"]

    def test_negative_hours(self):
        result = get_recent_energy_summary.invoke({"hours": -1})
        if "error" not in result:
            assert isinstance(result, dict)


class TestToolKit:
    def test_all_tools_present(self):
        names = [t.name for t in TOOL_KIT]
        assert sorted(names) == sorted(EXPECTED_TOOL_NAMES)

    def test_tool_count(self):
        assert len(TOOL_KIT) == 7

    def test_each_tool_has_invoke_method(self):
        for tool in TOOL_KIT:
            assert hasattr(tool, "invoke")
            assert callable(tool.invoke)

    def test_each_tool_has_name(self):
        for tool in TOOL_KIT:
            assert isinstance(tool.name, str)
            assert len(tool.name) > 0

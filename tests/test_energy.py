import pytest
from datetime import datetime
from models.energy import EnergyUsage, SolarGeneration, DatabaseManager


class TestEnergyUsage:
    def test_create_instance(self, sample_timestamp):
        record = EnergyUsage(
            timestamp=sample_timestamp,
            consumption_kwh=12.5,
            device_type="EV",
            device_name="Tesla Model 3",
            cost_usd=1.50
        )
        assert record.timestamp == sample_timestamp
        assert record.consumption_kwh == 12.5
        assert record.device_type == "EV"
        assert record.device_name == "Tesla Model 3"
        assert record.cost_usd == 1.50

    def test_create_instance_minimal(self, sample_timestamp):
        record = EnergyUsage(
            timestamp=sample_timestamp,
            consumption_kwh=5.0
        )
        assert record.timestamp == sample_timestamp
        assert record.consumption_kwh == 5.0
        assert record.device_type is None
        assert record.device_name is None
        assert record.cost_usd is None

    def test_repr(self, sample_timestamp):
        record = EnergyUsage(
            timestamp=sample_timestamp,
            consumption_kwh=7.2,
            device_name="Main AC"
        )
        expected = f"<EnergyUsage(timestamp={sample_timestamp}, consumption=7.2kWh, device=Main AC)>"
        assert repr(record) == expected


class TestSolarGeneration:
    def test_create_instance(self, sample_timestamp):
        record = SolarGeneration(
            timestamp=sample_timestamp,
            generation_kwh=3.4,
            weather_condition="sunny",
            temperature_c=28.5,
            solar_irradiance=750.0
        )
        assert record.timestamp == sample_timestamp
        assert record.generation_kwh == 3.4
        assert record.weather_condition == "sunny"
        assert record.temperature_c == 28.5
        assert record.solar_irradiance == 750.0

    def test_repr(self, sample_timestamp):
        record = SolarGeneration(
            timestamp=sample_timestamp,
            generation_kwh=4.1,
            weather_condition="partly_cloudy"
        )
        expected = f"<SolarGeneration(timestamp={sample_timestamp}, generation=4.1kWh, weather=partly_cloudy)>"
        assert repr(record) == expected


class TestDatabaseManager:
    def test_init(self, temp_db_path):
        db = DatabaseManager(db_path=temp_db_path)
        assert db.db_path == temp_db_path

    def test_create_tables(self, temp_db_path):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()
        import os
        assert os.path.exists(temp_db_path)

    def test_add_and_query_usage(self, temp_db_path, sample_timestamp):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        record = db.add_usage_record(
            timestamp=sample_timestamp,
            consumption_kwh=10.0,
            device_type="appliance",
            device_name="Dishwasher",
            cost_usd=1.20
        )
        assert isinstance(record, EnergyUsage)

        results = db.get_usage_by_date_range(
            datetime(2026, 6, 1),
            datetime(2026, 8, 1)
        )
        assert len(results) == 1
        assert results[0].device_name == "Dishwasher"
        assert results[0].consumption_kwh == 10.0

    def test_add_and_query_generation(self, temp_db_path, sample_timestamp):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        record = db.add_generation_record(
            timestamp=sample_timestamp,
            generation_kwh=5.5,
            weather_condition="sunny",
            temperature_c=30.0,
            solar_irradiance=800.0
        )
        assert isinstance(record, SolarGeneration)

        results = db.get_generation_by_date_range(
            datetime(2026, 6, 1),
            datetime(2026, 8, 1)
        )
        assert len(results) == 1
        assert results[0].weather_condition == "sunny"
        assert results[0].generation_kwh == 5.5

    def test_query_usage_empty_range(self, temp_db_path):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        results = db.get_usage_by_date_range(
            datetime(2020, 1, 1),
            datetime(2020, 1, 2)
        )
        assert results == []

    def test_query_generation_empty_range(self, temp_db_path):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        results = db.get_generation_by_date_range(
            datetime(2020, 1, 1),
            datetime(2020, 1, 2)
        )
        assert results == []

    def test_multiple_records(self, temp_db_path):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        for hour in range(5):
            db.add_usage_record(
                timestamp=datetime(2026, 7, 1, hour, 0, 0),
                consumption_kwh=2.0,
                device_type="HVAC"
            )

        results = db.get_usage_by_date_range(
            datetime(2026, 7, 1),
            datetime(2026, 7, 2)
        )
        assert len(results) == 5

    def test_add_usage_returns_record(self, temp_db_path, sample_timestamp):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        record = db.add_usage_record(
            timestamp=sample_timestamp,
            consumption_kwh=15.0
        )
        assert isinstance(record, EnergyUsage)

        results = db.get_usage_by_date_range(
            sample_timestamp, sample_timestamp
        )
        assert len(results) == 1
        assert results[0].consumption_kwh == 15.0

    def test_add_generation_returns_record(self, temp_db_path, sample_timestamp):
        db = DatabaseManager(db_path=temp_db_path)
        db.create_tables()

        record = db.add_generation_record(
            timestamp=sample_timestamp,
            generation_kwh=8.0
        )
        assert isinstance(record, SolarGeneration)

        results = db.get_generation_by_date_range(
            sample_timestamp, sample_timestamp
        )
        assert len(results) == 1
        assert results[0].generation_kwh == 8.0

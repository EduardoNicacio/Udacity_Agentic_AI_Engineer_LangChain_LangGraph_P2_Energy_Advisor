"""
Tools for EcoHome Energy Advisor Agent
"""
import os
import glob
import random
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models.energy import DatabaseManager

db_manager = DatabaseManager()


@tool
def get_weather_forecast(location: str, days: int = 3) -> Dict[str, Any]:
    """
    Get weather forecast for a specific location and number of days.

    Args:
        location (str): Location to get weather for (e.g., "San Francisco, CA")
        days (int): Number of days to forecast (1-7)

    Returns:
        Dict[str, Any]: Weather forecast data including temperature, conditions, and solar irradiance
    """
    try:
        days = max(1, min(7, days))
        today = datetime.now().strftime("%Y-%m-%d")
        seed_str = f"{location}_{today}"
        random.seed(hash(seed_str) & 0x7FFFFFFF)

        location_lower = location.lower()
        if "san francisco" in location_lower or "sf" in location_lower:
            base_temp = 18
        elif "phoenix" in location_lower or "arizona" in location_lower:
            base_temp = 32
        elif "miami" in location_lower or "florida" in location_lower:
            base_temp = 28
        elif "chicago" in location_lower or "new york" in location_lower:
            base_temp = 15
        else:
            base_temp = 22

        conditions_pool = ["sunny", "partly_cloudy", "cloudy", "rainy"]
        condition_weights = [0.35, 0.30, 0.20, 0.15]

        hourly_all = []
        daily_conditions = []

        for day_offset in range(days):
            day_seed = hash(f"{seed_str}_day{day_offset}") & 0x7FFFFFFF
            rng = random.Random(day_seed)

            day_condition = rng.choices(conditions_pool, weights=condition_weights, k=1)[0]
            daily_conditions.append(day_condition)

            condition_mult = {"sunny": 1.0, "partly_cloudy": 0.65, "cloudy": 0.30, "rainy": 0.10}
            weather_mult = condition_mult[day_condition]

            for hour in range(24):
                hour_temp = base_temp + rng.uniform(-4, 4)
                hour_temp += 6 * (1 - abs(hour - 14) / 10) if 6 <= hour <= 20 else -3

                if 6 <= hour <= 20:
                    solar_curve = 1 - abs(hour - 13) / 7
                    solar_irradiance = max(0, 900 * solar_curve * weather_mult + rng.uniform(-30, 30))
                else:
                    solar_irradiance = 0

                humidity = rng.uniform(30, 80)
                wind_speed = rng.uniform(2, 20)

                hourly_all.append({
                    "hour": hour,
                    "temperature_c": round(hour_temp, 1),
                    "condition": day_condition,
                    "solar_irradiance": round(solar_irradiance, 1),
                    "humidity": round(humidity, 1),
                    "wind_speed": round(wind_speed, 1)
                })

        current = hourly_all[datetime.now().hour % 24].copy()

        forecast = {
            "location": location,
            "forecast_days": days,
            "current": current,
            "hourly": hourly_all
        }

        return forecast
    except Exception as e:
        return {"error": f"Failed to get weather forecast: {str(e)}"}


@tool
def get_electricity_prices(date: str = None) -> Dict[str, Any]:
    """
    Get electricity prices for a specific date or current day.

    Args:
        date (str): Date in YYYY-MM-DD format (defaults to today)

    Returns:
        Dict[str, Any]: Electricity pricing data with hourly rates
    """
    try:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        random.seed(hash(date) & 0x7FFFFFFF)

        # Off-peak: 22:00-06:00, Mid-peak: 06:00-10:00 & 14:00-18:00, On-peak: 10:00-14:00 & 18:00-22:00
        # Base rates
        off_peak_base = 0.08
        mid_peak_base = 0.12
        on_peak_base = 0.18

        hourly_rates = []

        for hour in range(24):
            if 22 <= hour or hour < 6:
                period = "off-peak"
                base_rate = off_peak_base
                demand_charge = 0.0
            elif 6 <= hour < 10:
                period = "mid-peak"
                base_rate = mid_peak_base
                demand_charge = 0.0
            elif 10 <= hour < 14:
                period = "on-peak"
                base_rate = on_peak_base
                demand_charge = 0.02
            elif 14 <= hour < 18:
                period = "mid-peak"
                base_rate = mid_peak_base
                demand_charge = 0.0
            else:
                period = "on-peak"
                base_rate = on_peak_base
                demand_charge = 0.02

            variation = random.uniform(-0.01, 0.01)
            rate = round(base_rate + variation, 4)

            hourly_rates.append({
                "hour": hour,
                "rate": rate,
                "period": period,
                "demand_charge": demand_charge
            })

        prices = {
            "date": date,
            "pricing_type": "time_of_use",
            "currency": "USD",
            "unit": "per_kWh",
            "hourly_rates": hourly_rates
        }

        return prices
    except Exception as e:
        return {"error": f"Failed to get electricity prices: {str(e)}"}


@tool
def query_energy_usage(start_date: str, end_date: str, device_type: str = None) -> Dict[str, Any]:
    """
    Query energy usage data from the database for a specific date range.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        device_type (str): Optional device type filter (e.g., "EV", "HVAC", "appliance")

    Returns:
        Dict[str, Any]: Energy usage data with consumption details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        records = db_manager.get_usage_by_date_range(start_dt, end_dt)

        if device_type:
            records = [r for r in records if r.device_type == device_type]

        usage_data = {
            "start_date": start_date,
            "end_date": end_date,
            "device_type": device_type,
            "total_records": len(records),
            "total_consumption_kwh": round(sum(r.consumption_kwh for r in records), 2),
            "total_cost_usd": round(sum(r.cost_usd or 0 for r in records), 2),
            "records": []
        }

        for record in records:
            usage_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "consumption_kwh": record.consumption_kwh,
                "device_type": record.device_type,
                "device_name": record.device_name,
                "cost_usd": record.cost_usd
            })

        return usage_data
    except Exception as e:
        return {"error": f"Failed to query energy usage: {str(e)}"}


@tool
def query_solar_generation(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Query solar generation data from the database for a specific date range.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format

    Returns:
        Dict[str, Any]: Solar generation data with production details
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        records = db_manager.get_generation_by_date_range(start_dt, end_dt)

        generation_data = {
            "start_date": start_date,
            "end_date": end_date,
            "total_records": len(records),
            "total_generation_kwh": round(sum(r.generation_kwh for r in records), 2),
            "average_daily_generation": round(sum(r.generation_kwh for r in records) / max(1, (end_dt - start_dt).days), 2),
            "records": []
        }

        for record in records:
            generation_data["records"].append({
                "timestamp": record.timestamp.isoformat(),
                "generation_kwh": record.generation_kwh,
                "weather_condition": record.weather_condition,
                "temperature_c": record.temperature_c,
                "solar_irradiance": record.solar_irradiance
            })

        return generation_data
    except Exception as e:
        return {"error": f"Failed to query solar generation: {str(e)}"}


@tool
def get_recent_energy_summary(hours: int = 24) -> Dict[str, Any]:
    """
    Get a summary of recent energy usage and solar generation.

    Args:
        hours (int): Number of hours to look back (default 24)

    Returns:
        Dict[str, Any]: Summary of recent energy data
    """
    try:
        usage_records = db_manager.get_recent_usage(hours)
        generation_records = db_manager.get_recent_generation(hours)

        summary = {
            "time_period_hours": hours,
            "usage": {
                "total_consumption_kwh": round(sum(r.consumption_kwh for r in usage_records), 2),
                "total_cost_usd": round(sum(r.cost_usd or 0 for r in usage_records), 2),
                "device_breakdown": {}
            },
            "generation": {
                "total_generation_kwh": round(sum(r.generation_kwh for r in generation_records), 2),
                "average_weather": "sunny" if generation_records else "unknown"
            }
        }

        for record in usage_records:
            device = record.device_type or "unknown"
            if device not in summary["usage"]["device_breakdown"]:
                summary["usage"]["device_breakdown"][device] = {
                    "consumption_kwh": 0,
                    "cost_usd": 0,
                    "records": 0
                }
            summary["usage"]["device_breakdown"][device]["consumption_kwh"] += record.consumption_kwh
            summary["usage"]["device_breakdown"][device]["cost_usd"] += record.cost_usd or 0
            summary["usage"]["device_breakdown"][device]["records"] += 1

        for device_data in summary["usage"]["device_breakdown"].values():
            device_data["consumption_kwh"] = round(device_data["consumption_kwh"], 2)
            device_data["cost_usd"] = round(device_data["cost_usd"], 2)

        return summary
    except Exception as e:
        return {"error": f"Failed to get recent energy summary: {str(e)}"}


@tool
def search_energy_tips(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search for energy-saving tips and best practices using RAG.

    Args:
        query (str): Search query for energy tips
        max_results (int): Maximum number of results to return

    Returns:
        Dict[str, Any]: Relevant energy tips and best practices
    """
    chroma_available = True
    try:
        import chromadb
    except ImportError:
        chroma_available = False

    if not chroma_available:
        return {
            "query": query,
            "total_results": 0,
            "tips": []
        }

    try:
        persist_directory = "data/vectorstore"
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)

        api_key = os.getenv("VOCAREUM_API_KEY")
        base_url = "https://openai.vocareum.com/v1"

        if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
            documents = []
            doc_dir = "data/documents"
            txt_files = glob.glob(os.path.join(doc_dir, "*.txt"))
            txt_files.sort()

            for doc_path in txt_files:
                if os.path.exists(doc_path):
                    loader = TextLoader(doc_path, encoding="utf-8")
                    docs = loader.load()
                    documents.extend(docs)

            if not documents:
                return {
                    "query": query,
                    "total_results": 0,
                    "tips": []
                }

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = text_splitter.split_documents(documents)

            embeddings = OpenAIEmbeddings(
                api_key=api_key,  # type: ignore
                base_url=base_url)
            vectorstore = Chroma.from_documents(
                documents=splits,
                embedding=embeddings,
                persist_directory=persist_directory
            )
        else:
            embeddings = OpenAIEmbeddings(
                api_key=api_key,  # type: ignore
                base_url=base_url)
            vectorstore = Chroma(
                persist_directory=persist_directory,
                embedding_function=embeddings
            )

        docs = vectorstore.similarity_search(query, k=max_results)

        results = {
            "query": query,
            "total_results": len(docs),
            "tips": []
        }

        for i, doc in enumerate(docs):
            results["tips"].append({
                "rank": i + 1,
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "relevance_score": "high" if i < 2 else "medium" if i < 4 else "low"
            })

        return results
    except Exception as e:
        return {
            "query": query,
            "total_results": 0,
            "tips": [],
            "error": f"Failed to search energy tips: {str(e)}"
        }


@tool
def calculate_energy_savings(device_type: str, current_usage_kwh: float,
                           optimized_usage_kwh: float, price_per_kwh: float = 0.12) -> Dict[str, Any]:
    """
    Calculate potential energy savings from optimization.

    Args:
        device_type (str): Type of device being optimized
        current_usage_kwh (float): Current energy usage in kWh
        optimized_usage_kwh (float): Optimized energy usage in kWh
        price_per_kwh (float): Price per kWh (default 0.12)

    Returns:
        Dict[str, Any]: Savings calculation results
    """
    savings_kwh = current_usage_kwh - optimized_usage_kwh
    savings_usd = savings_kwh * price_per_kwh
    savings_percentage = (savings_kwh / current_usage_kwh) * 100 if current_usage_kwh > 0 else 0

    return {
        "device_type": device_type,
        "current_usage_kwh": current_usage_kwh,
        "optimized_usage_kwh": optimized_usage_kwh,
        "savings_kwh": round(savings_kwh, 2),
        "savings_usd": round(savings_usd, 2),
        "savings_percentage": round(savings_percentage, 1),
        "price_per_kwh": price_per_kwh,
        "annual_savings_usd": round(savings_usd * 365, 2)
    }


TOOL_KIT = [
    get_weather_forecast,
    get_electricity_prices,
    query_energy_usage,
    query_solar_generation,
    get_recent_energy_summary,
    search_energy_tips,
    calculate_energy_savings
]

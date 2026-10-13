"""Tools for Aegis-NEO planetary defense agent."""

import math
import urllib.request
import json
from datetime import datetime, timezone


def get_current_date() -> str:
    """Returns today's date in YYYY-MM-DD format (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_near_earth_objects(start_date: str = "", end_date: str = "") -> str:
    """Fetches Near-Earth Objects (asteroids) from NASA's NeoWS public feed.

    Args:
        start_date: Starting date in YYYY-MM-DD format. Defaults to today UTC.
        end_date: Ending date in YYYY-MM-DD format. Defaults to start_date.

    Returns:
        JSON string containing the summary of detected NEOs with name, hazard status,
        estimated diameter in meters, close approach date, velocity, and miss distance.
    """
    if not start_date:
        start_date = get_current_date()
    if not end_date:
        end_date = start_date

    url = f"https://api.nasa.gov/neo/rest/v1/feed?start_date={start_date}&end_date={end_date}&api_key=DEMO_KEY"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Aegis-NEO-Planetary-Defense/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        near_earth_objects = data.get("near_earth_objects", {})
        results = []

        for date_key, items in near_earth_objects.items():
            for item in items:
                diam = item.get("estimated_diameter", {}).get("meters", {})
                min_d = diam.get("estimated_diameter_min", 0)
                max_d = diam.get("estimated_diameter_max", 0)
                avg_d = round((min_d + max_d) / 2, 1)

                close_approaches = item.get("close_approach_data", [])
                approach_info = {}
                if close_approaches:
                    cad = close_approaches[0]
                    v_kps = float(cad.get("relative_velocity", {}).get("kilometers_per_second", 0))
                    miss_km = float(cad.get("miss_distance", {}).get("kilometers", 0))
                    approach_info = {
                        "close_approach_date": cad.get("close_approach_date_full", cad.get("close_approach_date")),
                        "velocity_km_s": round(v_kps, 2),
                        "velocity_km_h": round(v_kps * 3600, 1),
                        "miss_distance_km": round(miss_km, 0),
                        "miss_distance_lunar": round(miss_km / 384400, 2), # In lunar distances (LD)
                        "orbiting_body": cad.get("orbiting_body"),
                    }

                results.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "nasa_jpl_url": item.get("nasa_jpl_url"),
                    "absolute_magnitude_h": item.get("absolute_magnitude_h"),
                    "is_potentially_hazardous": item.get("is_potentially_hazardous_asteroid", False),
                    "estimated_diameter_meters": avg_d,
                    "approach": approach_info
                })

        # Sort hazardous first, then closest miss distance
        results.sort(key=lambda x: (not x["is_potentially_hazardous"], x["approach"].get("miss_distance_km", float("inf"))))

        return json.dumps({
            "query_range": f"{start_date} to {end_date}",
            "element_count": data.get("element_count", len(results)),
            "neo_threat_list": results[:10]  # Return top 10 most relevant
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"Failed to retrieve NASA NEO data: {str(e)}",
            "fallback_instruction": "Use simulated asteroid telemetry (e.g., Asteroid 99942 Apophis or 2024 YR4) for testing."
        })


def calculate_impact_physics(diameter_meters: float, velocity_km_s: float, density_kg_m3: float = 2600.0) -> str:
    """Calculates potential kinetic impact energy, TNT equivalent, and crater estimate.

    Args:
        diameter_meters: Asteroid diameter in meters.
        velocity_km_s: Impact velocity in km/s (typical Earth impact is 15-25 km/s).
        density_kg_m3: Density of impactor in kg/m^3 (default 2600 kg/m^3 for rocky chondrite).

    Returns:
        JSON string with impact energy in Joules, Megatons of TNT, and estimated crater size.
    """
    radius = diameter_meters / 2.0
    volume = (4.0 / 3.0) * math.pi * (radius ** 3)
    mass_kg = volume * density_kg_m3

    velocity_m_s = velocity_km_s * 1000.0
    kinetic_energy_joules = 0.5 * mass_kg * (velocity_m_s ** 2)

    # 1 Megaton of TNT = 4.184e15 Joules
    megatons_tnt = kinetic_energy_joules / 4.184e15

    # Simple scaling law for transient crater diameter in rock: D_crater ≈ 1.8 * (E / 1e12)^0.28
    # where E is energy in Joules
    estimated_crater_diameter_m = 1.8 * ((kinetic_energy_joules / 1e12) ** 0.28) if kinetic_energy_joules > 0 else 0

    severity = "Negligible / High-altitude airburst"
    if megatons_tnt > 100000:
        severity = "Extinction Level Event (Global Catastrophe)"
    elif megatons_tnt > 1000:
        severity = "Continental devastation / Nuclear winter"
    elif megatons_tnt > 50:
        severity = "Regional disaster (Tunguska / Major metro destruction)"
    elif megatons_tnt > 0.5:
        severity = "Local blast damage / Window breakage (Chelyabinsk scale)"

    return json.dumps({
        "impactor_stats": {
            "diameter_m": diameter_meters,
            "velocity_km_s": velocity_km_s,
            "estimated_mass_metric_tons": round(mass_kg / 1000.0, 1)
        },
        "kinetic_energy": {
            "joules": f"{kinetic_energy_joules:.3e}",
            "megatons_tnt": round(megatons_tnt, 2),
            "hiroshima_equivalents": round(megatons_tnt / 0.015, 1)
        },
        "impact_effects": {
            "severity_assessment": severity,
            "estimated_crater_diameter_km": round(estimated_crater_diameter_m / 1000.0, 2),
            "estimated_crater_diameter_m": round(estimated_crater_diameter_m, 1)
        }
    }, indent=2)


def simulate_deflection_mission(
    asteroid_name: str,
    method: str,
    lead_time_years: float,
    asteroid_diameter_m: float = 150.0
) -> str:
    """Simulates a planetary defense mitigation mission (DART style).

    Args:
        asteroid_name: Name or designation of the asteroid (e.g. 'Apophis', '2024 YR4').
        method: Deflection technique ('Kinetic Impactor', 'Gravity Tractor', or 'Nuclear Standoff Burst').
        lead_time_years: Years before close approach / projected impact.
        asteroid_diameter_m: Estimated diameter in meters.

    Returns:
        JSON string with mission feasibility, required delta-V, and mission outcome report.
    """
    method_normalized = method.lower()

    if "kinetic" in method_normalized:
        # Kinetic impactor: Effective for diameters < 500m with at least 5-10 years lead time
        is_viable = (asteroid_diameter_m <= 400.0 and lead_time_years >= 3.0) or (lead_time_years >= 8.0)
        recommended_crafts = math.ceil(asteroid_diameter_m / 100.0)
        feasibility_score = 88 if is_viable else 45
        tech_readiness = "TRL 9 (Flight Proven by NASA DART Mission)"
        notes = f"Requires {recommended_crafts} coordinated impactor spacecraft."
    elif "gravity" in method_normalized:
        # Gravity tractor: Requires decades of lead time and smaller mass
        is_viable = (asteroid_diameter_m <= 250.0 and lead_time_years >= 15.0)
        feasibility_score = 75 if is_viable else 25
        tech_readiness = "TRL 6 (Demonstrated ion drive components)"
        notes = "Station-keeping ion drive craft slowly pulls asteroid via mutual gravity over 10-20 years."
    elif "nuclear" in method_normalized:
        # Standoff nuclear pulse: Last resort for huge bodies or short lead time
        is_viable = lead_time_years >= 1.0
        feasibility_score = 92 if is_viable else 50
        tech_readiness = "TRL 7 (Requires UN space treaty exception & heavy lift launch)"
        notes = "X-ray ablation of asteroid surface vaporizes material, generating a rocket reaction force."
    else:
        return json.dumps({
            "error": f"Unknown deflection method '{method}'. Supported methods: 'Kinetic Impactor', 'Gravity Tractor', 'Nuclear Standoff Burst'."
        })

    return json.dumps({
        "mission_designation": f"PROJECT SHIELD: Intercept {asteroid_name}",
        "target": asteroid_name,
        "diameter_m": asteroid_diameter_m,
        "selected_method": method,
        "lead_time_years": lead_time_years,
        "evaluation": {
            "viability": "RECOMMENDED" if is_viable else "HIGH RISK / INSUFFICIENT LEAD TIME",
            "feasibility_score_pct": feasibility_score,
            "technology_readiness": tech_readiness,
            "tactical_notes": notes
        }
    }, indent=2)

def generate_intercept_tactical_visual(asteroid_name: str, trajectory_type: str = "Kinetic Impact Intercept") -> str:
    """Generates a tactical visual radar rendering of an asteroid interception trajectory.

    Args:
        asteroid_name: Name of target asteroid (e.g. 'Apophis', '2024 YR4').
        trajectory_type: Interception geometry or mission profile.

    Returns:
        JSON string containing tactical display specs and visualization prompt description.
    """
    return json.dumps({
        "tactical_display": {
            "target": asteroid_name,
            "trajectory": trajectory_type,
            "telemetry_overlay": "Vectors: Velocity V_rel, Impact Delta-V vector, Earth gravitational contour lines",
            "visual_description": f"High-contrast planetary defense heads-up radar display showing {asteroid_name} orbital path approaching Earth, with glowing green intercept arc and impact point coordinates."
        }
    }, indent=2)

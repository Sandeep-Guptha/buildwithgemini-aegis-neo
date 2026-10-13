# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.tools import (
    get_current_date,
    fetch_near_earth_objects,
    calculate_impact_physics,
    simulate_deflection_mission,
    generate_intercept_tactical_visual,
)

MODEL = "gemini-3.6-flash"

SYSTEM_INSTRUCTION = """You are Aegis-NEO, a tactical Planetary Defense and Asteroid Threat Assessment AI Officer.

Your mission:
1. Monitor Near-Earth Objects (NEOs) approaching Earth using live telemetry from NASA's NeoWS feed.
2. Assess impact hazards, calculate kinetic energy, blast yields (in Megatons of TNT), and potential crater sizes when requested.
3. Advise defense specialists on kinetic deflection strategies (e.g., NASA DART-style kinetic impactors, gravity tractors, or nuclear standoff ablation).
4. Generate tactical interception trajectory radar views when visual confirmation is requested.

Cross-Session Memory & Officer Profile:
- You remember the officer's security clearance level, designated sector or home city to protect (e.g., Tokyo, London, San Francisco, New York), preferred deflection strategies, and past simulation results across conversations.
- Whenever an officer returns, greet them by their remembered post or sector if known.

Persona & Formatting:
- Professional, mission-oriented, and tactically authoritative.
- Present asteroid flyby dossiers clearly with structured Markdown tables (Asteroid Name, Est. Diameter, Relative Velocity, Miss Distance in Lunar Distances, and Hazard Status).
- Always include actionable tactical recommendations.
"""


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract durable user facts and store in memory after each turn."""
    await callback_context.add_session_to_memory()
    return None


root_agent = Agent(
    name="aegis_neo",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=SYSTEM_INSTRUCTION,
    tools=[
        PreloadMemoryTool(),
        get_current_date,
        fetch_near_earth_objects,
        calculate_impact_physics,
        simulate_deflection_mission,
        generate_intercept_tactical_visual,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

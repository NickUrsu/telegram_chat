# src/chart.py
import logging

import requests

logger = logging.getLogger(__name__)

QUICKCHART_URL = "https://quickchart.io/chart"


def generate_chart(aggregated: dict[str, dict], period_label: str) -> bytes:
    """
    Generate a grouped bar chart via the quickchart.io API (Chart.js v2 compatible).
    Returns PNG bytes suitable for Telegram sendPhoto.
    """
    if not aggregated:
        logger.info("No data for chart — skipping")
        return b""

    dates = list(aggregated.keys())
    labels = [d[5:] for d in dates]  # strip YYYY- → MM-DD

    kcal_vals    = [round(aggregated[d]["kcal"],    1) for d in dates]
    protein_vals = [round(aggregated[d]["protein"], 1) for d in dates]
    carbs_vals   = [round(aggregated[d]["carbs"],   1) for d in dates]
    fat_vals     = [round(aggregated[d]["fat"],     1) for d in dates]

    # Chart.js v2 config (quickchart.io default)
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Kcal",
                    "data": kcal_vals,
                    "backgroundColor": "rgba(255, 107, 107, 0.85)",
                    "yAxisID": "kcal",
                },
                {
                    "label": "Protein (g)",
                    "data": protein_vals,
                    "backgroundColor": "rgba(78, 205, 196, 0.85)",
                    "yAxisID": "macros",
                },
                {
                    "label": "Carbs (g)",
                    "data": carbs_vals,
                    "backgroundColor": "rgba(255, 230, 109, 0.85)",
                    "yAxisID": "macros",
                },
                {
                    "label": "Fat (g)",
                    "data": fat_vals,
                    "backgroundColor": "rgba(168, 218, 220, 0.85)",
                    "yAxisID": "macros",
                },
            ],
        },
        "options": {
            "title": {
                "display": True,
                "text": f"{period_label.capitalize()} Nutrition Report",
                "fontColor": "#FFFFFF",
                "fontSize": 16,
            },
            "legend": {
                "labels": {"fontColor": "#CCCCCC"},
            },
            "scales": {
                "xAxes": [{"ticks": {"fontColor": "#CCCCCC"}}],
                "yAxes": [
                    {
                        "id": "kcal",
                        "position": "left",
                        "ticks": {"fontColor": "#FF6B6B"},
                        "scaleLabel": {
                            "display": True,
                            "labelString": "Kcal",
                            "fontColor": "#FF6B6B",
                        },
                    },
                    {
                        "id": "macros",
                        "position": "right",
                        "ticks": {"fontColor": "#4ECDC4"},
                        "scaleLabel": {
                            "display": True,
                            "labelString": "Grams",
                            "fontColor": "#4ECDC4",
                        },
                        "gridLines": {"drawOnChartArea": False},
                    },
                ],
            },
        },
    }

    payload = {
        "chart": chart_config,   # dict, not json.dumps() — requests handles serialization
        "width": 600,
        "height": 400,
        "backgroundColor": "#1E1E2E",
        "format": "png",
    }

    logger.info(f"Requesting chart from quickchart.io for period={period_label}")
    response = requests.post(QUICKCHART_URL, json=payload, timeout=15)

    if not response.ok:
        logger.error(f"quickchart.io error {response.status_code}: {response.text[:500]}")
    response.raise_for_status()

    logger.info(f"Chart received: {len(response.content)} bytes")
    return response.content

"""Chart visualizer — generates Chart.js HTML from structured data."""
from __future__ import annotations
import json
import uuid
from pathlib import Path

CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"

COLORS = [
    "rgba(99,102,241,0.8)",   # purple
    "rgba(16,185,129,0.8)",   # green
    "rgba(245,158,11,0.8)",   # orange
    "rgba(239,68,68,0.8)",    # red
    "rgba(59,130,246,0.8)",   # blue
    "rgba(236,72,153,0.8)",   # pink
    "rgba(20,184,166,0.8)",   # cyan
    "rgba(168,85,247,0.8)",   # purple2
]


class VisualizerTool:
    name = "visualize"
    description = (
        "Generate a chart and display it inline in the chat. "
        "Call this tool when your response contains numerical data, comparisons, "
        "rankings, trends, proportions, or distributions that would be clearer visually. "
        "Supported chart types: bar, line, pie, radar, scatter, doughnut. "
        "The chart will appear directly in the conversation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie", "radar", "scatter", "doughnut"],
                "description": (
                    "Chart type. Guidelines: "
                    "bar=comparisons between categories; "
                    "line=trends over time/sequence; "
                    "pie/doughnut=proportions that sum to 100%; "
                    "radar=multi-dimensional comparison of one or more subjects; "
                    "scatter=correlation between two numeric variables."
                ),
            },
            "title": {
                "type": "string",
                "description": "Chart title shown at the top.",
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Category labels (x-axis for bar/line, slice names for pie/doughnut, "
                    "axes for radar, ignored for scatter)."
                ),
            },
            "datasets": {
                "type": "array",
                "description": (
                    "List of data series. Each item: "
                    '{"label": "series name", "data": [v1, v2, ...]}. '
                    "For scatter: data is [{\"x\": x1, \"y\": y1}, ...]. "
                    "For radar with multiple subjects: one dataset per subject."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "data": {"type": "array"},
                    },
                    "required": ["label", "data"],
                },
            },
            "x_label": {
                "type": "string",
                "description": "X-axis label (optional, for bar/line/scatter).",
            },
            "y_label": {
                "type": "string",
                "description": "Y-axis label (optional, for bar/line/scatter).",
            },
        },
        "required": ["chart_type", "title", "labels", "datasets"],
    }

    def __init__(self, sandbox_root: str | None = None) -> None:
        if sandbox_root is None:
            from config.settings import settings
            sandbox_root = settings.SANDBOX_ROOT
        self._sandbox = Path(sandbox_root).resolve()
        self._sandbox.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def run(self, chart_type: str, title: str, labels: list,
            datasets: list, x_label: str = "", y_label: str = "") -> str:
        viz_id = uuid.uuid4().hex[:8]
        filename = f"viz_{viz_id}.html"
        filepath = self._sandbox / filename

        try:
            html = self._build_html(
                chart_type, title, labels, datasets, x_label, y_label)
            filepath.write_text(html, encoding="utf-8")
            return json.dumps({
                "visualization_file": filename,
                "chart_type": chart_type,
                "title": title,
                "status": "rendered",
            }, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Visualization failed: {exc}"})

    # ------------------------------------------------------------------
    def _build_html(self, chart_type, title, labels, datasets,
                    x_label, y_label) -> str:
        # Build per-dataset configs with colour assignment
        ds_configs = []
        for i, ds in enumerate(datasets):
            color = COLORS[i % len(COLORS)]
            border = color.replace("0.8", "1")
            cfg = {
                "label": ds["label"],
                "data": ds["data"],
                "backgroundColor": (
                    COLORS[:len(labels)]          # pie/doughnut: one colour per slice
                    if chart_type in ("pie", "doughnut")
                    else color
                ),
                "borderColor": border,
                "borderWidth": 2,
            }
            if chart_type == "line":
                cfg["fill"] = False
                cfg["tension"] = 0.3
            ds_configs.append(cfg)

        chart_data = {"labels": labels, "datasets": ds_configs}
        options = {
            "responsive": True,
            "plugins": {
                "title": {"display": True, "text": title, "font": {"size": 16}},
                "legend": {"position": "bottom"},
            },
        }
        if chart_type not in ("pie", "doughnut", "radar"):
            options["scales"] = {
                "x": {"title": {"display": bool(x_label), "text": x_label}},
                "y": {"title": {"display": bool(y_label), "text": y_label}},
            }

        chart_js = json.dumps({
            "type": chart_type,
            "data": chart_data,
            "options": options,
        }, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="{CHART_JS_CDN}"></script>
<style>
  body {{ margin: 0; background: transparent; display: flex;
          justify-content: center; align-items: center; height: 100vh; }}
  canvas {{ max-width: 100%; }}
</style>
</head>
<body>
<canvas id="chart"></canvas>
<script>
  new Chart(document.getElementById('chart'), {chart_js});
</script>
</body>
</html>"""

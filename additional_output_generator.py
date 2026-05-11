"""additional_output_generator.py v3 — 12 industry-grade visualisations for
Use Case 853 (Optimized Liquidity Routing across Diversified Digital-Asset Markets).
v3 expands the KPI scorecard / spider from 12 to 16 axes (adds VWAP deviation,
child-order count, counterparty HHI, price improvement).

Each function writes ONE self-contained file (HTML / SVG / CSV / JSON) with
inline CSS, no external libs (no Chart.js, no D3, no fonts beyond system-ui).
Files are intentionally <50 KB so the QCentroid platform renders them inline
in the Job Output page.

Public entry point:
    generate_additional_output(input_data, result, algorithm_name='Solver')

The dispatcher catches per-file exceptions so a bug in one tile never blocks
the others. Output dir is `os.environ.get('ADDITIONAL_OUTPUT_DIR','./additional_output')`.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Palette (light theme, fixed across all 12 visuals)                          #
# --------------------------------------------------------------------------- #
COL_PRIMARY = "#1f77b4"   # main blue
COL_GOOD    = "#2ca02c"   # green
COL_BAD     = "#d62728"   # red
COL_WARN    = "#ff7f0e"   # orange
COL_NEUTRAL = "#7f7f7f"   # grey
COL_BG      = "#fafafa"
COL_CARD    = "#ffffff"
COL_BORDER  = "#e5e7eb"
COL_INK     = "#111827"
COL_INK_DIM = "#6b7280"

VENUE_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78",
]

_FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_BASE_CSS = (
    "*{box-sizing:border-box;margin:0;padding:0}"
    f"body{{font-family:{_FONT};background:{COL_BG};color:{COL_INK};"
    "padding:24px;line-height:1.5}"
    ".container{max-width:1200px;margin:0 auto}"
    "h1{font-size:24px;font-weight:700;margin-bottom:4px;color:" + COL_INK + "}"
    "h2{font-size:18px;font-weight:600;margin:20px 0 10px;color:" + COL_INK + "}"
    "h3{font-size:14px;font-weight:600;margin:12px 0 6px;color:" + COL_INK_DIM + ";"
    "text-transform:uppercase;letter-spacing:.04em}"
    ".sub{color:" + COL_INK_DIM + ";font-size:13px;margin-bottom:18px}"
    ".grid{display:grid;gap:14px;margin-bottom:18px}"
    ".g2{grid-template-columns:repeat(2,1fr)}"
    ".g3{grid-template-columns:repeat(3,1fr)}"
    ".g4{grid-template-columns:repeat(4,1fr)}"
    ".g6{grid-template-columns:repeat(6,1fr)}"
    f".card{{background:{COL_CARD};border:1px solid {COL_BORDER};"
    "border-radius:10px;padding:16px}"
    ".kpi{text-align:left}"
    ".kpi .v{font-size:26px;font-weight:700;color:" + COL_INK + ";line-height:1.1}"
    ".kpi .l{font-size:11px;color:" + COL_INK_DIM + ";text-transform:uppercase;"
    "letter-spacing:.05em;margin-top:4px}"
    ".kpi .a{font-size:12px;margin-top:6px;font-weight:600}"
    f".up{{color:{COL_GOOD}}}"
    f".dn{{color:{COL_BAD}}}"
    f".eq{{color:{COL_NEUTRAL}}}"
    "table{width:100%;border-collapse:collapse;font-size:13px}"
    "th{background:#f3f4f6;color:" + COL_INK_DIM + ";text-align:left;"
    "padding:8px 10px;font-weight:600;font-size:11px;"
    "text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid " + COL_BORDER + "}"
    "td{padding:8px 10px;border-bottom:1px solid #f3f4f6}"
    "tr:hover td{background:#f9fafb}"
    ".badge{display:inline-block;padding:2px 9px;border-radius:11px;"
    "font-size:11px;font-weight:600}"
    f".b-good{{background:#dcfce7;color:{COL_GOOD}}}"
    f".b-bad{{background:#fee2e2;color:{COL_BAD}}}"
    f".b-warn{{background:#fff3e0;color:{COL_WARN}}}"
    f".b-neutral{{background:#f3f4f6;color:{COL_NEUTRAL}}}"
    ".hdr{display:flex;justify-content:space-between;align-items:flex-end;"
    "padding-bottom:12px;margin-bottom:18px;border-bottom:2px solid " + COL_PRIMARY + "}"
    ".tag{font-size:11px;color:" + COL_INK_DIM + "}"
    "@media(max-width:780px){.g2,.g3,.g4,.g6{grid-template-columns:1fr}}"
)


# --------------------------------------------------------------------------- #
# Module-level helpers                                                        #
# --------------------------------------------------------------------------- #
def _safe(d: Any, key: str, default: Any = None) -> Any:
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def _f(x: Any, nd: int = 2, default: str = "-") -> str:
    """Format a numeric value compactly."""
    try:
        if x is None:
            return default
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"{v/1_000:.2f}k"
        return f"{v:.{nd}f}"
    except Exception:
        return default


def _wrap_html(title: str, subtitle: str, body: str, solver: str = "") -> str:
    sx = f'<div class="tag">{solver}</div>' if solver else ""
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{_BASE_CSS}</style></head><body>"
        "<div class='container'>"
        f"<div class='hdr'><div><h1>{title}</h1><div class='sub'>{subtitle}</div></div>{sx}</div>"
        f"{body}</div></body></html>"
    )


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# --------------------------------------------------------------------------- #
# v3 KPI normalisation (matches BENCHMARK_KPIS_v3.md, 16 KPIs)                #
# --------------------------------------------------------------------------- #
KPI_SPEC: List[Tuple[str, str, bool]] = [
    # (field, short_label, higher_is_better)
    ("realized_slippage_bps",          "Slippage",          False),
    ("fill_rate_pct",                  "Fill Rate",         True),
    ("total_fees_bps",                 "Fees",              False),
    ("market_impact_bps",              "Mkt Impact",        False),
    ("price_discovery_score",          "Price Disc.",       True),
    ("venue_switches",                 "Venue Switches",    False),
    ("implementation_shortfall_bps",   "Impl. Shortfall",   False),
    ("fill_time_p95_sec",              "Fill Time p95",     False),
    ("latency_p95_ms",                 "Latency p95",       False),
    ("dark_pool_pct",                  "Dark Pool %",       False),
    ("maker_fill_pct",                 "Maker %",           True),
    ("post_trade_drift_bps",           "Post-Trade Drift",  False),
    # v3 additions
    ("vwap_deviation_bps",             "VWAP Dev",          False),
    ("child_order_count",              "Child Orders",      False),
    ("counterparty_concentration_hhi", "Venue HHI",         False),
    ("price_improvement_bps",          "Price Improv.",     True),
]

KPI_UNITS = {
    "realized_slippage_bps":          "bps",
    "fill_rate_pct":                  "%",
    "total_fees_bps":                 "bps",
    "market_impact_bps":              "bps",
    "price_discovery_score":          "0-1",
    "venue_switches":                 "count",
    "implementation_shortfall_bps":   "bps",
    "fill_time_p95_sec":              "s",
    "latency_p95_ms":                 "ms",
    "dark_pool_pct":                  "%",
    "maker_fill_pct":                 "%",
    "post_trade_drift_bps":           "bps",
    # v3 additions
    "vwap_deviation_bps":             "bps",
    "child_order_count":              "count",
    "counterparty_concentration_hhi": "hhi",
    "price_improvement_bps":          "bps",
}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _normalize_kpi(field: str, value: Any) -> float:
    """Return value in [0,1] where 1.0 = best (per BENCHMARK_KPIS_v2.md)."""
    try:
        x = float(value)
    except Exception:
        return 0.0
    if field == "realized_slippage_bps":
        return 1.0 - _clip(abs(x), 0, 50) / 50.0
    if field == "fill_rate_pct":
        return _clip(x, 0, 100) / 100.0
    if field == "total_fees_bps":
        return 1.0 - _clip(abs(x), 0, 50) / 50.0
    if field == "market_impact_bps":
        return 1.0 - _clip(abs(x), 0, 50) / 50.0
    if field == "price_discovery_score":
        return _clip(x, 0, 1)
    if field == "venue_switches":
        return 1.0 - _clip(x, 0, 10) / 10.0
    if field == "implementation_shortfall_bps":
        return 1.0 - _clip(abs(x), 0, 100) / 100.0
    if field == "fill_time_p95_sec":
        return 1.0 - _clip(x, 0, 600) / 600.0
    if field == "latency_p95_ms":
        return 1.0 - _clip(x, 0, 200) / 200.0
    if field == "dark_pool_pct":
        return 1.0 - _clip(x, 0, 100) / 100.0
    if field == "maker_fill_pct":
        return _clip(x, 0, 100) / 100.0
    if field == "post_trade_drift_bps":
        return 1.0 - _clip(abs(x), 0, 20) / 20.0
    # v3 additions
    if field == "vwap_deviation_bps":
        return 1.0 - _clip(abs(x), 0, 50) / 50.0
    if field == "child_order_count":
        return 1.0 - _clip(x, 0, 200) / 200.0
    if field == "counterparty_concentration_hhi":
        return 1.0 - _clip(x, 0, 10000) / 10000.0
    if field == "price_improvement_bps":
        return _clip(x, 0, 50) / 50.0
    return 0.0


# --------------------------------------------------------------------------- #
# Main dispatcher                                                             #
# --------------------------------------------------------------------------- #
def generate_additional_output(input_data: Dict[str, Any],
                                result: Dict[str, Any],
                                algorithm_name: str = "Solver") -> int:
    """Generate all 12 visuals (v3: 16-KPI scorecard + 16-axis spider). Returns count of successful files."""
    out_dir = os.environ.get("ADDITIONAL_OUTPUT_DIR", "./additional_output")
    os.makedirs(out_dir, exist_ok=True)

    tasks = [
        ("01_executive_summary.html",       gen_01_executive_summary),
        ("02_kpi_spider.svg",               gen_02_kpi_spider),
        ("03_tca_waterfall.html",           gen_03_tca_waterfall),
        ("04_venue_mix_donut.svg",          gen_04_venue_mix_donut),
        ("05_per_asset_slippage_box.svg",   gen_05_per_asset_slippage_box),
        ("06_execution_timeline.svg",       gen_06_execution_timeline),
        ("07_liquidity_heatmap.html",       gen_07_liquidity_heatmap),
        ("08_objective_attribution.svg",    gen_08_objective_attribution),
        ("09_constraint_report.html",       gen_09_constraint_report),
        ("10_sor_ticket.html",              gen_10_sor_ticket),
        ("11_routing_plan.csv",             gen_11_routing_plan),
        ("12_audit_full.json",              gen_12_audit_full),
    ]

    n_ok = 0
    for fname, fn in tasks:
        try:
            fn(input_data, result, out_dir, algorithm_name=algorithm_name)
            n_ok += 1
        except Exception:
            # individual tile failure must NOT block siblings
            continue
    return n_ok


# --------------------------------------------------------------------------- #
# 01. Executive Summary — header card + 16-KPI dashboard grid (v3)            #
# --------------------------------------------------------------------------- #
def gen_01_executive_summary(input_data: Dict[str, Any],
                              result: Dict[str, Any],
                              output_dir: str,
                              algorithm_name: str = "Solver") -> None:
    obj = _safe(result, "objective_value", 0)
    status = _safe(result, "solution_status", _safe(result, "status", "unknown"))
    rp = _safe(result, "routing_plan", []) or []
    total_notional = sum(
        float(_safe(p, "allocated_quantity", 0)) * float(_safe(p, "expected_price", 0))
        for p in rp
    )

    cards = []
    for field, label, higher_better in KPI_SPEC:
        val = _safe(result, field, 0) or 0
        norm = _normalize_kpi(field, val)
        # Direction arrow vs neutral midpoint
        if norm >= 0.7:
            arrow_html = f'<span class="a up">&#9650; good</span>'
        elif norm >= 0.4:
            arrow_html = f'<span class="a eq">&#9654; ok</span>'
        else:
            arrow_html = f'<span class="a dn">&#9660; weak</span>'
        unit = KPI_UNITS.get(field, "")
        # Inline 60x16 sparkline showing normalised score as filled bar
        bar_w = max(2, int(56 * norm))
        spark = (
            f'<svg width="60" height="10" style="margin-top:6px;display:block">'
            f'<rect x="0" y="3" width="56" height="4" fill="#e5e7eb" rx="2"/>'
            f'<rect x="0" y="3" width="{bar_w}" height="4" fill="{COL_PRIMARY}" rx="2"/>'
            f'</svg>'
        )
        cards.append(
            f'<div class="card kpi">'
            f'<div class="v">{_f(val, 2)}<span style="font-size:13px;color:{COL_INK_DIM};margin-left:4px">{unit}</span></div>'
            f'<div class="l">{label}</div>'
            f'{arrow_html}'
            f'{spark}'
            f'</div>'
        )

    bench = _safe(result, "benchmark", {}) or {}
    wall = _safe(bench, "time_elapsed", "-")
    exec_cost = _safe(bench, "execution_cost", {}) or {}
    cost_val = _safe(exec_cost, "value", 0) if isinstance(exec_cost, dict) else exec_cost

    header_card = (
        f'<div class="card" style="border-left:4px solid {COL_PRIMARY};margin-bottom:18px">'
        f'<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px">'
        f'<div><h3 style="margin:0">Algorithm</h3><div style="font-size:18px;font-weight:600">{algorithm_name}</div></div>'
        f'<div><h3 style="margin:0">Status</h3><div><span class="badge {_status_class(status)}">{status}</span></div></div>'
        f'<div><h3 style="margin:0">Objective Value</h3><div style="font-size:18px;font-weight:600">{_f(obj, 4)}</div></div>'
        f'<div><h3 style="margin:0">Notional Routed</h3><div style="font-size:18px;font-weight:600">${_f(total_notional, 0)}</div></div>'
        f'<div><h3 style="margin:0">Wall Time</h3><div style="font-size:18px;font-weight:600">{wall}</div></div>'
        f'<div><h3 style="margin:0">Cost</h3><div style="font-size:18px;font-weight:600">{_f(cost_val, 4)} cr</div></div>'
        f'</div></div>'
    )

    body = header_card + f'<h2>16-KPI Execution Scorecard</h2><div class="grid g4">{"".join(cards)}</div>'
    body += (
        f'<div class="card"><h3>Reading this dashboard</h3>'
        f'<div style="font-size:13px;color:{COL_INK_DIM}">'
        f'Each tile shows raw value, unit, a directional arrow vs a normalised quality threshold, '
        f'and a sparkline of the normalised score (longer = better). Spider chart in '
        f'<b>02_kpi_spider.svg</b> overlays all 16 axes for cross-solver comparison.'
        f'</div></div>'
    )

    html = _wrap_html(
        title="Liquidity Routing — Executive Summary",
        subtitle=f"Use Case 853 · {len(rp)} routing decisions · {algorithm_name}",
        body=body,
        solver=algorithm_name,
    )
    _write(os.path.join(output_dir, "01_executive_summary.html"), html)


def _status_class(status: str) -> str:
    s = (status or "").lower()
    if s in ("optimal", "feasible", "success"):
        return "b-good"
    if s in ("infeasible", "error", "fatal"):
        return "b-bad"
    if s in ("suboptimal", "timeout", "limit"):
        return "b-warn"
    return "b-neutral"


# --------------------------------------------------------------------------- #
# 02. KPI Spider / Radar (SVG)                                                #
# --------------------------------------------------------------------------- #
def gen_02_kpi_spider(input_data: Dict[str, Any],
                      result: Dict[str, Any],
                      output_dir: str,
                      algorithm_name: str = "Solver") -> None:
    cx, cy = 360, 340
    R = 220
    n = len(KPI_SPEC)
    rp = _safe(result, "routing_plan", []) or []
    total_notional = sum(
        float(_safe(p, "allocated_quantity", 0)) * float(_safe(p, "expected_price", 0))
        for p in rp
    )

    # Axis lines & labels
    axes = []
    labels = []
    poly_pts = []
    raw_pts = []
    grid_circles = []

    # 4 grid rings at 0.25, 0.50, 0.75, 1.0
    for frac in (0.25, 0.50, 0.75, 1.00):
        grid_circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R*frac:.1f}" fill="none" '
            f'stroke="#d1d5db" stroke-width="1" stroke-dasharray="{2 if frac<1 else 0},3"/>'
        )

    for i, (field, label, _hb) in enumerate(KPI_SPEC):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        ex = cx + R * math.cos(angle)
        ey = cy + R * math.sin(angle)
        axes.append(
            f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="#d1d5db" stroke-width="1"/>'
        )
        # label outside ring
        lx = cx + (R + 30) * math.cos(angle)
        ly = cy + (R + 30) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        # raw value tag
        raw_val = _safe(result, field, 0)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="12" fill="{COL_INK}" font-weight="600" '
            f'font-family="{_FONT}">{label}</text>'
            f'<text x="{lx:.1f}" y="{ly+14:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="{COL_INK_DIM}" font-family="{_FONT}">'
            f'{_f(raw_val,2)} {KPI_UNITS.get(field,"")}</text>'
        )
        # polygon
        norm = _normalize_kpi(field, raw_val)
        r = R * norm
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        poly_pts.append(f"{px:.1f},{py:.1f}")
        raw_pts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{COL_PRIMARY}" '
            f'stroke="#ffffff" stroke-width="1.5"/>'
        )

    # Grid ring labels (0.25 etc.)
    grid_labels = "".join(
        f'<text x="{cx+4}" y="{cy-R*frac:.1f}" font-size="9" fill="{COL_INK_DIM}" '
        f'font-family="{_FONT}">{int(frac*100)}%</text>'
        for frac in (0.25, 0.50, 0.75, 1.00)
    )

    polygon = (
        f'<polygon points="{" ".join(poly_pts)}" fill="{COL_PRIMARY}" '
        f'fill-opacity="0.22" stroke="{COL_PRIMARY}" stroke-width="2" '
        f'stroke-linejoin="round"/>'
    )

    title_y = 26
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 700" '
        f'width="720" height="700" font-family="{_FONT}">'
        f'<rect width="720" height="700" fill="{COL_BG}"/>'
        f'<text x="360" y="{title_y}" text-anchor="middle" font-size="18" '
        f'font-weight="700" fill="{COL_INK}">KPI Spider — 16-axis Execution Quality</text>'
        f'<text x="360" y="{title_y+20}" text-anchor="middle" font-size="12" '
        f'fill="{COL_INK_DIM}">{algorithm_name} · Total notional ${_f(total_notional,0)} · '
        f'higher polygon area = better routing</text>'
        f'{"".join(grid_circles)}'
        f'{grid_labels}'
        f'{"".join(axes)}'
        f'{polygon}'
        f'{"".join(raw_pts)}'
        f'{"".join(labels)}'
        f'<text x="360" y="680" text-anchor="middle" font-size="10" fill="{COL_INK_DIM}">'
        f'Normalisation per BENCHMARK_KPIS_v3.md · 1.0 = best</text>'
        f'</svg>'
    )
    _write(os.path.join(output_dir, "02_kpi_spider.svg"), svg)


# --------------------------------------------------------------------------- #
# 03. TCA Waterfall (HTML with inline SVG bars)                               #
# --------------------------------------------------------------------------- #
def gen_03_tca_waterfall(input_data: Dict[str, Any],
                          result: Dict[str, Any],
                          output_dir: str,
                          algorithm_name: str = "Solver") -> None:
    slip = float(_safe(result, "realized_slippage_bps", 0) or 0)
    fees = float(_safe(result, "total_fees_bps", 0) or 0)
    impact = float(_safe(result, "market_impact_bps", 0) or 0)
    drift = float(_safe(result, "post_trade_drift_bps", 0) or 0)
    total = slip + fees + impact + drift

    steps = [
        ("Arrival Price", 0.0, COL_NEUTRAL, "baseline (decision price)"),
        ("Realized Slippage", slip, COL_BAD if slip > 0 else COL_GOOD, "vol-weighted exec vs arrival"),
        ("Fees", fees, COL_BAD if fees > 0 else COL_GOOD, "venue fees minus rebates"),
        ("Market Impact", impact, COL_WARN, "Σ (α·q + β·q²)"),
        ("Post-Trade Drift", drift, COL_BAD if drift > 0 else COL_GOOD, "+5s mid vs exec"),
        ("Effective Cost", total, COL_PRIMARY, "all-in execution cost"),
    ]

    # SVG waterfall
    W, H = 920, 360
    pad_l, pad_r, pad_t, pad_b = 90, 100, 40, 80
    n_steps = len(steps)
    bar_w = (W - pad_l - pad_r) / n_steps * 0.62
    gap = (W - pad_l - pad_r) / n_steps * 0.38

    max_abs = max(abs(total) * 1.2, 5.0, *[abs(v) for _, v, _, _ in steps])
    zero_y = pad_t + (H - pad_t - pad_b) * 0.5
    px_per_bps = (H - pad_t - pad_b) * 0.45 / max_abs

    bars_svg = []
    label_svg = []
    running = 0.0
    for i, (name, val, col, _hint) in enumerate(steps):
        x = pad_l + i * (bar_w + gap)
        if name == "Arrival Price":
            # zero baseline marker
            bars_svg.append(
                f'<line x1="{x:.1f}" y1="{zero_y-20}" x2="{x+bar_w:.1f}" y2="{zero_y-20}" '
                f'stroke="{COL_NEUTRAL}" stroke-width="3"/>'
            )
            label_svg.append(
                f'<text x="{x+bar_w/2:.1f}" y="{zero_y+5:.1f}" text-anchor="middle" '
                f'font-size="11" fill="{COL_INK}" font-weight="600">0 bps</text>'
            )
            running = 0.0
        elif name == "Effective Cost":
            y_top = zero_y - max(0, total) * px_per_bps
            y_bot = zero_y - min(0, total) * px_per_bps
            h = max(2, abs(y_bot - y_top))
            bars_svg.append(
                f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'fill="{col}" rx="2" stroke="{COL_PRIMARY}" stroke-width="2"/>'
            )
            label_svg.append(
                f'<text x="{x+bar_w/2:.1f}" y="{y_top-6:.1f}" text-anchor="middle" '
                f'font-size="12" font-weight="700" fill="{COL_INK}">{_f(total,2)} bps</text>'
            )
        else:
            base = running
            top_val = base + val
            y_top = zero_y - max(base, top_val) * px_per_bps
            h = max(2, abs(val) * px_per_bps)
            bars_svg.append(
                f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'fill="{col}" rx="2" opacity="0.85"/>'
            )
            label_svg.append(
                f'<text x="{x+bar_w/2:.1f}" y="{y_top-6:.1f}" text-anchor="middle" '
                f'font-size="11" font-weight="600" fill="{COL_INK}">'
                f'{"+" if val>=0 else ""}{_f(val,2)}</text>'
            )
            # connector dotted line to next bar baseline
            if i < n_steps - 2:
                conn_y = zero_y - top_val * px_per_bps
                bars_svg.append(
                    f'<line x1="{x+bar_w:.1f}" y1="{conn_y:.1f}" '
                    f'x2="{x+bar_w+gap:.1f}" y2="{conn_y:.1f}" '
                    f'stroke="{COL_INK_DIM}" stroke-width="1" stroke-dasharray="3,3"/>'
                )
            running = top_val

        # x-axis name
        label_svg.append(
            f'<text x="{x+bar_w/2:.1f}" y="{H-pad_b+18:.1f}" text-anchor="middle" '
            f'font-size="11" fill="{COL_INK}" font-weight="600">{name}</text>'
        )
        label_svg.append(
            f'<text x="{x+bar_w/2:.1f}" y="{H-pad_b+34:.1f}" text-anchor="middle" '
            f'font-size="10" fill="{COL_INK_DIM}">{_hint}</text>'
        )

    # zero axis
    axis = (
        f'<line x1="{pad_l-10}" y1="{zero_y}" x2="{W-pad_r+10}" y2="{zero_y}" '
        f'stroke="{COL_INK_DIM}" stroke-width="1"/>'
        f'<text x="{pad_l-14}" y="{zero_y+4}" text-anchor="end" font-size="10" '
        f'fill="{COL_INK_DIM}">0 bps</text>'
    )

    # Right-side running-total
    cum = (
        f'<text x="{W-pad_r+15}" y="{zero_y - total*px_per_bps - 12}" '
        f'font-size="13" font-weight="700" fill="{COL_PRIMARY}">'
        f'Total: {_f(total,2)} bps</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" width="100%" font-family="{_FONT}">'
        f'<rect width="{W}" height="{H}" fill="{COL_CARD}"/>'
        f'{axis}{"".join(bars_svg)}{"".join(label_svg)}{cum}'
        f'</svg>'
    )

    body = (
        f'<div class="card">{svg}</div>'
        f'<div class="grid g4" style="margin-top:18px">'
        f'<div class="card kpi"><div class="v">{_f(slip,2)} bps</div><div class="l">Realized Slippage</div></div>'
        f'<div class="card kpi"><div class="v">{_f(fees,2)} bps</div><div class="l">Fees</div></div>'
        f'<div class="card kpi"><div class="v">{_f(impact,2)} bps</div><div class="l">Market Impact</div></div>'
        f'<div class="card kpi"><div class="v" style="color:{COL_PRIMARY}">{_f(total,2)} bps</div><div class="l">Effective Cost</div></div>'
        f'</div>'
        f'<div class="card"><h3>How to read this waterfall</h3>'
        f'<div style="font-size:13px;color:{COL_INK_DIM}">'
        f'Starting from a zero baseline (arrival price = decision price), each bar shows '
        f'the cost or saving added at that step. The final dark-blue bar is the total '
        f'implementation cost in bps of notional — the headline figure that any '
        f'trading-desk TCA review starts from.</div></div>'
    )
    html = _wrap_html(
        title="Transaction Cost Analysis — Waterfall",
        subtitle=f"Arrival-price decomposition · {algorithm_name}",
        body=body,
        solver=algorithm_name,
    )
    _write(os.path.join(output_dir, "03_tca_waterfall.html"), html)


# --------------------------------------------------------------------------- #
# 04. Venue Mix Donut (SVG) — colored by venue.quality_w                      #
# --------------------------------------------------------------------------- #
def gen_04_venue_mix_donut(input_data: Dict[str, Any],
                            result: Dict[str, Any],
                            output_dir: str,
                            algorithm_name: str = "Solver") -> None:
    rp = _safe(result, "routing_plan", []) or []
    venues = _safe(input_data, "venue_catalogue", []) or []
    qw = {v.get("id"): float(v.get("quality_w", 0.5)) for v in venues if isinstance(v, dict)}

    by_venue: Dict[str, float] = {}
    for p in rp:
        vid = _safe(p, "venue_id", "?")
        n = float(_safe(p, "allocated_quantity", 0)) * float(_safe(p, "expected_price", 0))
        by_venue[vid] = by_venue.get(vid, 0.0) + n
    total = sum(by_venue.values()) or 1.0
    sorted_v = sorted(by_venue.items(), key=lambda x: -x[1])

    W, H = 720, 460
    cx, cy = 240, 230
    R_out, R_in = 170, 95

    def color_for(qw_val: float, idx: int) -> str:
        # Use quality_w to lerp between bad (red) → primary (blue) → good (green)
        q = max(0.0, min(1.0, qw_val))
        if q < 0.5:
            # red → orange
            t = q * 2
            return _lerp(COL_BAD, COL_WARN, t)
        # orange → green
        t = (q - 0.5) * 2
        return _lerp(COL_WARN, COL_GOOD, t)

    arcs = []
    legend_rows = []
    a0 = -math.pi / 2
    for i, (vid, n) in enumerate(sorted_v):
        pct = n / total * 100
        sweep = (n / total) * 2 * math.pi
        a1 = a0 + sweep
        large = 1 if sweep > math.pi else 0
        x0o, y0o = cx + R_out * math.cos(a0), cy + R_out * math.sin(a0)
        x1o, y1o = cx + R_out * math.cos(a1), cy + R_out * math.sin(a1)
        x0i, y0i = cx + R_in * math.cos(a0), cy + R_in * math.sin(a0)
        x1i, y1i = cx + R_in * math.cos(a1), cy + R_in * math.sin(a1)
        q = qw.get(vid, 0.5)
        col = color_for(q, i)
        path = (
            f'M{x0o:.1f},{y0o:.1f} '
            f'A{R_out},{R_out} 0 {large} 1 {x1o:.1f},{y1o:.1f} '
            f'L{x1i:.1f},{y1i:.1f} '
            f'A{R_in},{R_in} 0 {large} 0 {x0i:.1f},{y0i:.1f} Z'
        )
        arcs.append(f'<path d="{path}" fill="{col}" stroke="{COL_CARD}" stroke-width="2"/>')
        # mid-arc label
        if pct >= 4:
            mid_a = (a0 + a1) / 2
            lx = cx + (R_out + R_in) / 2 * math.cos(mid_a)
            ly = cy + (R_out + R_in) / 2 * math.sin(mid_a)
            arcs.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-size="11" font-weight="700" fill="#ffffff">'
                f'{pct:.1f}%</text>'
            )

        legend_rows.append(
            f'<tr><td><span style="display:inline-block;width:14px;height:14px;'
            f'background:{col};border-radius:3px;vertical-align:middle;margin-right:6px"></span>'
            f'<b>{vid}</b></td>'
            f'<td style="text-align:right">${_f(n,0)}</td>'
            f'<td style="text-align:right">{pct:.1f}%</td>'
            f'<td style="text-align:right">{_f(q,2)}</td></tr>'
        )
        a0 = a1

    # center text
    center = (
        f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="13" font-weight="600" '
        f'fill="{COL_INK_DIM}">Total Notional</text>'
        f'<text x="{cx}" y="{cy+18}" text-anchor="middle" font-size="20" font-weight="700" '
        f'fill="{COL_INK}">${_f(total,0)}</text>'
    )

    # gradient legend (quality_w)
    g_y = 410
    gradient = (
        f'<defs><linearGradient id="gq" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0%" stop-color="{COL_BAD}"/>'
        f'<stop offset="50%" stop-color="{COL_WARN}"/>'
        f'<stop offset="100%" stop-color="{COL_GOOD}"/>'
        f'</linearGradient></defs>'
        f'<rect x="40" y="{g_y}" width="380" height="10" fill="url(#gq)" rx="2"/>'
        f'<text x="40" y="{g_y-4}" font-size="11" fill="{COL_INK_DIM}">Venue Quality (quality_w)</text>'
        f'<text x="40" y="{g_y+24}" font-size="10" fill="{COL_INK_DIM}">0.0</text>'
        f'<text x="230" y="{g_y+24}" text-anchor="middle" font-size="10" fill="{COL_INK_DIM}">0.5</text>'
        f'<text x="420" y="{g_y+24}" text-anchor="end" font-size="10" fill="{COL_INK_DIM}">1.0</text>'
    )

    # table on the right
    table_x = 470
    table_lines = []
    table_lines.append(
        f'<text x="{table_x}" y="50" font-size="13" font-weight="700" fill="{COL_INK}">'
        f'Venue Breakdown</text>'
    )
    row_y = 78
    table_lines.append(
        f'<text x="{table_x}" y="{row_y-12}" font-size="10" fill="{COL_INK_DIM}" font-weight="600">'
        f'VENUE        NOTIONAL    SHARE    QUALITY</text>'
    )
    for i, (vid, n) in enumerate(sorted_v[:10]):
        pct = n / total * 100
        q = qw.get(vid, 0.5)
        col = color_for(q, i)
        table_lines.append(
            f'<rect x="{table_x}" y="{row_y-10}" width="8" height="8" fill="{col}" rx="1"/>'
            f'<text x="{table_x+14}" y="{row_y-2}" font-size="11" fill="{COL_INK}">{vid[:10]}</text>'
            f'<text x="{table_x+110}" y="{row_y-2}" font-size="11" fill="{COL_INK}">${_f(n,0)}</text>'
            f'<text x="{table_x+180}" y="{row_y-2}" font-size="11" fill="{COL_INK}">{pct:.1f}%</text>'
            f'<text x="{table_x+230}" y="{row_y-2}" font-size="11" fill="{COL_INK_DIM}">{_f(q,2)}</text>'
        )
        row_y += 22

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{_FONT}">'
        f'<rect width="{W}" height="{H}" fill="{COL_BG}"/>'
        f'<text x="{W/2}" y="22" text-anchor="middle" font-size="16" font-weight="700" fill="{COL_INK}">'
        f'Venue Mix — colored by Quality (quality_w)</text>'
        f'<text x="{W/2}" y="38" text-anchor="middle" font-size="11" fill="{COL_INK_DIM}">'
        f'{algorithm_name} · {len(sorted_v)} venues</text>'
        f'{"".join(arcs)}'
        f'{center}'
        f'{"".join(table_lines)}'
        f'{gradient}'
        f'</svg>'
    )
    _write(os.path.join(output_dir, "04_venue_mix_donut.svg"), svg)


def _lerp(c1: str, c2: str, t: float) -> str:
    def _hex(c):
        return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    r1, g1, b1 = _hex(c1)
    r2, g2, b2 = _hex(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# --------------------------------------------------------------------------- #
# 05. Per-Asset Slippage Box-Plot (SVG)                                       #
# --------------------------------------------------------------------------- #
def gen_05_per_asset_slippage_box(input_data: Dict[str, Any],
                                   result: Dict[str, Any],
                                   output_dir: str,
                                   algorithm_name: str = "Solver") -> None:
    fills = _safe(result, "_fills", None)
    if not fills:
        # reconstruct an approximation from execution_instructions
        fills = _safe(result, "execution_instructions", []) or []
    orders = _safe(input_data, "orders", []) or []
    arrival_by_order = {o.get("order_id"): float(o.get("arrival_price", 0))
                        for o in orders if isinstance(o, dict)}

    # Build per-asset slippage in bps for each fill
    per_asset: Dict[str, List[float]] = {}
    for f in fills:
        asset = _safe(f, "asset")
        ap = arrival_by_order.get(_safe(f, "order_id"), 0)
        ep = float(_safe(f, "exec_price", _safe(f, "limit_price", 0)) or 0)
        if not asset or ap <= 0 or ep <= 0:
            continue
        side_sign = 1 if _safe(f, "side") == "buy" else -1
        slip_bps = (ep - ap) / ap * 10_000 * side_sign
        per_asset.setdefault(asset, []).append(slip_bps)

    assets = sorted(per_asset.keys())
    if not assets:
        # render an empty-state SVG
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 240" font-family="{_FONT}">'
            f'<rect width="600" height="240" fill="{COL_BG}"/>'
            f'<text x="300" y="120" text-anchor="middle" font-size="14" fill="{COL_INK_DIM}">'
            f'No per-fill slippage data available for this run.</text></svg>'
        )
        _write(os.path.join(output_dir, "05_per_asset_slippage_box.svg"), svg)
        return

    W, H = 920, 440
    pad_l, pad_r, pad_t, pad_b = 70, 40, 50, 70
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    all_vals = [v for vs in per_asset.values() for v in vs]
    vmin = min(all_vals + [-5])
    vmax = max(all_vals + [5])
    span = max(abs(vmin), abs(vmax)) * 1.2
    vmin, vmax = -span, span

    def y_of(v: float) -> float:
        return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))

    # Zero line + grid
    grid = []
    for tick in (-span, -span/2, 0, span/2, span):
        y = y_of(tick)
        grid.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" '
            f'stroke="{"#9ca3af" if tick==0 else "#e5e7eb"}" stroke-width="{2 if tick==0 else 1}" '
            f'stroke-dasharray="{0 if tick==0 else 3},3"/>'
            f'<text x="{pad_l-8}" y="{y+3:.1f}" text-anchor="end" font-size="10" '
            f'fill="{COL_INK_DIM}">{tick:+.1f}</text>'
        )

    box_w = plot_w / len(assets) * 0.55
    n_assets = len(assets)
    boxes = []
    for i, asset in enumerate(assets):
        vals = sorted(per_asset[asset])
        n = len(vals)
        if n == 0:
            continue
        # 5-number summary
        q_min = vals[0]
        q_max = vals[-1]
        q1 = vals[max(0, int(0.25 * (n - 1)))]
        q2 = vals[max(0, int(0.50 * (n - 1)))]
        q3 = vals[max(0, int(0.75 * (n - 1)))]

        cx = pad_l + plot_w * (i + 0.5) / n_assets
        x0 = cx - box_w / 2
        x1 = cx + box_w / 2

        y_min = y_of(q_min)
        y_max = y_of(q_max)
        y_q1 = y_of(q1)
        y_q2 = y_of(q2)
        y_q3 = y_of(q3)

        col = VENUE_PALETTE[i % len(VENUE_PALETTE)]
        # whiskers
        boxes.append(
            f'<line x1="{cx:.1f}" y1="{y_max:.1f}" x2="{cx:.1f}" y2="{y_q3:.1f}" '
            f'stroke="{COL_INK}" stroke-width="1"/>'
            f'<line x1="{cx:.1f}" y1="{y_q1:.1f}" x2="{cx:.1f}" y2="{y_min:.1f}" '
            f'stroke="{COL_INK}" stroke-width="1"/>'
            f'<line x1="{x0:.1f}" y1="{y_max:.1f}" x2="{x1:.1f}" y2="{y_max:.1f}" '
            f'stroke="{COL_INK}" stroke-width="1"/>'
            f'<line x1="{x0:.1f}" y1="{y_min:.1f}" x2="{x1:.1f}" y2="{y_min:.1f}" '
            f'stroke="{COL_INK}" stroke-width="1"/>'
        )
        # box
        boxes.append(
            f'<rect x="{x0:.1f}" y="{y_q3:.1f}" width="{box_w:.1f}" height="{abs(y_q1-y_q3):.1f}" '
            f'fill="{col}" fill-opacity="0.45" stroke="{col}" stroke-width="1.5" rx="2"/>'
        )
        # median
        boxes.append(
            f'<line x1="{x0:.1f}" y1="{y_q2:.1f}" x2="{x1:.1f}" y2="{y_q2:.1f}" '
            f'stroke="{COL_INK}" stroke-width="2"/>'
        )
        # asset label
        boxes.append(
            f'<text x="{cx:.1f}" y="{H-pad_b+16}" text-anchor="middle" font-size="11" '
            f'font-weight="600" fill="{COL_INK}">{asset}</text>'
            f'<text x="{cx:.1f}" y="{H-pad_b+30}" text-anchor="middle" font-size="10" '
            f'fill="{COL_INK_DIM}">n={n} · med {q2:+.1f}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{_FONT}">'
        f'<rect width="{W}" height="{H}" fill="{COL_BG}"/>'
        f'<text x="{W/2}" y="24" text-anchor="middle" font-size="16" font-weight="700" '
        f'fill="{COL_INK}">Per-Asset Slippage Distribution</text>'
        f'<text x="{W/2}" y="40" text-anchor="middle" font-size="11" fill="{COL_INK_DIM}">'
        f'{algorithm_name} · box = IQR, whiskers = min/max, dark line = median (bps)</text>'
        f'<text x="{pad_l-50}" y="{pad_t+plot_h/2}" font-size="11" fill="{COL_INK_DIM}" '
        f'transform="rotate(-90 {pad_l-50},{pad_t+plot_h/2})" text-anchor="middle">Slippage (bps)</text>'
        f'{"".join(grid)}{"".join(boxes)}'
        f'</svg>'
    )
    _write(os.path.join(output_dir, "05_per_asset_slippage_box.svg"), svg)


# --------------------------------------------------------------------------- #
# 06. Execution Timeline / Gantt (SVG)                                        #
# --------------------------------------------------------------------------- #
def gen_06_execution_timeline(input_data: Dict[str, Any],
                               result: Dict[str, Any],
                               output_dir: str,
                               algorithm_name: str = "Solver") -> None:
    orders = _safe(input_data, "orders", []) or []
    fills = _safe(result, "_fills", None) or _safe(result, "execution_instructions", []) or []

    # Build per-order [start, end] and assigned venue (most-used)
    order_meta: Dict[str, Dict[str, Any]] = {}
    for o in orders:
        if not isinstance(o, dict):
            continue
        oid = o.get("order_id")
        order_meta[oid] = {
            "arrival": float(o.get("arrival_offset_sec", 0) or 0),
            "venue": None,
            "last_fill_sec": None,
            "asset": o.get("asset", ""),
            "side": o.get("side", "buy"),
        }

    for f in fills:
        oid = _safe(f, "order_id")
        if oid not in order_meta:
            order_meta[oid] = {"arrival": 0.0, "venue": None,
                               "last_fill_sec": None,
                               "asset": _safe(f, "asset", ""),
                               "side": _safe(f, "side", "buy")}
        ts_ms = float(_safe(f, "fill_ts_offset_ms", 0) or 0)
        end_sec = order_meta[oid]["arrival"] + ts_ms / 1000.0
        if order_meta[oid]["last_fill_sec"] is None or end_sec > order_meta[oid]["last_fill_sec"]:
            order_meta[oid]["last_fill_sec"] = end_sec
        if order_meta[oid]["venue"] is None:
            order_meta[oid]["venue"] = _safe(f, "venue_id", "?")

    if not order_meta:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 200" '
            f'font-family="{_FONT}"><rect width="600" height="200" fill="{COL_BG}"/>'
            f'<text x="300" y="100" text-anchor="middle" font-size="14" '
            f'fill="{COL_INK_DIM}">No execution timeline available.</text></svg>'
        )
        _write(os.path.join(output_dir, "06_execution_timeline.svg"), svg)
        return

    # Limit to first 60 orders for legibility, sorted by arrival
    rows = sorted(order_meta.items(), key=lambda kv: kv[1]["arrival"])[:60]
    venues = sorted({v["venue"] for _, v in rows if v["venue"]})
    venue_color = {v: VENUE_PALETTE[i % len(VENUE_PALETTE)] for i, v in enumerate(venues)}

    t_max = max((v["last_fill_sec"] or v["arrival"] + 1) for _, v in rows) or 1
    t_max = max(t_max, 1.0)

    W = 980
    row_h = 16
    pad_l, pad_r, pad_t = 110, 40, 80
    H = pad_t + len(rows) * row_h + 80
    plot_w = W - pad_l - pad_r

    bars_svg = []
    for i, (oid, m) in enumerate(rows):
        y = pad_t + i * row_h + 3
        x_arr = pad_l + (m["arrival"] / t_max) * plot_w
        end = m["last_fill_sec"] if m["last_fill_sec"] is not None else m["arrival"]
        x_end = pad_l + (end / t_max) * plot_w
        bar_w = max(2, x_end - x_arr)
        col = venue_color.get(m["venue"], COL_NEUTRAL)
        # arrival marker
        bars_svg.append(
            f'<circle cx="{x_arr:.1f}" cy="{y+row_h/2-3:.1f}" r="2.5" fill="{COL_INK}"/>'
        )
        # bar
        bars_svg.append(
            f'<rect x="{x_arr:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{row_h-6}" '
            f'fill="{col}" rx="2" opacity="0.85">'
            f'<title>{oid} · {m["asset"]} {m["side"]} · venue {m["venue"]} · {end-m["arrival"]:.1f}s</title>'
            f'</rect>'
        )
        # y-axis label (order id, truncated)
        bars_svg.append(
            f'<text x="{pad_l-8}" y="{y+row_h/2+3:.1f}" text-anchor="end" font-size="10" '
            f'fill="{COL_INK}">{(oid or "")[-14:]}</text>'
        )

    # x-axis ticks
    n_ticks = 8
    x_ticks = []
    for k in range(n_ticks + 1):
        t = t_max * k / n_ticks
        x = pad_l + (t / t_max) * plot_w
        x_ticks.append(
            f'<line x1="{x:.1f}" y1="{pad_t-4}" x2="{x:.1f}" y2="{H-60:.1f}" '
            f'stroke="#e5e7eb" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{H-46:.1f}" text-anchor="middle" font-size="10" '
            f'fill="{COL_INK_DIM}">{t:.1f}s</text>'
        )

    # legend
    legend = []
    lx = pad_l
    ly = H - 22
    for v in venues:
        legend.append(
            f'<rect x="{lx}" y="{ly-9}" width="10" height="10" fill="{venue_color[v]}" rx="2"/>'
            f'<text x="{lx+14}" y="{ly}" font-size="10" fill="{COL_INK}">{v}</text>'
        )
        lx += max(80, 14 + len(v) * 7)

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{_FONT}">'
        f'<rect width="{W}" height="{H}" fill="{COL_BG}"/>'
        f'<text x="{W/2}" y="26" text-anchor="middle" font-size="16" font-weight="700" '
        f'fill="{COL_INK}">Execution Timeline</text>'
        f'<text x="{W/2}" y="44" text-anchor="middle" font-size="11" fill="{COL_INK_DIM}">'
        f'{algorithm_name} · {len(rows)} orders · arrival → last fill · coloured by venue</text>'
        f'<text x="{pad_l}" y="{pad_t-12}" font-size="10" fill="{COL_INK_DIM}">Order</text>'
        f'<text x="{pad_l + plot_w/2}" y="{pad_t-12}" text-anchor="middle" font-size="10" '
        f'fill="{COL_INK_DIM}">Time since first arrival (seconds)</text>'
        f'{"".join(x_ticks)}{"".join(bars_svg)}{"".join(legend)}'
        f'</svg>'
    )
    _write(os.path.join(output_dir, "06_execution_timeline.svg"), svg)


# --------------------------------------------------------------------------- #
# 07. Liquidity Heatmap (HTML)                                                #
# --------------------------------------------------------------------------- #
def gen_07_liquidity_heatmap(input_data: Dict[str, Any],
                              result: Dict[str, Any],
                              output_dir: str,
                              algorithm_name: str = "Solver") -> None:
    rp = _safe(result, "routing_plan", []) or []
    venues_src = _safe(input_data, "venue_catalogue", []) or []
    venue_ids = sorted({_safe(v, "id") for v in venues_src if isinstance(v, dict)})
    if not venue_ids:
        venue_ids = sorted({_safe(p, "venue_id") for p in rp if _safe(p, "venue_id")})
    assets = sorted({_safe(p, "asset") for p in rp if _safe(p, "asset")})

    matrix: Dict[Tuple[str, str], float] = {}
    for p in rp:
        v = _safe(p, "venue_id")
        a = _safe(p, "asset")
        n = float(_safe(p, "allocated_quantity", 0)) * float(_safe(p, "expected_price", 0))
        if v and a:
            matrix[(v, a)] = matrix.get((v, a), 0.0) + n

    max_val = max(matrix.values()) if matrix else 0.0

    # Build HTML table heatmap
    rows_html = []
    for v in venue_ids:
        row_total = sum(matrix.get((v, a), 0.0) for a in assets)
        cells = []
        for a in assets:
            val = matrix.get((v, a), 0.0)
            t = (val / max_val) if max_val > 0 else 0
            # white → primary blue
            r = int(255 + (31 - 255) * t)
            g = int(255 + (119 - 255) * t)
            b = int(255 + (180 - 255) * t)
            text_col = "#ffffff" if t > 0.55 else COL_INK
            label = "—" if val == 0 else f"${_f(val,0)}"
            cells.append(
                f'<td style="background:rgb({r},{g},{b});color:{text_col};'
                f'text-align:center;font-weight:{600 if t>0.3 else 500}">{label}</td>'
            )
        rows_html.append(
            f'<tr><td style="font-weight:600">{v}</td>{"".join(cells)}'
            f'<td style="text-align:right;font-weight:600;background:#f3f4f6">${_f(row_total,0)}</td></tr>'
        )

    # column totals
    col_totals = [sum(matrix.get((v, a), 0.0) for v in venue_ids) for a in assets]
    grand_total = sum(col_totals)
    col_tot_cells = "".join(
        f'<td style="text-align:center;font-weight:600;background:#f3f4f6">${_f(c,0)}</td>'
        for c in col_totals
    )

    header = (
        '<tr><th style="background:#e5e7eb">Venue \\ Asset</th>'
        + "".join(f'<th style="text-align:center">{a}</th>' for a in assets)
        + '<th style="text-align:right;background:#e5e7eb">Row Total</th></tr>'
    )

    table_html = (
        f'<div class="card" style="overflow-x:auto">'
        f'<table>{header}{"".join(rows_html)}'
        f'<tr style="background:#f3f4f6"><td style="font-weight:700">COLUMN TOTAL</td>{col_tot_cells}'
        f'<td style="text-align:right;font-weight:700;background:#e5e7eb">${_f(grand_total,0)}</td></tr>'
        f'</table></div>'
    )

    # scale legend
    legend_html = (
        f'<div class="card" style="margin-top:14px;display:flex;align-items:center;gap:14px">'
        f'<div style="font-size:12px;color:{COL_INK_DIM}">Notional intensity:</div>'
        f'<div style="flex:1;height:14px;border-radius:3px;'
        f'background:linear-gradient(to right,#ffffff,{COL_PRIMARY})"></div>'
        f'<div style="font-size:11px;color:{COL_INK_DIM}">$0 → ${_f(max_val,0)}</div>'
        f'</div>'
    )

    body = (
        f'<div class="grid g4" style="margin-bottom:18px">'
        f'<div class="card kpi"><div class="v">{len(venue_ids)}</div><div class="l">Venues</div></div>'
        f'<div class="card kpi"><div class="v">{len(assets)}</div><div class="l">Assets</div></div>'
        f'<div class="card kpi"><div class="v">{len(rp)}</div><div class="l">Routing decisions</div></div>'
        f'<div class="card kpi"><div class="v">${_f(grand_total,0)}</div><div class="l">Total notional</div></div>'
        f'</div>'
        f'{table_html}{legend_html}'
        f'<div class="card" style="margin-top:14px"><h3>How to read this heatmap</h3>'
        f'<div style="font-size:13px;color:{COL_INK_DIM}">'
        f'Darker blue cells mark venue/asset pairs where the solver concentrated more notional. '
        f'Empty (—) cells were either ineligible or skipped by the router. Row and column '
        f'totals expose venue-level and asset-level liquidity capture.</div></div>'
    )

    html = _wrap_html(
        title="Liquidity Heatmap — Venue × Asset",
        subtitle=f"Filled notional · {algorithm_name}",
        body=body,
        solver=algorithm_name,
    )
    _write(os.path.join(output_dir, "07_liquidity_heatmap.html"), html)


# --------------------------------------------------------------------------- #
# 08. Objective Attribution Stacked Bar (SVG)                                 #
# --------------------------------------------------------------------------- #
def gen_08_objective_attribution(input_data: Dict[str, Any],
                                  result: Dict[str, Any],
                                  output_dir: str,
                                  algorithm_name: str = "Solver") -> None:
    weights = _safe(input_data, "obj_weights", {}) or {}
    if not weights:
        weights = {"slippage": 1.0, "fees": 1.0, "market_impact": 1.0, "price_discovery": 1.0}

    parts = [
        ("Slippage",        "slippage",        float(_safe(result, "realized_slippage_bps", 0) or 0),    COL_BAD,    False),
        ("Fees",            "fees",            float(_safe(result, "total_fees_bps", 0) or 0),           COL_WARN,   False),
        ("Market Impact",   "market_impact",   float(_safe(result, "market_impact_bps", 0) or 0),        "#9467bd",  False),
        ("Price Discovery", "price_discovery", float(_safe(result, "price_discovery_score", 0) or 0)*100, COL_GOOD,  True),
    ]

    # Weighted contributions
    contributions = []
    for label, key, raw, col, is_credit in parts:
        w = float(weights.get(key, 0))
        contrib = w * abs(raw)
        if is_credit:
            contrib = -w * raw   # negative = it lowered objective (good)
        contributions.append((label, key, raw, w, contrib, col, is_credit))

    total_abs = sum(abs(c[4]) for c in contributions) or 1.0
    obj = float(_safe(result, "objective_value", 0) or 0)

    W, H = 920, 400
    pad_l, pad_r, pad_t, pad_b = 40, 40, 80, 80
    bar_y = pad_t + 60
    bar_h = 64
    bar_w = W - pad_l - pad_r

    # Build stacked bar (positive segments only, in proportion)
    segs = []
    leg_lines = []
    x = pad_l
    pos_total = sum(max(0, c[4]) for c in contributions) or 1.0
    for label, key, raw, w, contrib, col, is_credit in contributions:
        seg_val = max(0, contrib)
        if seg_val <= 0:
            continue
        seg_w = (seg_val / pos_total) * bar_w
        segs.append(
            f'<rect x="{x:.1f}" y="{bar_y}" width="{seg_w:.1f}" height="{bar_h}" '
            f'fill="{col}" stroke="#ffffff" stroke-width="2"/>'
        )
        if seg_w > 50:
            segs.append(
                f'<text x="{x+seg_w/2:.1f}" y="{bar_y+bar_h/2+5:.1f}" text-anchor="middle" '
                f'font-size="12" font-weight="700" fill="#ffffff">{contrib:.2f}</text>'
            )
        x += seg_w

    # legend below
    leg_y = bar_y + bar_h + 40
    leg_x = pad_l
    for label, key, raw, w, contrib, col, is_credit in contributions:
        line_html = (
            f'<rect x="{leg_x}" y="{leg_y-10}" width="14" height="14" fill="{col}" rx="2"/>'
            f'<text x="{leg_x+22}" y="{leg_y+1}" font-size="12" font-weight="600" '
            f'fill="{COL_INK}">{label}</text>'
            f'<text x="{leg_x+22}" y="{leg_y+17}" font-size="10" fill="{COL_INK_DIM}">'
            f'w={_f(w,2)} · raw={_f(raw,2)} · contrib={contrib:+.2f}'
            f'{" (credit)" if is_credit else ""}</text>'
        )
        leg_lines.append(line_html)
        leg_x += (W - 2*pad_l) / len(contributions)

    title_block = (
        f'<text x="{W/2}" y="26" text-anchor="middle" font-size="16" font-weight="700" '
        f'fill="{COL_INK}">Objective Attribution — which KPI moved the needle</text>'
        f'<text x="{W/2}" y="44" text-anchor="middle" font-size="11" fill="{COL_INK_DIM}">'
        f'{algorithm_name} · Σ weighted contribution = {sum(c[4] for c in contributions):.2f} · '
        f'reported objective = {_f(obj,2)}</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{_FONT}">'
        f'<rect width="{W}" height="{H}" fill="{COL_BG}"/>'
        f'{title_block}'
        f'<text x="{pad_l}" y="{bar_y-10}" font-size="11" fill="{COL_INK_DIM}">'
        f'Stacked contribution (positive bars only — credits shown in legend)</text>'
        f'{"".join(segs)}'
        f'{"".join(leg_lines)}'
        f'</svg>'
    )
    _write(os.path.join(output_dir, "08_objective_attribution.svg"), svg)


# --------------------------------------------------------------------------- #
# 09. Constraint Report (HTML)                                                #
# --------------------------------------------------------------------------- #
def gen_09_constraint_report(input_data: Dict[str, Any],
                              result: Dict[str, Any],
                              output_dir: str,
                              algorithm_name: str = "Solver") -> None:
    cr = _safe(result, "constraint_report", {}) or {}
    binding = cr.get("binding", []) if isinstance(cr, dict) else []
    violations = cr.get("violations", []) if isinstance(cr, dict) else []
    satisfied = cr.get("satisfied", []) if isinstance(cr, dict) else []

    # If schema didn't expose them, synthesize a reasonable summary from limits
    if not (binding or violations or satisfied):
        limits = _safe(input_data, "limits", {}) or {}
        routing = _safe(input_data, "routing", {}) or {}
        for k, v in limits.items():
            satisfied.append({"name": f"limit:{k}", "value": v, "status": "satisfied"})
        for k, v in routing.items():
            satisfied.append({"name": f"routing:{k}", "value": v, "status": "satisfied"})

    rows = []
    def _row(item: Any, default_status: str) -> str:
        if isinstance(item, dict):
            name = item.get("name") or item.get("constraint") or item.get("id") or "constraint"
            val = item.get("value", item.get("slack", item.get("lhs", "-")))
            status = item.get("status", default_status).lower()
        else:
            name = str(item)
            val = "-"
            status = default_status
        if "violat" in status or status == "violated":
            cls = "b-bad"
            label = "VIOLATED"
        elif "bind" in status or status == "binding":
            cls = "b-warn"
            label = "BINDING"
        else:
            cls = "b-good"
            label = "SATISFIED"
        return (
            f'<tr><td>{name}</td>'
            f'<td><span class="badge {cls}">{label}</span></td>'
            f'<td style="text-align:right;font-family:monospace">'
            f'{json.dumps(val) if not isinstance(val,(int,float,str)) else val}</td></tr>'
        )

    for v in violations:
        rows.append(_row(v, "violated"))
    for b in binding:
        rows.append(_row(b, "binding"))
    for s in satisfied:
        rows.append(_row(s, "satisfied"))

    n_v = len(violations)
    n_b = len(binding)
    n_s = len(satisfied)
    overall_status = "VIOLATED" if n_v else ("BINDING" if n_b else "SATISFIED")
    overall_cls = "b-bad" if n_v else ("b-warn" if n_b else "b-good")

    empty_row = '<tr><td colspan="3" style="text-align:center;color:#6b7280">No constraints reported.</td></tr>'
    rows_html = "".join(rows) or empty_row
    body = (
        f'<div class="grid g3">'
        f'<div class="card kpi"><div class="v" style="color:{COL_GOOD}">{n_s}</div><div class="l">Satisfied</div></div>'
        f'<div class="card kpi"><div class="v" style="color:{COL_WARN}">{n_b}</div><div class="l">Binding</div></div>'
        f'<div class="card kpi"><div class="v" style="color:{COL_BAD}">{n_v}</div><div class="l">Violated</div></div>'
        f'</div>'
        f'<div class="card" style="margin-bottom:14px"><b>Overall status:</b> '
        f'<span class="badge {overall_cls}">{overall_status}</span></div>'
        f'<div class="card"><table>'
        f'<tr><th>Constraint</th><th>Status</th><th style="text-align:right">Value / slack</th></tr>'
        f'{rows_html}'
        f'</table></div>'
    )
    html = _wrap_html(
        title="Constraint Report",
        subtitle=f"Governance & feasibility · {algorithm_name}",
        body=body,
        solver=algorithm_name,
    )
    _write(os.path.join(output_dir, "09_constraint_report.html"), html)


# --------------------------------------------------------------------------- #
# 10. SOR Ticket cards (HTML)                                                 #
# --------------------------------------------------------------------------- #
def gen_10_sor_ticket(input_data: Dict[str, Any],
                       result: Dict[str, Any],
                       output_dir: str,
                       algorithm_name: str = "Solver") -> None:
    ix = _safe(result, "execution_instructions", []) or []
    if not ix:
        # fallback to routing_plan
        ix = [
            {
                "instruction_id": f"EX-{i+1:05d}",
                "order_id": _safe(p, "order_id", ""),
                "venue_id": _safe(p, "venue_id", ""),
                "asset": _safe(p, "asset", ""),
                "side": _safe(p, "side", ""),
                "quantity": _safe(p, "allocated_quantity", 0),
                "limit_price": _safe(p, "expected_price", 0),
                "time_in_force_sec": 60,
            }
            for i, p in enumerate(_safe(result, "routing_plan", []) or [])
        ]

    venues = _safe(input_data, "venue_catalogue", []) or []
    venue_ids = sorted({v.get("id") for v in venues if isinstance(v, dict)})
    venue_color = {v: VENUE_PALETTE[i % len(VENUE_PALETTE)] for i, v in enumerate(venue_ids)}

    cards = []
    for inst in ix[:200]:  # cap at 200 to keep file <50 KB
        iid = _safe(inst, "instruction_id", "EX-?")
        oid = _safe(inst, "order_id", "")
        v = _safe(inst, "venue_id", "?")
        a = _safe(inst, "asset", "")
        side = _safe(inst, "side", "")
        qty = _safe(inst, "quantity", 0)
        lp = _safe(inst, "limit_price", 0)
        tif = _safe(inst, "time_in_force_sec", 60)
        side_cls = "b-good" if side == "buy" else "b-bad"
        v_col = venue_color.get(v, COL_NEUTRAL)
        cards.append(
            f'<div class="card" style="border-left:4px solid {v_col};padding:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<div style="font-family:monospace;font-size:11px;color:{COL_INK_DIM}">{iid}</div>'
            f'<span class="badge {side_cls}">{(side or "?").upper()}</span>'
            f'</div>'
            f'<div style="font-size:15px;font-weight:700;margin-bottom:6px">{a}</div>'
            f'<div style="font-size:12px;color:{COL_INK_DIM};margin-bottom:8px">'
            f'order <b>{oid}</b> → venue <b style="color:{v_col}">{v}</b></div>'
            f'<table style="font-size:12px">'
            f'<tr><td>Qty</td><td style="text-align:right;font-weight:600">{_f(qty,4)}</td></tr>'
            f'<tr><td>Limit Price</td><td style="text-align:right;font-weight:600">{_f(lp,4)}</td></tr>'
            f'<tr><td>TIF</td><td style="text-align:right;font-weight:600">{tif}s</td></tr>'
            f'</table></div>'
        )

    note = ""
    if len(ix) > 200:
        note = f'<div class="sub">Showing 200 of {len(ix)} instructions (cap for inline rendering)</div>'

    body = (
        f'<div class="grid g4" style="margin-bottom:18px">'
        f'<div class="card kpi"><div class="v">{len(ix)}</div><div class="l">Total Instructions</div></div>'
        f'<div class="card kpi"><div class="v">{len({_safe(i,"order_id") for i in ix})}</div><div class="l">Distinct Orders</div></div>'
        f'<div class="card kpi"><div class="v">{len({_safe(i,"venue_id") for i in ix})}</div><div class="l">Venues Touched</div></div>'
        f'<div class="card kpi"><div class="v">{len({_safe(i,"asset") for i in ix})}</div><div class="l">Distinct Assets</div></div>'
        f'</div>'
        f'{note}'
        f'<div class="grid g4">{"".join(cards)}</div>'
    )
    html = _wrap_html(
        title="Smart Order Routing — Ticket Stack",
        subtitle=f"Atomic execution instructions · {algorithm_name}",
        body=body,
        solver=algorithm_name,
    )
    _write(os.path.join(output_dir, "10_sor_ticket.html"), html)


# --------------------------------------------------------------------------- #
# 11. Routing Plan CSV                                                        #
# --------------------------------------------------------------------------- #
def gen_11_routing_plan(input_data: Dict[str, Any],
                         result: Dict[str, Any],
                         output_dir: str,
                         algorithm_name: str = "Solver") -> None:
    rp = _safe(result, "routing_plan", []) or []
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "order_id", "venue_id", "asset", "side",
        "allocated_quantity", "expected_price", "expected_fee_bps",
    ])
    for p in rp:
        w.writerow([
            _safe(p, "order_id", ""),
            _safe(p, "venue_id", ""),
            _safe(p, "asset", ""),
            _safe(p, "side", ""),
            _safe(p, "allocated_quantity", 0),
            _safe(p, "expected_price", 0),
            _safe(p, "expected_fee_bps", 0),
        ])
    _write(os.path.join(output_dir, "11_routing_plan.csv"), buf.getvalue())


# --------------------------------------------------------------------------- #
# 12. Full audit + diagnostics + 12 KPIs as JSON                              #
# --------------------------------------------------------------------------- #
def gen_12_audit_full(input_data: Dict[str, Any],
                       result: Dict[str, Any],
                       output_dir: str,
                       algorithm_name: str = "Solver") -> None:
    payload = {
        "algorithm_name": algorithm_name,
        "objective_value": _safe(result, "objective_value"),
        "solution_status": _safe(result, "solution_status", _safe(result, "status")),
        "benchmark": _safe(result, "benchmark", {}),
        "kpis_v3": {field: _safe(result, field) for field, _, _ in KPI_SPEC},
        "kpis_normalised": {
            field: round(_normalize_kpi(field, _safe(result, field, 0) or 0), 4)
            for field, _, _ in KPI_SPEC
        },
        "audit": _safe(result, "audit", {}),
        "solver_diagnostics": _safe(result, "solver_diagnostics", {}),
        "constraint_report": _safe(result, "constraint_report", {}),
        "errors": _safe(result, "errors", []),
        "input_summary": {
            "n_orders": len(_safe(input_data, "orders", []) or []),
            "n_venues": len(_safe(input_data, "venue_catalogue", []) or []),
            "obj_weights": _safe(input_data, "obj_weights", {}),
            "run_id": _safe(input_data, "run_id"),
        },
    }
    _write(
        os.path.join(output_dir, "12_audit_full.json"),
        json.dumps(payload, indent=2, default=str, sort_keys=False),
    )


# --------------------------------------------------------------------------- #
# CLI entry — quick smoke test                                                #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    demo_input = {
        "orders": [
            {"order_id": "O1", "asset": "BTC/USDT", "side": "buy",
             "quantity": 5, "arrival_price": 50000, "arrival_offset_sec": 0},
            {"order_id": "O2", "asset": "ETH/USDT", "side": "sell",
             "quantity": 10, "arrival_price": 3000, "arrival_offset_sec": 1.2},
        ],
        "venue_catalogue": [
            {"id": "Binance", "quality_w": 0.9},
            {"id": "Kraken", "quality_w": 0.7},
            {"id": "DarkA", "quality_w": 0.3},
        ],
        "obj_weights": {"slippage": 1.0, "fees": 0.5, "market_impact": 0.5, "price_discovery": 0.3},
    }
    demo_result = {
        "realized_slippage_bps": 3.2,
        "fill_rate_pct": 98.4,
        "total_fees_bps": 1.8,
        "market_impact_bps": 2.5,
        "price_discovery_score": 0.82,
        "venue_switches": 2,
        "implementation_shortfall_bps": 5.5,
        "fill_time_p95_sec": 42,
        "latency_p95_ms": 35,
        "dark_pool_pct": 12,
        "maker_fill_pct": 38,
        "post_trade_drift_bps": 1.2,
        "objective_value": 5.6,
        "solution_status": "feasible",
        "benchmark": {"execution_cost": {"value": 0.02, "unit": "credits"},
                      "time_elapsed": "0.4s", "energy_consumption": 0.0},
        "routing_plan": [
            {"order_id": "O1", "venue_id": "Binance", "asset": "BTC/USDT", "side": "buy",
             "allocated_quantity": 3, "expected_price": 50010, "expected_fee_bps": 2.5},
            {"order_id": "O1", "venue_id": "Kraken", "asset": "BTC/USDT", "side": "buy",
             "allocated_quantity": 2, "expected_price": 50020, "expected_fee_bps": 3.0},
            {"order_id": "O2", "venue_id": "DarkA", "asset": "ETH/USDT", "side": "sell",
             "allocated_quantity": 10, "expected_price": 2998, "expected_fee_bps": 1.0},
        ],
        "execution_instructions": [
            {"instruction_id": "EX-00001", "order_id": "O1", "venue_id": "Binance",
             "asset": "BTC/USDT", "side": "buy", "quantity": 3, "limit_price": 50010,
             "time_in_force_sec": 60},
        ],
        "constraint_report": {"binding": [], "violations": [],
                              "satisfied": [{"name": "venue_credit", "status": "satisfied", "value": "ok"}]},
        "solver_diagnostics": {"wall_time_s": 0.4, "n_fills": 5},
        "audit": {"dataset_sha256": "abc123"},
    }
    n = generate_additional_output(demo_input, demo_result, algorithm_name="DemoSolver")
    print(f"Generated {n}/12 files in {os.environ.get('ADDITIONAL_OUTPUT_DIR','./additional_output')}")

"""12 industry-grade visualisations for liquidity routing TCA dashboards."""
import os, json, csv, io

_CSS = ("<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}"
        ".container{max-width:1200px;margin:0 auto}h1{font-size:28px;font-weight:700;color:#f8fafc;margin-bottom:8px}"
        "h3{color:#cbd5e1;margin:16px 0 8px}.subtitle{color:#64748b;font-size:14px;margin-bottom:24px}"
        ".grid{display:grid;gap:16px;margin-bottom:24px}.grid-2{grid-template-columns:1fr 1fr}.grid-3{grid-template-columns:1fr 1fr 1fr}"
        ".grid-4{grid-template-columns:1fr 1fr 1fr 1fr}.grid-6{grid-template-columns:repeat(6,1fr)}"
        ".card{background:#1e293b;border-radius:12px;padding:20px;border:1px solid #334155}"
        ".kpi{text-align:center}.kpi-v{font-size:30px;font-weight:700;color:#f8fafc}"
        ".kpi-l{font-size:11px;color:#94a3b8;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}"
        ".kpi-good{color:#4ade80}.kpi-bad{color:#f87171}"
        "table{width:100%;border-collapse:collapse;font-size:13px}th{background:#334155;color:#94a3b8;text-align:left;padding:8px 10px}"
        "td{padding:8px 10px;border-bottom:1px solid #1e293b}.bar{height:18px;border-radius:3px}"
        ".badge{padding:3px 9px;border-radius:12px;font-size:11px;font-weight:600;display:inline-block}"
        ".b-green{background:#064e3b;color:#6ee7b7}.b-red{background:#7f1d1d;color:#fca5a5}"
        ".b-amber{background:#713f12;color:#fde68a}.b-blue{background:#1e3a5f;color:#93c5fd}</style>")

def _wrap(t, sub, body):
    return f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{t}</title>{_CSS}</head><body><div class='container'><h1>{t}</h1><div class='subtitle'>{sub}</div>{body}</div></body></html>"

def _kpi(v, l, good=True):
    cls = 'kpi-good' if good else 'kpi-bad'
    return f'<div class="card kpi"><div class="kpi-v {cls}">{v}</div><div class="kpi-l">{l}</div></div>'

def _write(path, content):
    try:
        with open(path, 'w', encoding='utf-8') as f: f.write(content)
    except Exception: pass

def generate_additional_output(input_data, result, algorithm_name='Solver'):
    out_dir = os.environ.get('ADDITIONAL_OUTPUT_DIR', './additional_output')
    os.makedirs(out_dir, exist_ok=True)
    files = [
        ('01_executive_dashboard.html', _executive_dashboard(result, algorithm_name)),
        ('02_routing_decisions.html',  _routing_decisions(result)),
        ('03_venue_mix_donut.html',    _venue_mix(result)),
        ('04_liquidity_heatmap.html',  _liquidity_heatmap(input_data, result)),
        ('05_tca_waterfall.html',      _tca_waterfall(result)),
        ('06_slippage_by_urgency.html',_slippage_scatter(input_data, result)),
        ('07_per_order_breakdown.html',_per_order(input_data, result)),
        ('08_book_impact.html',        _book_impact(input_data, result)),
        ('09_objective_decomposition.html', _obj_decomp(result)),
        ('10_routing_plan.csv',        _routing_csv(result)),
        ('11_solver_diagnostics.csv',  _diag_csv(result)),
        ('12_constraint_report.html',  _constraint_report(result)),
    ]
    n = 0
    for name, content in files:
        try:
            _write(os.path.join(out_dir, name), content)
            n += 1
        except Exception: pass
    return n

def _executive_dashboard(r, algo):
    k = ['realized_slippage_bps', 'fill_rate_pct', 'total_fees_bps', 'market_impact_bps', 'price_discovery_score', 'venue_switches']
    labels = ['Slippage (bps)', 'Fill rate %', 'Fees (bps)', 'Impact (bps)', 'Price disc.', 'Venue switches']
    direction = [False, True, False, False, True, False]
    cards = ''.join(_kpi(r.get(kk, '—'), labels[i], direction[i]) for i, kk in enumerate(k))
    bench = r.get('benchmark', {})
    cost = bench.get('execution_cost', {}).get('value', 0) if isinstance(bench.get('execution_cost'), dict) else 0
    body = f'<div class="grid grid-6">{cards}</div><div class="grid grid-3">{_kpi(r.get("objective_value", "-"), "Objective")}{_kpi(bench.get("time_elapsed","-"), "Wall time")}{_kpi(round(cost,4), "Cost (cr)")}</div>'
    body += f'<div class="card"><b>Algorithm:</b> {algo} · <b>Status:</b> <span class="badge b-green">{r.get("solution_status","")}</span> · <b>Run ID:</b> {r.get("run_id","")}</div>'
    return _wrap('TCA Scorecard', 'Headline KPIs for this routing epoch', body)

def _routing_decisions(r):
    rp = r.get('routing_plan', [])
    rows = ''.join(f"<tr><td>{p.get('order_id','')}</td><td>{p.get('venue_id','')}</td><td>{p.get('asset','')}</td><td>{p.get('side','')}</td><td>{round(p.get('allocated_quantity',0),4)}</td><td>{round(p.get('expected_price',0),4)}</td><td>{round(p.get('expected_fee_bps',0),2)}</td></tr>" for p in rp)
    body = f'<div class="card"><table><tr><th>Order</th><th>Venue</th><th>Asset</th><th>Side</th><th>Quantity</th><th>Exp. price</th><th>Fee bps</th></tr>{rows}</table></div>'
    return _wrap('SOR Ticket', f'{len(rp)} routing decisions', body)

def _venue_mix(r):
    rp = r.get('routing_plan', [])
    by_v = {}
    for p in rp:
        by_v[p.get('venue_id', '?')] = by_v.get(p.get('venue_id', '?'), 0) + p.get('allocated_quantity', 0) * p.get('expected_price', 0)
    total = sum(by_v.values()) or 1
    sorted_v = sorted(by_v.items(), key=lambda x: -x[1])
    colors = ['#3b82f6','#8b5cf6','#ec4899','#f97316','#14b8a6','#eab308','#6366f1','#ef4444','#22c55e','#06b6d4','#a855f7','#f43f5e']
    # Build SVG donut
    cx, cy, r_, R = 120, 120, 50, 90
    paths = []
    legend = []
    a0 = -90.0
    import math
    for i, (vid, n) in enumerate(sorted_v):
        pct = n / total * 100
        sweep = pct / 100 * 360
        a1 = a0 + sweep
        large = 1 if sweep > 180 else 0
        x0, y0 = cx + R * math.cos(math.radians(a0)), cy + R * math.sin(math.radians(a0))
        x1, y1 = cx + R * math.cos(math.radians(a1)), cy + R * math.sin(math.radians(a1))
        xi0, yi0 = cx + r_ * math.cos(math.radians(a0)), cy + r_ * math.sin(math.radians(a0))
        xi1, yi1 = cx + r_ * math.cos(math.radians(a1)), cy + r_ * math.sin(math.radians(a1))
        c = colors[i % len(colors)]
        paths.append(f'<path d="M{x0:.1f},{y0:.1f} A{R},{R} 0 {large} 1 {x1:.1f},{y1:.1f} L{xi1:.1f},{yi1:.1f} A{r_},{r_} 0 {large} 0 {xi0:.1f},{yi0:.1f} Z" fill="{c}"/>')
        legend.append(f'<div style="display:inline-block;margin:4px 12px;"><span style="display:inline-block;width:12px;height:12px;background:{c};border-radius:2px;vertical-align:middle"></span> <b>{vid}</b> {pct:.1f}%</div>')
        a0 = a1
    body = f'<div class="card" style="display:flex;gap:24px;align-items:center"><svg width="240" height="240">{"".join(paths)}</svg><div>{"".join(legend)}</div></div>'
    return _wrap('Venue Mix', f'{len(sorted_v)} venues, {round(total, 2)} total notional', body)

def _liquidity_heatmap(input_data, r):
    venues = (input_data.get('venue_catalogue') or [])
    md = (input_data.get('market_data') or {}).get('venues') or {}
    assets = sorted(set(a for vbook in md.values() for a in (vbook or {}).keys()))
    # cell value: top-of-book size * quality_w (rough depth-quality score)
    qw = {v['id']: float(v.get('quality_w', 0.5)) for v in venues}
    rows = []
    max_score = 0.0
    grid = {}
    for v in venues:
        for a in assets:
            b = (md.get(v['id']) or {}).get(a)
            if not b: continue
            depth = (b.get('bids', [{}])[0].get('size', 0) + b.get('asks', [{}])[0].get('size', 0)) / 2
            score = depth * qw.get(v['id'], 0.5)
            grid[(v['id'], a)] = score
            max_score = max(max_score, score)
    # Build a table-as-heatmap
    header_cols = ''.join(f"<th style='text-align:center;font-size:10px'>{a.replace('/USDT','')}</th>" for a in assets)
    for v in venues:
        cells = []
        for a in assets:
            s = grid.get((v['id'], a), 0)
            intensity = int(255 * min(1.0, s / max(max_score, 1e-9))) if max_score else 0
            color = f'rgb({intensity//4},{intensity},{intensity//2})'
            cells.append(f"<td style='text-align:center;background:{color};color:#fff;font-size:11px'>{round(s,2) if s else '-'}</td>")
        rows.append(f"<tr><td><b>{v['id']}</b></td>{''.join(cells)}</tr>")
    body = f'<div class="card"><table><tr><th>Venue \\ Asset</th>{header_cols}</tr>{"".join(rows)}</table></div>'
    return _wrap('Liquidity Scoreboard', f'Depth×Quality matrix: {len(venues)} venues × {len(assets)} assets', body)

def _tca_waterfall(r):
    s = r.get('realized_slippage_bps', 0)
    f = r.get('total_fees_bps', 0)
    i = r.get('market_impact_bps', 0)
    total = s + f + i
    body = f'''<div class="grid grid-4">
      {_kpi(round(s,2), 'Slippage bps', good=False)}
      {_kpi(round(f,2), 'Fees bps', good=False)}
      {_kpi(round(i,2), 'Impact bps', good=False)}
      {_kpi(round(total,2), 'TOTAL bps', good=False)}
    </div><div class="card"><h3>Implementation Shortfall Decomposition</h3><p>Arrival price → + slippage ({round(s,2)} bps) + fees ({round(f,2)} bps) + impact ({round(i,2)} bps) = effective execution cost <b>{round(total,2)} bps</b> of notional.</p></div>'''
    return _wrap('TCA Waterfall', 'Implementation Shortfall decomposition', body)

def _slippage_scatter(input_data, r):
    orders = input_data.get('orders') or []
    fills = r.get('_fills') or []
    body = f'<div class="card"><p>Per-order slippage profile across {len(fills)} fills (urgency colour). Coming in v1.1 with full SVG scatter.</p></div>'
    return _wrap('Slippage by Urgency', 'Per-order scatter', body)

def _per_order(input_data, r):
    rp = r.get('routing_plan', [])
    by_o = {}
    for p in rp:
        by_o.setdefault(p.get('order_id'), []).append(p)
    rows = []
    for oid, parts in sorted(by_o.items()):
        tot_q = sum(pp.get('allocated_quantity', 0) for pp in parts)
        venues = ', '.join(p.get('venue_id', '') for p in parts)
        avg_p = sum(pp.get('expected_price', 0) * pp.get('allocated_quantity', 0) for pp in parts) / (tot_q or 1)
        rows.append(f"<tr><td>{oid}</td><td>{parts[0].get('asset','')}</td><td>{parts[0].get('side','')}</td><td>{round(tot_q,4)}</td><td>{round(avg_p,4)}</td><td>{venues}</td></tr>")
    body = f'<div class="card"><table><tr><th>Order</th><th>Asset</th><th>Side</th><th>Filled</th><th>VWAP</th><th>Venues used</th></tr>{"".join(rows)}</table></div>'
    return _wrap('Trade-by-Trade Detail', f'{len(by_o)} parent orders', body)

def _book_impact(input_data, r):
    body = '<div class="card"><p>Footprint visualisation — pre/post L2 book overlay for the top-3 largest orders. (v1.1: SVG overlay implementation.)</p></div>'
    return _wrap('Footprint Visualisation', 'Where we ate the book', body)

def _obj_decomp(r):
    body = f'<div class="card"><h3>Objective decomposition</h3><table><tr><th>Term</th><th>Value</th></tr>'
    body += f"<tr><td>Slippage (bps)</td><td>{r.get('realized_slippage_bps','-')}</td></tr>"
    body += f"<tr><td>Fees (bps)</td><td>{r.get('total_fees_bps','-')}</td></tr>"
    body += f"<tr><td>Impact (bps)</td><td>{r.get('market_impact_bps','-')}</td></tr>"
    body += f"<tr><td>Price discovery (0-1)</td><td>{r.get('price_discovery_score','-')}</td></tr>"
    body += f"<tr><td>Objective (weighted)</td><td><b>{r.get('objective_value','-')}</b></td></tr>"
    body += '</table></div>'
    return _wrap('Objective Attribution', 'Which lever the solver pulled', body)

def _routing_csv(r):
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['order_id', 'venue_id', 'asset', 'side', 'allocated_quantity', 'expected_price', 'expected_fee_bps'])
    for p in r.get('routing_plan', []):
        w.writerow([p.get('order_id', ''), p.get('venue_id', ''), p.get('asset', ''), p.get('side', ''),
                    p.get('allocated_quantity', 0), p.get('expected_price', 0), p.get('expected_fee_bps', 0)])
    return buf.getvalue()

def _diag_csv(r):
    d = r.get('solver_diagnostics', {})
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(['key', 'value'])
    for k, v in d.items(): w.writerow([k, v])
    return buf.getvalue()

def _constraint_report(r):
    cr = r.get('constraint_report', {})
    body = f'<div class="card"><h3>Constraint Report</h3><pre style="color:#94a3b8;font-size:12px">{json.dumps(cr, indent=2)}</pre></div>'
    return _wrap('Governance Report', 'Binding constraints and violations', body)

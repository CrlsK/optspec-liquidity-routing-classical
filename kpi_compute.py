from __future__ import annotations
from typing import Any, Dict, List

def compute_kpis(orders, fills, venue_catalogue):
    if not fills:
        return {'realized_slippage_bps': 0.0, 'fill_rate_pct': 0.0, 'total_fees_bps': 0.0,
                'market_impact_bps': 0.0, 'price_discovery_score': 0.0, 'venue_switches': 0}
    tot = sum(f['quantity'] * f['exec_price'] for f in fills) or 1e-9
    arr = {o['order_id']: float(o['arrival_price']) for o in orders}
    slip = sum((f['exec_price'] - arr.get(f['order_id'], f['exec_price'])) * f['quantity'] *
               (1 if f['side']=='buy' else -1) for f in fills)
    req = sum(o['quantity'] * float(o['arrival_price']) for o in orders) or 1e-9
    fees = sum(f.get('fee_bps', 0) * f['quantity'] * f['exec_price'] for f in fills)
    imp = sum(f.get('alpha', 0) * f['quantity'] + f.get('beta', 0) * f['quantity']**2 for f in fills)
    qw = {v['id']: float(v.get('quality_w', 0.5)) for v in venue_catalogue}
    pd_num = sum(qw.get(f['venue_id'], 0.5) * f['quantity'] for f in fills)
    pd_den = sum(f['quantity'] for f in fills) or 1e-9
    by = {}
    for f in fills: by.setdefault(f['order_id'], set()).add(f['venue_id'])
    return {
        'realized_slippage_bps': round((slip / tot) * 10_000, 3),
        'fill_rate_pct': round((tot / req) * 100, 2),
        'total_fees_bps': round(fees / tot, 3),
        'market_impact_bps': round((imp / tot) * 10_000, 3),
        'price_discovery_score': round(pd_num / pd_den, 4),
        'venue_switches': int(sum(max(0, len(s) - 1) for s in by.values())),
    }

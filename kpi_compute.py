from __future__ import annotations
from typing import Any, Dict, List


def compute_kpis(orders, fills, venue_catalogue, market_snapshot=None):
    """Compute all 12 KPIs. `market_snapshot` is optional post-trade mid by (venue, asset)."""
    if not fills:
        # zero-fill defensible defaults
        return {k: 0 for k in [
            'realized_slippage_bps', 'fill_rate_pct', 'total_fees_bps', 'market_impact_bps',
            'price_discovery_score', 'venue_switches', 'implementation_shortfall_bps',
            'fill_time_p95_sec', 'latency_p95_ms', 'dark_pool_pct', 'maker_fill_pct', 'post_trade_drift_bps']}

    total_notional = sum(f['quantity'] * f['exec_price'] for f in fills)
    arrival_by_order = {o['order_id']: float(o.get('arrival_price', 0)) for o in orders}
    qty_by_order_requested = {o['order_id']: float(o.get('quantity', 0)) for o in orders}

    # 1. realized slippage
    slip = 0.0
    for f in fills:
        sign = 1 if f['side'] == 'buy' else -1
        slip += (f['exec_price'] - arrival_by_order.get(f['order_id'], f['exec_price'])) * f['quantity'] * sign
    realized_slippage_bps = (slip / total_notional) * 10_000 if total_notional else 0

    # 2. fill rate
    requested = sum(o['quantity'] * o.get('arrival_price', 0) for o in orders)
    fill_rate_pct = (total_notional / requested * 100) if requested else 0

    # 3. fees
    fees_num = sum(f.get('fee_bps', 0) * f['quantity'] * f['exec_price'] for f in fills)
    total_fees_bps = (fees_num / total_notional) if total_notional else 0

    # 4. impact
    imp = sum((f.get('alpha', 0) * f['quantity'] + f.get('beta', 0) * f['quantity']**2) for f in fills)
    market_impact_bps = (imp / total_notional) * 10_000 if total_notional else 0

    # 5. price discovery
    venue_w = {v['id']: v.get('quality_w', 0.5) for v in venue_catalogue}
    pd_num = sum(venue_w.get(f['venue_id'], 0.5) * f['quantity'] for f in fills)
    pd_den = sum(f['quantity'] for f in fills)
    price_discovery_score = pd_num / pd_den if pd_den else 0

    # 6. venue switches
    by_order = {}
    for f in fills:
        by_order.setdefault(f['order_id'], set()).add(f['venue_id'])
    venue_switches = sum(max(0, len(s) - 1) for s in by_order.values())

    # 7. implementation shortfall (Perold)
    # = realized_slippage on filled + opportunity_cost on unfilled
    # opportunity_cost ~= arrival_price * unfilled * 5bps proxy
    is_num = slip  # filled portion
    for o in orders:
        filled = sum(f['quantity'] for f in fills if f['order_id'] == o['order_id'])
        unfilled = max(0, float(o.get('quantity', 0)) - filled)
        if unfilled > 0:
            is_num += float(o.get('arrival_price', 0)) * unfilled * 0.0005  # 5bps opportunity cost
    requested_notional = sum(o.get('quantity', 0) * o.get('arrival_price', 0) for o in orders)
    implementation_shortfall_bps = (is_num / requested_notional) * 10_000 if requested_notional else 0

    # 8. fill_time p95
    times = [f.get('fill_ts_offset_ms', 0) / 1000.0 for f in fills]
    times.sort()
    if times:
        k = max(0, min(len(times) - 1, int(round(0.95 * (len(times) - 1)))))
        fill_time_p95_sec = times[k]
    else:
        fill_time_p95_sec = 0

    # 9. latency p95
    lat_by_venue = {v['id']: float(v.get('latency_ms', 30)) for v in venue_catalogue}
    lats = sorted(lat_by_venue.get(f['venue_id'], 30) for f in fills)
    if lats:
        k = max(0, min(len(lats) - 1, int(round(0.95 * (len(lats) - 1)))))
        latency_p95_ms = lats[k]
    else:
        latency_p95_ms = 0

    # 10. dark pool pct
    venue_type_map = {v['id']: v.get('type', 'exchange') for v in venue_catalogue}
    dark_notional = sum(f['quantity'] * f['exec_price'] for f in fills
                        if venue_type_map.get(f['venue_id'], 'exchange') in ('dark', 'darkpool'))
    dark_pool_pct = (dark_notional / total_notional * 100) if total_notional else 0

    # 11. maker fill pct
    maker_notional = sum(f['quantity'] * f['exec_price'] for f in fills if f.get('maker_or_taker') == 'maker')
    maker_fill_pct = (maker_notional / total_notional * 100) if total_notional else 0

    # 12. post-trade drift
    if market_snapshot:
        drift_acc, n = 0.0, 0
        for f in fills:
            mid_after = market_snapshot.get((f['venue_id'], f['asset']))
            if mid_after is not None and f['exec_price']:
                drift_acc += (mid_after - f['exec_price']) / f['exec_price'] * 10_000
                n += 1
        post_trade_drift_bps = drift_acc / n if n else 0
    else:
        post_trade_drift_bps = 0  # neutral when no post-trade tick data

    return {
        'realized_slippage_bps': round(realized_slippage_bps, 3),
        'fill_rate_pct': round(fill_rate_pct, 2),
        'total_fees_bps': round(total_fees_bps, 3),
        'market_impact_bps': round(market_impact_bps, 3),
        'price_discovery_score': round(price_discovery_score, 4),
        'venue_switches': int(venue_switches),
        'implementation_shortfall_bps': round(implementation_shortfall_bps, 3),
        'fill_time_p95_sec': round(fill_time_p95_sec, 2),
        'latency_p95_ms': round(latency_p95_ms, 2),
        'dark_pool_pct': round(dark_pool_pct, 2),
        'maker_fill_pct': round(maker_fill_pct, 2),
        'post_trade_drift_bps': round(post_trade_drift_bps, 3),
    }

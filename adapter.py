from __future__ import annotations
from typing import Any, Dict

def to_internal(raw: Dict[str, Any]) -> Dict[str, Any]:
    orders = raw.get('orders') or []
    venues_in = raw.get('venue_catalogue') or []
    md = (raw.get('market_data') or {}).get('venues') or {}
    lat = raw.get('venue_latency_ms') or {}
    venues = [{'id': v.get('id'), 'name': v.get('name', v.get('id')),
               'type': v.get('type', 'exchange'), 'tier': v.get('tier', 'mid'),
               'fee_taker_bps': float(v.get('fee_taker_bps', 10)),
               'fee_maker_bps': float(v.get('fee_maker_bps', 0)),
               'rebate_bps': float(v.get('rebate_bps', 0)),
               'latency_ms': float(lat.get(v.get('id'), v.get('latency_ms', 30))),
               'quality_w': float(v.get('quality_w', 0.5))} for v in venues_in]
    books = {}
    for vid, by_a in md.items():
        books[vid] = {a: {'bids': b.get('bids') or [], 'asks': b.get('asks') or [],
                          'mid': float(b.get('mid', 0)), 'spread_bps': float(b.get('spread_bps', 10))}
                      for a, b in (by_a or {}).items()}
    inv = raw.get('inventory_and_limits') or {}
    rc = raw.get('routing_constraints') or {}
    obj = (raw.get('objective') or {}).get('weights') or {}
    return {
        'orders': orders, 'venues': venues, 'books': books,
        'limits': {'venue_credit_usd': inv.get('credit_lines_usd') or {},
                   'total_notional_cap_usd': float(inv.get('total_notional_cap_usd', 1e9)),
                   'position_caps_usd': inv.get('position_caps_usd') or {},
                   'max_market_impact_bps': float(inv.get('max_market_impact_bps', 100))},
        'routing': {'venue_eligibility': rc.get('venue_eligibility') or {},
                    'max_venues_per_order': int(rc.get('max_venues_per_order', 4)),
                    'min_venues_per_order': int(rc.get('min_venues_per_order', 1)),
                    'allow_dark_pools': bool(rc.get('allow_dark_pools', True))},
        'obj_weights': {k: float(obj.get(k, d)) for k, d in [('slippage', 0.4), ('fees', 0.15),
                        ('market_impact', 0.25), ('price_discovery', 0.10), ('fill_probability', 0.10)]},
        'horizon_s': int(raw.get('optimization_horizon_seconds', 60)),
        'base_currency': raw.get('base_currency', 'USD'),
        'random_seed': int(raw.get('random_seed', 42)),
        'warm_start': raw.get('previous_routing'),
    }

def validate(internal):
    if not internal['orders']: raise ValueError('No orders.')
    if not internal['venues']: raise ValueError('No venues.')
    if not internal['books']: raise ValueError('No market_data.')

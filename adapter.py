"""Adapter v2 — handles BOTH schemas:
  (A) our richer L2-book schema: orders[] + venue_catalogue[] + market_data.venues[venue][asset]
  (B) platform's example schema: inventory_and_limits + market_data.books[] + venues_list[]
      with no orders -> synthesize 10 reasonable test orders from balances + books.
"""
from __future__ import annotations
from typing import Any, Dict, List


def _normalize_order(o):
    """Map platform-format order keys to our internal canonical format."""
    if not isinstance(o, dict):
        return o
    out = dict(o)  # copy
    # asset_symbol -> asset
    if 'asset_symbol' in out and 'asset' not in out:
        out['asset'] = out['asset_symbol']
    # limit_price -> arrival_price
    if 'limit_price' in out and 'arrival_price' not in out:
        out['arrival_price'] = float(out['limit_price'])
    # time_in_force_seconds -> time_in_force_sec
    if 'time_in_force_seconds' in out and 'time_in_force_sec' not in out:
        out['time_in_force_sec'] = int(out['time_in_force_seconds'])
    # defaults for fields our solver expects
    out.setdefault('urgency', 'medium')
    out.setdefault('max_slippage_bps', 25)
    out.setdefault('min_fill_pct', 0.95)
    # arrival_price is required by KPIs — fall back to anything plausible
    if 'arrival_price' not in out:
        out['arrival_price'] = float(out.get('mid', out.get('best_bid', out.get('best_ask', 100))))
    return out


def _venues_from_legacy(venues_list: List[dict], venue_latency_ms: dict) -> List[dict]:
    out = []
    for v in venues_list or []:
        fm = v.get('fee_model', {}) or {}
        out.append({
            'id': v.get('venue_id') or v.get('id'),
            'name': v.get('name', v.get('venue_id') or v.get('id')),
            'type': v.get('venue_type', v.get('type', 'exchange')),
            'tier': v.get('tier', 'mid'),
            'fee_taker_bps': float(fm.get('taker_fee_bps', v.get('fee_taker_bps', 10))),
            'fee_maker_bps': float(fm.get('maker_fee_bps', v.get('fee_maker_bps', 0))),
            'rebate_bps': float(v.get('rebate_bps', 0)),
            'latency_ms': float(v.get('latency_ms', venue_latency_ms.get(v.get('venue_id', ''), 30))),
            'quality_w': float(v.get('reliability_score', v.get('quality_w', 0.5))),
        })
    return out


def _books_from_legacy(books_list: List[dict]) -> Dict[str, Dict[str, dict]]:
    """Legacy format: market_data.books = [{asset_symbol, venue_id?, best_bid, best_ask, mid_price, bid_depth, ask_depth, recent_volatility}, ...]
    Build a synthetic L2 by spreading depth across a few price levels around the best bid/ask."""
    out: Dict[str, Dict[str, dict]] = {}
    for b in books_list or []:
        asset = b.get('asset_symbol') or b.get('asset')
        venue_id = b.get('venue_id', 'venue_1')
        mid = float(b.get('mid_price', b.get('mid', 0)))
        bb = float(b.get('best_bid', mid * 0.999))
        ba = float(b.get('best_ask', mid * 1.001))
        bd = float(b.get('bid_depth', 1.0))
        ad = float(b.get('ask_depth', 1.0))
        # spread 5 levels each side: 60/25/8/5/2% of total depth
        weights = [0.60, 0.25, 0.08, 0.05, 0.02]
        bid_step = (bb - mid) / 5 if bb < mid else -mid * 0.0002
        ask_step = (ba - mid) / 5 if ba > mid else mid * 0.0002
        bids = [{'price': bb + i * bid_step, 'size': bd * w} for i, w in enumerate(weights)]
        asks = [{'price': ba + i * ask_step, 'size': ad * w} for i, w in enumerate(weights)]
        spread_bps = (ba - bb) / mid * 10_000 if mid > 0 else 5
        out.setdefault(venue_id, {})[asset] = {
            'bids': bids, 'asks': asks, 'mid': mid, 'spread_bps': spread_bps,
            'best_bid': bb, 'best_ask': ba,
        }
    return out


def _synthesize_orders(books: Dict[str, Dict[str, dict]], balances: List[dict], n: int = 10) -> List[dict]:
    """When the dataset has no `orders`, build a deterministic set of test orders
    from the assets present in market_data + the available balances."""
    assets = set()
    for venue_books in books.values():
        for a in venue_books:
            assets.add(a)
    if not assets:
        return []
    asset_list = sorted(assets)
    orders = []
    for i in range(n):
        a = asset_list[i % len(asset_list)]
        side = 'buy' if i % 2 == 0 else 'sell'
        # arrival price = first venue's mid for this asset
        ap = next((b.get('mid', 100) for v in books.values() for k, b in v.items() if k == a), 100)
        # quantity scaled by the size of available_balances
        bal_for = next((float(b.get('free', 1)) for b in balances if b.get('asset', '').startswith(a.split('-')[0])), 1)
        qty = max(0.01, bal_for * 0.1) if side == 'sell' else max(0.01, bal_for * 0.05)
        orders.append({
            'order_id': f'O{i+1:04d}',
            'client_id': f'CLT{(i % 5) + 1:03d}',
            'asset': a,
            'side': side,
            'quantity': qty,
            'arrival_price': float(ap),
            'urgency': ['low', 'medium', 'high', 'critical'][i % 4],
            'max_slippage_bps': [15, 25, 40, 60][i % 4],
            'time_in_force_sec': [30, 60, 120, 300, 600][i % 5],
            'min_fill_pct': 0.95,
        })
    return orders


def to_internal(raw: Dict[str, Any]) -> Dict[str, Any]:
    # ---------- VENUES ----------
    if raw.get('venue_catalogue'):
        venues_in = raw.get('venue_catalogue') or []
        lat = raw.get('venue_latency_ms') or {}
        venues = [{
            'id': v.get('id'), 'name': v.get('name', v.get('id')),
            'type': v.get('type', 'exchange'), 'tier': v.get('tier', 'mid'),
            'fee_taker_bps': float(v.get('fee_taker_bps', 10)),
            'fee_maker_bps': float(v.get('fee_maker_bps', 0)),
            'rebate_bps': float(v.get('rebate_bps', 0)),
            'latency_ms': float(lat.get(v.get('id'), v.get('latency_ms', 30))),
            'quality_w': float(v.get('quality_w', 0.5)),
        } for v in venues_in]
    else:
        venues = _venues_from_legacy(raw.get('venues_list') or raw.get('venues') or [], raw.get('venue_latency_ms') or {})

    # ---------- BOOKS ----------
    md = (raw.get('market_data') or {})
    books: Dict[str, Dict[str, dict]] = {}
    if isinstance(md.get('venues'), dict):
        for vid, by_a in md['venues'].items():
            books[vid] = {a: {
                'bids': b.get('bids') or [], 'asks': b.get('asks') or [],
                'mid': float(b.get('mid', 0)), 'spread_bps': float(b.get('spread_bps', 10)),
                'best_bid': float(b.get('best_bid', 0)), 'best_ask': float(b.get('best_ask', 0)),
            } for a, b in (by_a or {}).items()}
    elif isinstance(md.get('books'), list):
        books = _books_from_legacy(md['books'])

    # ---------- ORDERS ----------
    orders = raw.get('orders') or []
    if not orders:
        balances = (raw.get('inventory_and_limits') or {}).get('available_balances') or []
        orders = _synthesize_orders(books, balances, n=10)
    orders = [_normalize_order(o) for o in orders]

    inv = raw.get('inventory_and_limits') or {}
    rc = raw.get('routing_constraints') or {}
    obj = (raw.get('objective') or {}).get('weights') or {}
    # legacy credit_limits -> credit_lines_usd
    credit_lines = inv.get('credit_lines_usd')
    if not credit_lines and isinstance(inv.get('credit_limits'), list):
        credit_lines = {c.get('venue_id'): float(c.get('max_gross_exposure', 1e7)) for c in inv['credit_limits']}

    return {
        'orders': orders, 'venues': venues, 'books': books,
        'limits': {
            'venue_credit_usd': credit_lines or {},
            'total_notional_cap_usd': float(inv.get('total_notional_cap_usd', 1e9)),
            'position_caps_usd': inv.get('position_caps_usd') or {},
            'max_market_impact_bps': float(inv.get('max_market_impact_bps', 100)),
        },
        'routing': {
            'venue_eligibility': rc.get('venue_eligibility') or {},
            'max_venues_per_order': int(rc.get('max_venues_per_order', 4)),
            'min_venues_per_order': int(rc.get('min_venues_per_order', 1)),
            'allow_dark_pools': bool(rc.get('allow_dark_pools', True)),
        },
        'obj_weights': {k: float(obj.get(k, d)) for k, d in [
            ('slippage', 0.4), ('fees', 0.15), ('market_impact', 0.25),
            ('price_discovery', 0.10), ('fill_probability', 0.10)
        ]},
        'horizon_s': int(raw.get('optimization_horizon_seconds', 60)),
        'base_currency': raw.get('base_currency', 'USD'),
        'random_seed': int(raw.get('random_seed', 42)),
        'warm_start': raw.get('previous_routing'),
    }


def validate(internal):
    if not internal['orders']:
        raise ValueError('No orders (none in payload and none could be synthesized from balances/books).')
    if not internal['venues']:
        raise ValueError('No venues (neither venue_catalogue nor venues_list).')
    if not internal['books']:
        raise ValueError('No market data (neither market_data.venues nor market_data.books).')

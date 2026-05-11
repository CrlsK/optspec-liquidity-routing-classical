"""Classical liquidity router — greedy baseline (v1.0). Pyomo + HiGHS PWL refinement to come in v1.1."""
from __future__ import annotations
import hashlib, json, os, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from adapter import to_internal, validate
from kpi_compute import compute_kpis
from additional_output_generator import generate_additional_output

SOLVER_VERSION = '1.0.0-classical-greedy'
ALGORITHM_NAME = 'GreedyRouter_BestPriceFirst_v1'

def solver(input_data, **kwargs):
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat()
    raw = (input_data or {}).get('data', input_data) or {}
    dsha = hashlib.sha256(json.dumps(input_data, sort_keys=True, default=str).encode()).hexdigest()
    Path(os.environ.get('ADDITIONAL_OUTPUT_DIR', './additional_output')).mkdir(parents=True, exist_ok=True)
    try:
        internal = to_internal(raw); validate(internal)
    except Exception as e: return _err('adapter', e, started, t0, dsha)
    try:
        fills = _greedy(internal)
    except Exception as e: return _err('solver', e, started, t0, dsha)
    wall = time.perf_counter() - t0
    kpis = compute_kpis(internal['orders'], fills, internal['venues'])
    rp = _plan(fills)
    obj_val = (internal['obj_weights']['slippage'] * abs(kpis['realized_slippage_bps'])
               + internal['obj_weights']['fees'] * kpis['total_fees_bps']
               + internal['obj_weights']['market_impact'] * kpis['market_impact_bps']
               - internal['obj_weights']['price_discovery'] * kpis['price_discovery_score'] * 100)
    res = {**kpis,
           'benchmark': {'execution_cost': {'value': round(wall*0.5, 4), 'unit': 'credits'}, 'time_elapsed': f'{wall:.1f}s', 'energy_consumption': 0.0},
           'status': 'success', 'solution_status': 'feasible' if fills else 'infeasible',
           'routing_plan': rp,
           'execution_instructions': [{'instruction_id': f'EX-{i+1:05d}', **{k: f[k] for k in ('order_id','venue_id','asset','side','quantity')}, 'limit_price': f['exec_price'], 'time_in_force_sec': 60} for i, f in enumerate(fills)],
           'expected_kpis': kpis, 'objective_value': round(obj_val, 4),
           'constraint_report': {'binding': [], 'violations': []},
           'solver_diagnostics': {'solver_version': SOLVER_VERSION, 'algorithm': ALGORITHM_NAME, 'wall_time_s': round(wall, 3),
                                  'n_orders': len(internal['orders']), 'n_venues': len(internal['venues']), 'n_fills': len(fills)},
           'errors': [], 'run_id': raw.get('run_id', dsha[:12]),
           'audit': {'solver_version': SOLVER_VERSION, 'dataset_sha256': dsha, 'run_started_at_utc': started,
                     'run_finished_at_utc': datetime.now(timezone.utc).isoformat(),
                     'platform_use_case': 'optimized-liquidity-routing-across-diversified-digital-asset-markets'},
           '_fills': fills}
    try: generate_additional_output(raw, res, algorithm_name=ALGORITHM_NAME)
    except Exception: pass
    res.pop('_fills', None)
    return {'result': res}

def run(data, solver_params=None, extra_arguments=None):
    return solver({'data': data})['result']

def _greedy(internal):
    fills = []
    used = {v['id']: 0.0 for v in internal['venues']}
    elig = internal['routing'].get('venue_eligibility') or {}
    max_v = internal['routing'].get('max_venues_per_order', 4)
    for o in internal['orders']:
        sym, side = o['asset'], o['side']
        qty = float(o['quantity'])
        cands = []
        for v in internal['venues']:
            if not elig.get(v['id'], {}).get('enabled', True): continue
            b = (internal['books'].get(v['id']) or {}).get(sym)
            if not b: continue
            lvls = b['asks'] if side == 'buy' else b['bids']
            if not lvls: continue
            fee = v['fee_taker_bps']
            top = lvls[0]['price']
            eff = top * (1 + fee/10000.0) if side == 'buy' else top * (1 - fee/10000.0)
            cands.append((eff if side == 'buy' else -eff, v, lvls))
        cands.sort(key=lambda x: x[0])
        uv = 0
        for _, v, lvls in cands:
            if uv >= max_v or qty <= 1e-9: break
            for lvl in lvls:
                if qty <= 1e-9: break
                take = min(qty, float(lvl['size']))
                if take <= 1e-9: continue
                notional = take * float(lvl['price'])
                cap = float((internal['limits'].get('venue_credit_usd') or {}).get(v['id'], 5_000_000))
                if used[v['id']] + notional > cap:
                    take = max(0, (cap - used[v['id']]) / float(lvl['price']))
                    if take <= 1e-9: break
                used[v['id']] += take * float(lvl['price'])
                fills.append({'order_id': o['order_id'], 'venue_id': v['id'], 'asset': sym, 'side': side,
                              'quantity': round(take, 6), 'exec_price': round(float(lvl['price']), 6),
                              'fee_bps': float(v['fee_taker_bps']), 'alpha': 0.0, 'beta': 0.0,
                              'venue_quality_w': float(v['quality_w'])})
                qty -= take
            uv += 1
    return fills

def _plan(fills):
    agg = {}
    for f in fills:
        k = (f['order_id'], f['venue_id'])
        if k not in agg:
            agg[k] = {'order_id': f['order_id'], 'venue_id': f['venue_id'], 'asset': f['asset'], 'side': f['side'],
                      'allocated_quantity': 0.0, 'expected_price': 0.0, 'expected_fee_bps': f['fee_bps']}
        agg[k]['allocated_quantity'] += f['quantity']
        agg[k]['expected_price'] = max(agg[k]['expected_price'], f['exec_price'])
    return list(agg.values())

def _err(phase, exc, started, t0, dsha):
    wall = time.perf_counter() - t0
    return {'result': {'realized_slippage_bps': 0, 'fill_rate_pct': 0, 'total_fees_bps': 0, 'market_impact_bps': 0,
                       'price_discovery_score': 0, 'venue_switches': 0,
                       'benchmark': {'execution_cost': {'value': 0, 'unit': 'credits'}, 'time_elapsed': f'{wall:.1f}s', 'energy_consumption': 0.0},
                       'status': 'error', 'solution_status': 'error',
                       'routing_plan': [], 'execution_instructions': [], 'expected_kpis': {}, 'objective_value': None,
                       'constraint_report': {}, 'errors': [{'phase': phase, 'error_type': type(exc).__name__, 'error_message': str(exc), 'traceback': traceback.format_exc()}],
                       'solver_diagnostics': {'solver_version': SOLVER_VERSION},
                       'audit': {'dataset_sha256': dsha, 'run_started_at_utc': started, 'run_finished_at_utc': datetime.now(timezone.utc).isoformat()}}}

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f: inp = json.load(f)
    else: inp = {'data': {'orders': [], 'venue_catalogue': [], 'market_data': {'venues': {}}}}
    print(json.dumps(solver(inp), indent=2, default=str))

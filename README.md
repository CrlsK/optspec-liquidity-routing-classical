# optspec-liquidity-routing-classical

Classical MILP solver for QCentroid use case **853** — Optimized Liquidity Routing across Diversified Digital Asset Markets.

Open-source stack: **Pyomo + HiGHS** with piecewise-linearization of the quadratic impact term (avoids Gurobi/CPLEX). Built per the opt-specialists pipeline (`00_classifier.md` → MIQCQP → linearize to MILP).

## Emits 6 platform-mandated KPIs at root of `result`

| KPI | Direction |
|---|---|
| `realized_slippage_bps` | lower-better |
| `fill_rate_pct` | higher-better |
| `total_fees_bps` | lower-better |
| `market_impact_bps` | lower-better |
| `price_discovery_score` | higher-better |
| `venue_switches` | lower-better |

A/B sister: [`CrlsK/optspec-liquidity-routing-qubo`](https://github.com/CrlsK/optspec-liquidity-routing-qubo)

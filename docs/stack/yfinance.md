# yfinance

**Package:** `yfinance`  •  **Version pin:** `>=0.2.40`  •  **Extras group:** `m3xa-core[markets]`  •  **Role:** Optional market data for the agent hub

## What it does

Scrapes Yahoo Finance for tickers, prices, and basic fundamentals. The `MarketsAgent` in `m3xa_core/actors/agent_hub.py` uses it to attach live BRL/SELIC/Ibovespa context when the query is about Brazilian markets.

## Where it's used in m3xa-core

- `m3xa_core/actors/agent_hub.py` — `MarketsAgent.fire()` runs only if the classifier flagged a markets-relevant topic. Lazy import inside the method so the agent hub can construct without the extra installed.

## Why we picked it

- Free.
- No API key.
- Good enough for the reference demo. **Not suitable for production** — Yahoo throttles aggressively and the unofficial API breaks periodically.

## Alternatives considered

| Alternative | Why we didn't pick it |
|---|---|
| Tiingo (paid) | What our production stack uses. Adds an API key requirement that's wrong for a reference repo. |
| `pyield` (Brazilian fixed-income) | Solid for Brazilian rates but narrower scope. Could co-exist as a second markets source. |
| Direct B3 / BCB APIs | Better long-term; more setup than a reference demo deserves. |

## How to swap it out

`MarketsAgent` is a single class. Subclass or replace it; register your version via `hub.register(YourMarketsAgent())`.

## Links

- GitHub: <https://github.com/ranaroussi/yfinance>
- Last verified: 2026-05-19

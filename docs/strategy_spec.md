# Strategy Specification

This document formalizes the first version of the relative-strength strategy.

## Philosophy

The portfolio should stay simple:

- concentrated exposure to the strongest asset or assets;
- cash only when the entire universe is in absolute downtrend;
- slow rotations when possible;
- fast enough reaction when leadership clearly changes;
- equal-weight allocations only.

## Absolute Cash Defense

Cash is allowed only when every tracked asset is simultaneously:

- below EMA 35;
- below SMA 100;
- below SMA 200.

This prevents the system from going to cash just because relative leadership is
unclear.

## Relative Leadership

Leadership is evaluated through a pairwise ratio matrix. For an `N` asset
universe, each asset is compared with the other `N - 1` assets.

For each ratio `A / B`, the signal for A versus B uses four criteria:

- ratio above EMA 35;
- ratio above SMA 100;
- ratio above SMA 200;
- EMA 35 rising over 10 sessions.

The ratio is a win when the score is clearly positive, a loss when it is clearly
negative, and neutral when the evidence is too close to call.

## SMA200 Entry Filter

By default, an asset cannot become a new target allocation while it trades below
its own SMA 200. The relative-strength matrix can still rank that asset, but the
portfolio-selection step rejects it.

If no active asset is above its SMA 200 and the full cash-defense rule has not
triggered, the target allocation becomes cash by entry filter.

The default production setting requires one positive absolute trend point, which
matches the SMA 200 filter. Research scenarios can raise this threshold to two
or three positive trend points to test stricter absolute-trend confirmation.

## Research Universes

The recommended live-research universe is `universe_recommended.toml`: BTC,
GLD, SLV, SMH, QQQ, and SPY. It intentionally excludes ETH and global country
ETFs because the current research sweep shows better performance and cleaner
drawdown behavior with the core ETF set plus Bitcoin.

The recommended research configuration requires the leader to be above EMA35,
SMA100, and SMA200, uses a strict leader threshold, and uses a biweekly decision
frequency. Live monitoring can still run weekly, but this configuration records
the current best backtested execution cadence for the recommended universe.

Additional research universes are available for longer-window tests:

- `universe_core_etf_2010.toml` removes crypto so the backtest can start in
  2010;
- `universe_global_etf_2010.toml` adds USD-listed country ETF proxies for
  France, Germany, UK, Japan, Hong Kong, and South Korea;
- `universe_global_usd.toml` combines the global ETF set with BTC and ETH, but
  naturally starts later because ETH history begins later.

## Range Handling

Many neutral pairs imply range or transition behavior. The report should lower
conviction in that case, even if it still proposes a target allocation.

## Holding Period

Both the live report and backtest use a minimum holding period of 28 days for
medium- and low-conviction rotations. A challenger must also beat the incumbent
directly in their pair ratio before a rotation is accepted. A neutral direct
ratio keeps the incumbent even if the challenger ranks first through indirect
wins elsewhere in the matrix.

The model can still rotate earlier when:

- the target becomes cash;
- the current allocation is cash;
- the incumbent no longer passes the entry filter;
- the challenger wins directly and the new signal has high conviction.

This is intentionally simple. It reflects the desired behavior: avoid noisy
weekly churn, but do not wait through a major leadership break.

## Weekly Timing

The default simulation uses:

- signal date: Friday close;
- execution date: next business day;
- default execution proxy: Monday.

The live process should run before the US market open on Monday so any manual
execution can happen around the US session open.

For mixed crypto/ETF data, the research dataset is aligned to a common close
calendar. Crypto weekend closes are not used to create synthetic ETF execution
dates.

## Open Questions

- What should be the first production-grade data provider after `yfinance`?
- Should crypto weekend data affect the Friday signal, or only Friday closes?
- Should reports include chart images or stay Markdown-only at first?
- Which notification channel should be used for weekly operation?
- Which stricter absolute-trend threshold, if any, survives out-of-sample data
  without overfitting to the 2020-2026 window?

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

## Range Handling

Many neutral pairs imply range or transition behavior. The report should lower
conviction in that case, even if it still proposes a target allocation.

## Flip-Flop Stabilizer

Some ranges alternate between two single-asset leaders for several weeks. The
strategy can stabilize those periods by widening the tie treatment only for the
same repeated pair:

- the recent signal window must contain exactly two single-asset leaders;
- the leaders must switch at least the configured number of times;
- both assets must still pass the entry filter;
- their relative-strength scores must remain within the normal tie tolerance
  plus the configured flip-flop tolerance boost.

When those conditions are met, the target allocation becomes `50% / 50%` for the
two assets and the regime is marked as `stabilized_range`.

## Holding Period

The backtest uses a preferred minimum holding period of 28 days. It can still
rotate earlier when:

- the target becomes cash;
- the current allocation is cash;
- a flip-flop stabilized range overlaps the current allocation;
- the new signal has high conviction.

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

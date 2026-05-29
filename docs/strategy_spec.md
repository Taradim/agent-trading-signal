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

## Range Handling

Many neutral pairs imply range or transition behavior. The report should lower
conviction in that case, even if it still proposes a target allocation.

## Holding Period

The backtest uses a preferred minimum holding period of 28 days. It can still
rotate earlier when:

- the target becomes cash;
- the current allocation is cash;
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

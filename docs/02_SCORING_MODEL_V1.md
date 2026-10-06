# Gold Signal — Scoring Model v1.0.0

Status: **DRAFT FOR REVIEW**. Once approved, the parameters are frozen. Any later change creates a new
model version (v1.1.0, …). Backtests and stored signals always record the version they used.

Executable reference: [`scoring_v1_reference.py`](scoring_v1_reference.py). Every number in §11 comes
from running it. The production engine must reproduce those numbers exactly; that's a unit test.

---

## 0. Design rules

1. **Changes, not levels** (one exception, §6.2): the model scores direction, magnitude and persistence of
   moves, standardized by each series' typical move size.
2. **Noise is ignored explicitly.** A move smaller than ¼ of a typical move contributes exactly 0.
3. **Bounded and saturating.** Every component lives in (−1, +1). One indicator can never contribute
   more than its weight, no matter how extreme.
4. **Price is not an input.** The gold price is never used in the score, so the score doesn't chase
   momentum and can't explain gold with gold. Price is used only for panic detection and for backtest P&L.
5. **Stale data decays to neutral.** It never quietly keeps contributing.
6. **Signal ≠ score.** The score moves every day. The signal changes only after hysteresis confirms it.
7. **Confidence ≠ probability.** It measures model agreement, data quality and persistence.
8. **Point-in-time.** Every input carries an `available_at` timestamp, and the engine sees only data with
   `available_at ≤ evaluation time`. Live and backtest use the same code path.

---

## 1. Primitives

**Horizon change.** For a series `x` evaluated at time `t` and horizon `h ∈ {1D, 7D, 30D}` (calendar days):

```
t_h      = date of the latest valid observation ≤ (t − h)        # for 1D: the previous observation
Δ_h      = x(t) − x(t_h)                    # yields & rates, in basis points
Δ_h      = 100 · ln( x(t) / x(t_h) )        # prices, indices, FX, ETF holdings, in %
```

**Soft dead-zone** (d = 0.25):

```
soft(z) = sign(z) · max(|z| − 0.25, 0)
```

**Squash** (κ = 2):

```
sq(z) = tanh( soft(z) / 2 )
```

| standardized move z | 0.2 | 0.5 | 1.0 | 1.5 | 2.0 | 3.0 | 5.0 |
|---|---|---|---|---|---|---|---|
| sq(z) | 0.000 | 0.124 | 0.358 | 0.556 | 0.704 | 0.880 | 0.983 |

So one typical move gives a moderate signal (≈0.36), two give a strong one (≈0.70), and the signal saturates
after that.

**Multi-horizon trend score:**

```
T(x; dir, σ, ω) = Σ_h  ω_h · sq( dir · Δ_h / σ_h )          ∈ (−1, +1)
```

- `dir = −1` if a rising series is bearish for gold, `+1` if it is bullish.
- `σ_h` is the **reference typical move** for that horizon: a fixed v1 constant, roughly one standard
  deviation of h-day changes over 2010–2024, rounded.
- Default horizon weights `ω = (1D 0.20, 7D 0.30, 30D 0.50)`.

**Freshness factor** (age in business days on the series' own holiday calendar):

```
f = 1                                   if age ≤ fresh
f = (hard − age) / (hard − fresh)       if fresh < age < hard
f = 0                                   if age ≥ hard or no data
```

---

## 2. Component formulas

Each component `i` produces `s_i ∈ (−1, +1)` (positive = favorable for gold).

### 2.1 Real Yield — weight 30 (US 10Y TIPS yield, FRED `DFII10` / Treasury real curve)

```
s_RY = T(real10y; dir = −1, σ = (5, 12, 25) bp, ω = (0.2, 0.3, 0.5))
```

Falling real yields are bullish. A 1-bp daily wiggle (z = 0.2) contributes 0. A 28-bp fall over 30 days
(z = 1.12) contributes strongly.

### 2.2 Fed Expectations — weight 20

Inputs (two things kept strictly separate, and the app shows them separately):

- **Current Fed policy:** target range `[L, U]`, midpoint `mid = (L+U)/2`, and EFFR.
- **Market-implied policy:** `r3m`, `r6m`, `r12m`. V1 default source is the T-bill curve (FRED `DGS3MO`,
  `DGS6MO`, `DGS1`), a free, daily, reliable proxy for the expected average policy rate. A fed-funds-futures
  or OIS provider can be plugged in later behind the same interface (`method` field records which was used).

```
P            = (r6m + r12m) / 2                          # the "expected path" point
repricing    = T(P; dir = −1, σ = (4, 10, 22) bp, ω = (0.2, 0.3, 0.5))
priced_12m   = (r12m − mid) · 100                        # bp; negative = cuts priced
stance       = sq( −priced_12m / 50 )
s_FED        = 0.7 · repricing + 0.3 · stance
```

70% of the weight sits on the **change** in expectations, which is what moves gold. 30% sits on how much easing is
already priced. The T-bill vs fed funds basis (typically ±5–15 bp) mostly falls inside the dead-zone
(¼ × 50 bp = 12.5 bp).

### 2.3 DXY — weight 15

```
s_DXY = T(DXY; dir = −1, σ = (0.45, 1.0, 2.1) %, ω = (0.2, 0.3, 0.5))
```

### 2.4 US 10Y Nominal Yield — weight 10 (de-duplicated)

**Double-counting rule.** `nominal = real + breakeven`. The real-yield part of any nominal move is
**already scored in §2.1**, so this component never scores the raw nominal change. It scores only the
information the real-yield engine doesn't have:

```
breakeven       = DGS10 − DFII10                                  # inflation expectations
be_trend        = T(breakeven; dir = +1, σ = (3, 7, 15) bp)       # rising inflation expectations: supportive
z_level         = (DGS10 − mean_252d(DGS10)) / max(std_252d(DGS10), 10 bp)
level_pressure  = sq( −z_level )                                  # nominal yield elevated vs its 1y norm: headwind
s_10Y           = 0.6 · be_trend + 0.4 · level_pressure
```

Example: the nominal 10Y rises 18 bp with real yields up 3 bp. The real engine sees a small move (≈neutral).
This engine sees +15 bp of breakeven (mildly bullish) against a higher nominal level (mildly bearish). Nothing
is counted twice. This is the one place the model looks at a **level**, and it's relative to the series' own
trailing year, so it adapts across rate regimes.

### 2.5 US Economic Data — weight 10 (surprise-based)

For each release `j` with `release_time ≤ t` and age ≤ 60 days:

```
surprise_j = actual_j − consensus_j                  # consensus captured BEFORE release
z_j        = surprise_j / σ_j
e_j        = I_j · g_j · sq(z_j)                     # g = gold direction, I = importance
d_j        = 0.5 ^ (age_days_j / 14)                 # 14-day half-life
s_ECON     = Σ e_j·d_j  /  max( Σ I_j·d_j , 2.0 )
```

The `max(…, 2.0)` floor keeps a single release from saturating the component.

| Code | Release | σ (typical surprise) | g | I |
|---|---|---|---|---|
| CPI_YOY | CPI y/y | 0.1 pp | −1 (hot inflation → hawkish → bearish) | 0.7 |
| CORE_CPI_MOM | Core CPI m/m | 0.1 pp | −1 | 1.0 |
| PCE_YOY | PCE y/y | 0.1 pp | −1 | 0.5 |
| CORE_PCE_MOM | Core PCE m/m | 0.1 pp | −1 | 0.8 |
| NFP | Nonfarm payrolls | 75 K | −1 (strong jobs → bearish) | 1.0 |
| UNEMPLOYMENT | Unemployment rate | 0.1 pp | +1 (higher UR → easing → bullish) | 0.8 |
| INITIAL_CLAIMS | Weekly initial claims | 15 K | +1 | 0.3 |
| ISM_MFG | ISM Manufacturing | 2.0 pts | −1 | 0.5 |
| ISM_SERVICES | ISM Services | 2.0 pts | −1 | 0.5 |

Your two examples: NFP 30K vs 100K expected gives z = −0.93, so `e = 1.0 · (−1) · sq(−0.93) = +0.33` (bullish).
CPI 3.5% vs 3.1% gives z = +4.0, so `e = 0.7 · (−1) · 0.95 = −0.67` (bearish).

Stored per release: `previous, consensus, actual, surprise, z, impact, release_time, status`.
**Point-in-time:** the backtest uses the **first-print** actual and the consensus as captured before release,
never revised values.

### 2.6 Gold ETF Flows — weight 10 (slow by construction)

`H` = combined holdings in tonnes of physically backed ETFs (v1: GLD + IAU; more where data is reliable).

```
s_ETF = T(H; dir = +1, horizons = (7D, 30D, 90D), σ = (1.0, 2.5, 5.0) %, ω = (0.1, 0.5, 0.4))
```

There's no 1-day horizon and 90% of the weight sits on 30D/90D, so ETF data can't drive the daily signal.

> **Data note (2026-10-07).** The live service feeds this component with SPDR GLD holdings only (the one free
> daily series with history). GLD moves about twice as much in % terms as the global aggregate the sigmas
> were set for, so the component saturates more often. The parameters are frozen; whether to widen the
> sigmas is a v1.1 decision.

### 2.7 Central Bank Purchases — weight 5 (long-term)

Monthly net official-sector purchases in tonnes (WGC/IMF), keyed by **publication date**, not reference month.

```
T12   = trailing 12-month net purchases (t)
T3    = trailing 3-month net purchases (t)
s_CB  = 0.7 · sq( (T12 − 500) / 250 )  +  0.3 · sq( (4·T3 − T12) / 400 )
```

500 t/yr is the 2010–2021 baseline. The component updates monthly, and with weight 5 its total swing is
±2.5 points.

> **Data note (2026-10-07).** The live service uses holdings *reported to the IMF* (International Liquidity
> dataset, all reporting countries). Over 2010–2021 these match the WGC series the baseline was set on; from
> 2022 the WGC adds large estimates of unreported buying that this series does not contain, so recent
> "reported" purchases (~300–400 t/yr) read as below baseline. The indicator says so in the app.

---

## 3. Aggregation

```
s_eff_i   = f_i · s_i                                # stale data fades to neutral
points_i  = w_i · (1 + s_eff_i) / 2                  # ∈ [0, w_i]; neutral = w_i / 2
tilt_i    = points_i − w_i / 2                       # ∈ [−w_i/2, +w_i/2]
GoldScore = Σ points_i                               # ∈ [0, 100]; neutral = 50
```

**Display note (a deviation from your example):** showing "Real Yield +24" for a component whose neutral value
is 15 would mislead users. The UI shows **`20 / 30`** with a bar centered on the neutral midpoint, plus the signed
tilt (`+5.0`). The points still add up exactly to the Gold Score, so it stays fully decomposable.

**Bands:** 75–100 STRONG BUY · 60–74.9 BUY · 40–59.9 HOLD · 25–39.9 REDUCE · 0–24.9 SELL.

**Determinism:** component outputs are rounded to 4 decimals, points to 2 and the score to 1, so results are
identical across CPUs and languages.

---

## 4. Signal hysteresis (confirmation logic)

There is **one official evaluation per US trading day at 23:30 UTC**. Intraday refreshes update prices and a
*provisional* score but never change the signal.

```
Let S = current confirmed signal with band [lo, hi).
Upgrade candidate    if score ≥ hi + 3
Downgrade candidate  if score <  lo − 3
pending_days = pending_days + 1 if the candidate is in the same direction as yesterday's, else 1
               reset to 0 when there is no candidate
Confirm (S := band(score)) when pending_days ≥ 3,
       or immediately if the score is ≥ 10 points beyond the boundary ("decisive").
```

The new signal is the band the score is actually in, so it may skip a band.
Holidays produce no evaluation and don't count as a day.

Demo (from the reference script):

| Day | Score | Raw band | Confirmed | Pending |
|---|---|---|---|---|
| 1 | 58.0 | HOLD | HOLD | — |
| 2 | 61.5 | BUY | HOLD | — (inside the 3-pt buffer) |
| 3 | 64.2 | BUY | HOLD | ↑ 1 |
| 4 | 62.8 | BUY | HOLD | reset (fell back inside the buffer) |
| 5 | 63.4 | BUY | HOLD | ↑ 1 |
| 6 | 65.1 | BUY | HOLD | ↑ 2 |
| 7 | 66.0 | BUY | **BUY** | confirmed |
| 9 | 59.0 | HOLD | BUY | — (BUY keeps until < 57) |
| 10 | 56.5 | HOLD | BUY | ↓ 1 |
| 11 | 47.0 | HOLD | **HOLD** | decisive (13 pts below 60) |

The app shows pending state explicitly ("BUY pending — 2 of 3 days").

---

## 5. Confidence (model confidence, not probability of return)

```
strength = Σ w_i |s_eff_i|
A  (agreement)   = |Σ w_i s_eff_i| / strength            (0 if strength ≈ 0)
M  (magnitude)   = min(1, (strength / 100) / 0.5)
F  (freshness)   = Σ w_i f_i / 100
P  (persistence) = min(1, days_in_band / 10)   # consecutive official evals with raw band == confirmed signal
C  = 100 · F · (0.40·A + 0.30·M + 0.30·P) · (0.6 if regime = PANIC else 1)
If any critical component (Real Yield, Fed, DXY) has f = 0:  C = min(C, 40), status = DATA_DELAYED
```

UI label, always: **"Model confidence — not probability of future return."**

A HOLD with every indicator near zero gets low confidence ("nothing decisive"). A HOLD caused by strong
conflicting indicators also gets low confidence, through A.

---

## 6. Regime detection

### 6.1 Panic / liquidity shock trigger (any one)

| Rule | Threshold |
|---|---|
| VIX level | ≥ 35 |
| VIX spike | VIX ≥ 25 and 5-day change ≥ +50% |
| Gold daily move | \|1D\| ≥ 4% |
| Forced liquidation | gold 5D ≤ −6% and VIX ≥ 25 |
| Dollar squeeze | DXY 1D ≥ +1.5% |

VIX (FRED `VIXCLS`) is an auxiliary series. It's never scored.

### 6.2 Candidate regime

```
Major = {Real Yield, Fed, DXY, 10Y, Econ}            (weights sum to 85)
bull_breadth = Σ_major w_i · [s_eff_i > +0.15] / 85
bear_breadth = Σ_major w_i · [s_eff_i < −0.15] / 85
Δ20 = score − score 20 official evaluations ago

PANIC       if a trigger fires
GOLD BULL   if bull_breadth ≥ 0.6 and score ≥ 55 and Δ20 > −12
GOLD BEAR   if bear_breadth ≥ 0.6 and score ≤ 45 and Δ20 < +12
TRANSITION  otherwise   (mixed, or the score is moving sharply against the regime)
```

**Confirmation:** PANIC is entered immediately and exited only after 5 consecutive evaluations with no trigger.
Any other change needs the same candidate for 3 consecutive evaluations.

---

## 7. Turkish Gram Gold

```
GramGold_TRY = XAUUSD / 31.1034768 × USDTRY
ln(gram) = ln(XAUUSD) + ln(USDTRY) − ln(31.1035)      → gram return = gold return + USD/TRY return (exact, log)
```

The app shows this decomposition directly, for example "Gram gold 30D +3.9% = gold +2.1% + USD/TRY +1.8%".

**FX leg, carry-adjusted.** USD/TRY trends up almost every month, so a naive "USD/TRY rising = bullish" rule
would keep gram gold on BUY forever. The real question for a Turkish investor is whether the lira is weakening
**faster than TRY deposits compensate for**:

```
X_h  = 100·ln(USDTRY_t / USDTRY_{t_h})  −  (i_TRY − i_USD) · days_h / 365         # % excess depreciation
s_FX = T(X; dir = +1, σ = (0.5, 1.2, 2.5) %, ω = (0.2, 0.3, 0.5))
```

Here `i_TRY` is the TCMB one-week repo rate (EVDS, or config default) and `i_USD` is the Fed midpoint.

**Gram score: additive tilt, not an average.**

```
GramScore = clamp( GlobalScore + 25 · f_FX · s_FX , 0, 100 )
```

A weighted average would drag a neutral FX leg toward 50 and dilute a valid global signal. With the tilt, a
neutral lira leaves the global view intact, and a lira under real stress can lift gram gold by up to 25 points.
Gram gold uses the same bands and the same hysteresis, but keeps its own state.

```
Gram confidence = GlobalConfidence · (0.7 + 0.3·agree) · f_FX
agree = 0 if the gold leg and FX leg point in opposite directions (each beyond its neutral zone), else 1
```

Contrast case from the reference: **global 31 (REDUCE)** while USD/TRY outruns carry by 6.15% over 30 days
(s_FX = 0.74). **Gram = 49.6, so HOLD and not SELL.** The Why screen states both drivers explicitly.

Market gram gold (Kapalıçarşı/bank quote) is optional. When a licensed source is configured, the app shows its
premium versus theoretical: `market / theoretical − 1`.

---

## 8. Explanations ("Why?")

Explanations are **generated from model outputs as structured reason codes**. They aren't free text, so the app can
render them in EN/TR/RU from the same data.

```
Positive factors:  components with s_eff ≥ +0.15, sorted by tilt (descending)
Negative factors:  components with s_eff ≤ −0.15, sorted by |tilt|
Neutral:           |s_eff| < 0.15 → "little changed"
Magnitude word:    |s| < 0.15 little · < 0.45 moderately · < 0.75 significantly · else sharply
Sub-reasons:       the dominant horizon/sub-score with its actual numbers (e.g. 30D −28 bp)
Data warnings:     every component with f < 1, every DELAYED release
Conclusion code:   from (signal, regime, #positive vs #negative weight, strongest negative factor)
```

Example code: `{"code":"REAL_YIELD_FALLING","magnitude":"MODERATE","params":{"d30_bp":-28,"d7_bp":-11}}`.
Android template (EN): "Real yields have fallen moderately: −28 bp over 30 days."

---

## 9. Alert rules (server-side, deduplicated per day and type)

| Type | Rule |
|---|---|
| SIGNAL_CHANGED | the confirmed global or gram signal changes |
| SCORE_MOVE | \|score − score 5 evaluations ago\| ≥ 10 |
| REGIME_CHANGED | the confirmed regime changes |
| MACRO_RELEASE | release with I ≥ 0.7 published (includes surprise and impact) |
| FED_DECISION | FOMC decision recorded (change in bp vs what was priced) |
| EXTREME_EVENT | a panic trigger fires |
| DATA_DELAYED | a critical component reaches f = 0 (in-app only, no push) |

---

## 10. Backtest rules (look-ahead safe)

- Evaluate each US trading day at 23:30 UTC using only rows with `available_at ≤ eval_time`. Historical
  `available_at` = observation date + each source's documented publication lag (conservative).
- 400-day warm-up before the start date, used to initialize the 252-day statistics and hysteresis state. There is no trading during warm-up.
- **Execution:** a signal at day t's close is traded at the **close of t+1**.
- **Position (v1 binary):** STRONG BUY/BUY → 100% gold · REDUCE/SELL → 0% · HOLD → keep the current position.
  A HOLD at the start means starting in cash.
- Cash earns the 3M T-bill rate. Costs are 10 bp per side by default (configurable).
- Trade = entry to exit round trip. Metrics: final value, total return, CAGR, max drawdown, # trades, win rate,
  average gain, average loss, best/worst trade, % time invested, and the same metrics for Buy & Hold.
- Every result records `model_version`, `params_sha256` and **data coverage** (for example, "consensus data
  unavailable before 2014: Econ component neutral on 31% of days").
- **No tuning to the backtest.** v1.0.0 parameters were set a priori (above) and frozen on approval.
  Anything evaluated after the freeze date is true out-of-sample. Any change means a new version, and old
  results are kept.

---

## 11. Worked example (illustrative mock market, evaluated 2026-10-02 23:30 UTC)

Inputs (mock, not real market data):

| Component | Inputs |
|---|---|
| Real yield | 1D −3 bp · 7D −11 bp · 30D −28 bp |
| Fed | target 3.50–3.75 (mid 3.625) · implied 12M 3.18% (−44.5 bp priced) · path P: 1D −2 · 7D −9 · 30D −21 bp |
| DXY | 1D −0.22% · 7D −0.85% · 30D −1.70% |
| 10Y | nominal 4.45% vs 1y mean 4.15% (σ 0.14) · breakeven 1D +1 · 7D +4 · 30D +12 bp |
| Econ | NFP +30K vs +100K · UR 4.4 vs 4.3 · claims 241K vs 228K · ISM 48.9 vs 49.6 · CPI y/y 3.0 vs 2.9 (21 days ago) · … |
| ETF | holdings 7D +0.35% · 30D +1.6% · 90D +2.9% |
| Central banks | T12 = 780 t · T3 = 165 t |

Output:

| Component | s | Points | Tilt |
|---|---|---|---|
| Real Yield | +0.336 | 20.04 / 30 | +5.04 |
| Fed Expectations | +0.295 | 12.95 / 20 | +2.95 |
| DXY | +0.248 | 9.36 / 15 | +1.86 |
| 10Y Nominal | −0.181 | 4.09 / 10 | −0.91 |
| Economic Data | +0.145 | 5.72 / 10 | +0.72 |
| ETF Flows | +0.167 | 5.83 / 10 | +0.83 |
| Central Banks | +0.279 | 3.20 / 5 | +0.70 |
| **Gold Score** | | **61.2 / 100** | **BUY band** |

Confidence 68% (A 0.86 · M 0.52 · F 1.00 · P 0.60) · Regime GOLD BULL · Gram gold: 4,180.50 / 31.1035 × 49.85
= **₺6,700.15**. The FX leg is neutral (lira depreciation ≈ carry), so the gram score is **61.2, BUY**.

Generated "Why?" for this case:
> **Why is gold BUY?**
> 1. Real yields have fallen moderately: −28 bp over 30 days.
> 2. Market-implied Fed rates moved lower: −21 bp over 30 days; 44 bp of cuts priced over 12 months.
> 3. The dollar (DXY) is weakening: −1.7% over 30 days.
> 4. Gold ETF holdings are rising: +1.6% over 30 days.
> 5. Central-bank buying remains strong: 780 t over 12 months.
>
> **Neutral:** economic data is mixed (weak September payrolls, offset by a hot CPI print 3 weeks ago).
>
> **Negative factors:** the 10Y nominal yield is elevated (4.45%, 2.1σ above its 1-year average).
>
> **Conclusion:** most major macro drivers favor gold, but the elevated nominal yield remains a headwind.

**Calibration note:** a ~1σ move across all horizons gives a component s ≈ 0.35, which is why this healthy-but-
ordinary macro picture scores 61 and not 80. STRONG BUY needs roughly 1.5–2σ moves in most drivers at once, so
it should be rare. Phase 5 publishes the historical band frequencies as a sanity check, not as an optimization
target.

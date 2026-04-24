# Clickstream Behavioral Analysis

End-to-end pipeline for mining e-commerce clickstream data: funnel conversion, session behavior, RFM segmentation, predictive ML models, and CLV scoring — across ~270M events and 12M users.

---

## Project Structure

```
├── clickstream_extended.ipynb     # Main analysis notebook (sequential patterns, ML, CLV)
├── funnel_analysis_final.ipynb    # Funnel conversion analysis
├── session_analysis_final.py      # Session-level behavior analysis
├── user_analysis_final.py         # User-level RFM segmentation
```

---

## Data

**Format:** Parquet files (`*.parquet`)  
**Scale:** ~269.9M events | 12.1M unique users  
**Session definition:** Daily-proxy — one session = all events for a user within the same calendar day

**Schema:**

| Column | Type | Description |
|---|---|---|
| `event_time` | TIMESTAMP WITH TIME ZONE | Timestamp of the event |
| `event_type` | VARCHAR | `view`, `cart`, or `purchase` |
| `product_id` | BIGINT | Product identifier |
| `category_id` | BIGINT | Category identifier |
| `category_code` | VARCHAR | Human-readable category path |
| `brand` | VARCHAR | Product brand |
| `price` | DOUBLE | Product price |
| `user_id` | BIGINT | User identifier |
| `user_session` | VARCHAR | Platform-native session ID |
| `hour` | INTEGER | Hour of event (0–23) |
| `day_of_week` | INTEGER | Day of week (0=Monday) |
| `is_weekend` | INTEGER | 1 if Saturday/Sunday |
| `brand_was_missing` | INTEGER | Flag: brand was imputed |
| `category_was_missing` | INTEGER | Flag: category was imputed |

**Event type breakdown:**

| Event | Count | Share |
|---|---|---|
| view | 253,857,834 | 94.1% |
| cart | 11,870,371 | 4.4% |
| purchase | 4,150,415 | 1.5% |

---

## Analyses

### 1. Funnel Conversion (`funnel_analysis_final.ipynb`)

Computes view → cart → purchase conversion at two levels:

- **Raw event funnel** — counts all events
- **Deduplicated funnel** — unique user–product pairs (a user viewing the same product 10× counts as 1 view)

| Metric | Raw | Deduplicated |
|---|---|---|
| View → Cart | 4.68% | 4.37% |
| Cart → Purchase | 34.96% | 50.42% |
| View → Purchase | 1.63% | 2.20% |

Additional breakdowns by category, brand, price tier, and time of day.

---

### 2. Session Behavior (`session_analysis_final.py`)

Aggregates all events per user per day into session-level features and produces:

- Session summary statistics (duration, events, products per session)
- Purchase vs. non-purchase session comparison
- Session duration distribution with conversion rates per bucket
- Products viewed per session vs. conversion
- Cart abandonment rates
- Engagement level segmentation (Bounce → Very High)
- Hourly session patterns
- Weekend vs. weekday behavior

**Outputs** written to `dashboard_data_daily_proxy/`:

| File | Contents |
|---|---|
| `session_level_table.csv` | Full session-level feature table |
| `session_behavior_comparison.csv` | Purchase vs. non-purchase sessions |
| `session_duration_distribution.csv` | Duration buckets + conversion rates |
| `products_per_session.csv` | Products viewed buckets + conversion |
| `cart_abandonment.csv` | Cart abandonment breakdown |
| `session_engagement.csv` | Engagement level stats |
| `hourly_session_patterns.csv` | Hourly conversion and duration |
| `weekend_weekday_sessions.csv` | Day-type comparison |
| `session_analysis_master.json` | All results combined |
| `session_analysis/session_summary.json` | Top-level summary |

---

### 3. User RFM Segmentation (`user_analysis_final.py`)

Builds user-level aggregates and applies two segmentation approaches:

**RFM segmentation** (purchasing users only):

Scores each purchasing user on Recency, Frequency, and Monetary value using quintile ranking, then maps to named segments:

| Segment | Description |
|---|---|
| Champions | High R, F, and M |
| Loyal Customers | High frequency and monetary, moderate recency |
| Potential Loyalists | Recent with moderate engagement |
| New Customers | Recent but low frequency |
| Can't Lose Them | High value, lapsed |
| At Risk | Frequent but lapsed |
| Hibernating | Low recency and frequency |
| Price Sensitive | Low monetary |

**Behavioral segmentation** (all users):

| Segment | Criteria |
|---|---|
| Buyers | At least one purchase |
| Cart Abandoners | Added to cart, no purchase |
| Window Shoppers | 50+ views, no cart |
| Casual Browsers | 5 or fewer total events |
| Active Browsers | Everything else |

**Outputs** written to `dashboard_data_synced/`:

| File | Contents |
|---|---|
| `rfm_analysis/user_level_table.csv` | Per-user aggregate metrics |
| `rfm_analysis/user_segments.csv` | RFM segment assignments |
| `rfm_analysis/segment_characteristics.csv` | Segment-level stats |
| `behavioral_segments.csv` | Behavioral segment distribution |
| `power_user_summary.csv` | Power users (top 10% events) by segment |
| `clv_insights.json` | Revenue concentration / CLV summary |
| `rfm_analysis_master.json` | All results combined |

---

### 4. Sequential Patterns & ML (`clickstream_extended.ipynb`)

End-to-end notebook covering:

**Markov chain transition matrix**  
First-order transition probabilities across `view`, `cart`, `purchase` — computed via memory-safe rank-based self-join.

| From | To | Probability |
|---|---|---|
| cart | view | 52.7% |
| cart | purchase | 29.5% |
| purchase | view | 97.0% |
| view | view | 95.7% |

**Time-to-purchase analysis**  
Distribution of elapsed time from first event to first purchase per user.

**ML feature engineering**  
Session-level features: `views`, `carts`, `cart_to_view_ratio`, `unique_products`, `has_past_purchase`, `purchase_rate`, and more.

**Purchase probability model**  
Benchmarks XGBoost, LightGBM, Logistic Regression, and Random Forest using cross-validated ROC-AUC and Average Precision. Feature importance via SHAP.

**Cart abandonment model**  
Same model stack applied to predict abandonment probability per session.

**CLV scoring**  
Normalized CLV score and decile assignment per user based on purchase history and predicted future value.

**User segmentation**  

| Segment | Users |
|---|---|
| Browser | 7,851,237 |
| Occasional buyer | 1,255,029 |
| Cart abandoner | 958,531 |
| Dormant | 90 |

**Outputs** written to `outputs/`:

| File | Contents |
|---|---|
| `event_breakdown.csv` | Event type frequencies |
| `transition_probs.csv` | Markov transition probabilities |
| `transition_matrix.csv` | Pivoted transition matrix |
| `top_transitions.csv` | Top 10 event transitions |
| `funnel.csv` | Conversion funnel counts |
| `time_to_purchase.csv` | Raw time-to-purchase per user |
| `time_to_purchase_clean.csv` | Converted users only |
| `ml_dataset.csv` | Full feature + label dataset |
| `model_comparison.csv` | Cross-validated metrics, all models |
| `feature_importance_lgbm.csv` | LightGBM split-based importance |
| `feature_importance_rf.csv` | Random Forest importance |
| `shap_importance.csv` | SHAP mean absolute values |
| `purchase_probabilities.csv` | Per-user purchase probability |
| `abandon_probabilities.csv` | Per-user abandonment probability |
| `clv_scores.csv` | Per-user CLV score and decile |
| `clv_decile_summary.csv` | CLV decile aggregate stats |
| `segment_summary.csv` | Aggregate segment statistics |
| `user_segments.csv` | Segment assignment and scores |

---

## Setup

**Requirements:**

```
duckdb>=1.5.1
pandas
numpy
scikit-learn
xgboost
lightgbm
shap
```

Install:

```bash
pip install duckdb pandas numpy scikit-learn xgboost lightgbm shap
```

**DuckDB memory configuration** (adjust to your machine in `clickstream_extended.ipynb`):

```python
con.execute("SET memory_limit='4GB'")
con.execute("SET threads=4")
```

DuckDB is configured to spill to disk when memory is tight, so the pipeline can handle the full 270M-event dataset even on machines with limited RAM.

---

## Running the Pipeline

Place all `.parquet` data files in the working directory, then run in order:

```bash
# 1. Funnel analysis
jupyter nbconvert --to notebook --execute funnel_analysis_final.ipynb

# 2. Session-level analysis
python session_analysis_final.py

# 3. User RFM segmentation
python user_analysis_final.py

# 4. Sequential patterns + ML + CLV (run interactively)
jupyter notebook clickstream_extended.ipynb
```

> **Data path note:** `session_analysis_final.py` and `user_analysis_final.py` read from `D:\DataMining_Research\preprocessing_results\parquet\*.parquet` by default. Update the `PARQUET_PATH` variable at the top of each script to match your environment.

---

## Targeting Recommendations

| Segment | Action |
|---|---|
| Cart abandoners | Re-engage within 4h; target `abandon_prob > 0.6` with free-shipping incentive |
| Browsers | Prioritize `cart_to_view_ratio > 0.12` and `unique_products > 3` with urgency messaging |
| Occasional buyers | Cross-sell via post-purchase → view path (~97% transition); recommend related categories |
| High-value buyers | Retention and loyalty; personalize using browsed `product_id`s from event history |
| Dormant | Win-back only for `clv_score_norm > 40`; suppress others to reduce CAC |

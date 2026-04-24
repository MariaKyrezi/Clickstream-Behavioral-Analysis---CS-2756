import duckdb
import pandas as pd
import json
from datetime import datetime
import os

print("=" * 80)
print("SESSION-LEVEL BEHAVIOR ANALYSIS (DAILY-PROXY SESSIONS)")
print("=" * 80)

# =============================================================================
# CONFIGURATION
# =============================================================================

PARQUET_PATH = r"D:\DataMining_Research\preprocessing_results\parquet\*.parquet"
OUTPUT_DIR = "dashboard_data_daily_proxy"
SESSION_DIR = os.path.join(OUTPUT_DIR, "session_analysis")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

con = duckdb.connect()

print(f"\nData source: {PARQUET_PATH}")
print(f"Output directory: {OUTPUT_DIR}")
print(f"Session outputs: {SESSION_DIR}")

# =============================================================================
# BASE SESSION CTE
# One session = one user on one calendar day
# =============================================================================

BASE_SESSION_CTE = f"""
WITH base_events AS (
    SELECT
        user_id,
        product_id,
        event_time,
        CAST(event_time AS DATE) AS session_date,
        event_type,
        price,
        hour,
        is_weekend
    FROM '{PARQUET_PATH}'
    WHERE user_id IS NOT NULL
      AND event_time IS NOT NULL
),
session_table AS (
    SELECT
        user_id,
        session_date,
        CONCAT(CAST(user_id AS VARCHAR), '_', CAST(session_date AS VARCHAR)) AS session_id,
        MIN(event_time) AS session_start,
        MAX(event_time) AS session_end,
        (MAX(EPOCH(event_time)) - MIN(EPOCH(event_time))) / 60.0 AS session_duration_minutes,
        COUNT(*) AS total_events,
        COUNT(DISTINCT product_id) AS unique_products_viewed,
        SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS view_count,
        SUM(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS cart_count,
        SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS purchase_count,
        MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase,
        MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        SUM(CASE WHEN event_type = 'purchase' THEN price ELSE 0 END) AS total_revenue,
        ROUND(AVG(price), 2) AS avg_product_price,
        MAX(price) AS max_price_viewed,
        MAX(is_weekend) AS is_weekend_session,
        EXTRACT('hour' FROM MIN(event_time)) AS session_start_hour
    FROM base_events
    GROUP BY user_id, session_date
)
"""

# =============================================================================
# ANALYSIS 1: SESSION SUMMARY
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 1: SESSION SUMMARY STATISTICS")
print("=" * 80)

session_summary_query = BASE_SESSION_CTE + """
SELECT
    COUNT(*) AS total_sessions,
    COUNT(DISTINCT user_id) AS total_users,
    ROUND(AVG(session_duration_minutes), 2) AS avg_session_duration_min,
    ROUND(AVG(total_events), 2) AS avg_events_per_session,
    ROUND(AVG(unique_products_viewed), 2) AS avg_products_per_session,
    SUM(has_purchase) AS sessions_with_purchase,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS purchase_session_rate
FROM session_table
"""

session_summary = con.execute(session_summary_query).fetchdf()
print(session_summary.to_string(index=False))

summary_dict = session_summary.to_dict("records")[0]
with open(f"{SESSION_DIR}/session_summary.json", "w") as f:
    json.dump(summary_dict, f, indent=2)

# =============================================================================
# ANALYSIS 2: FULL SESSION TABLE
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 2: SESSION-LEVEL TABLE")
print("=" * 80)

session_table_query = BASE_SESSION_CTE + """
SELECT *
FROM session_table
"""

output_csv = f"{OUTPUT_DIR}/session_level_table.csv"
con.execute(f"""
    COPY ({session_table_query})
    TO '{output_csv}' (HEADER, DELIMITER ',')
""")

row_count = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{output_csv}')").fetchone()[0]
file_size = os.path.getsize(output_csv) / (1024 ** 2)

print(f"\nSaved: {output_csv}")
print(f"Rows: {row_count:,}")
print(f"Size: {file_size:.2f} MB")

# =============================================================================
# ANALYSIS 3: PURCHASE VS NON-PURCHASE SESSIONS
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 3: PURCHASE VS NON-PURCHASE SESSIONS")
print("=" * 80)

behavior_comparison_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN has_purchase = 1 THEN 'Purchase Session'
        ELSE 'Non-Purchase Session'
    END AS session_type,
    COUNT(*) AS session_count,
    ROUND(AVG(session_duration_minutes), 2) AS avg_duration_min,
    ROUND(AVG(total_events), 2) AS avg_events,
    ROUND(AVG(unique_products_viewed), 2) AS avg_products_viewed
FROM session_table
GROUP BY has_purchase
ORDER BY session_type
"""

behavior_comparison = con.execute(behavior_comparison_query).fetchdf()
behavior_comparison.to_csv(f"{OUTPUT_DIR}/session_behavior_comparison.csv", index=False)
print(behavior_comparison.to_string(index=False))

# =============================================================================
# ANALYSIS 4: SESSION DURATION DISTRIBUTION
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 4: SESSION DURATION DISTRIBUTION")
print("=" * 80)

duration_dist_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN session_duration_minutes < 1 THEN '< 1 min'
        WHEN session_duration_minutes < 5 THEN '1-5 min'
        WHEN session_duration_minutes < 15 THEN '5-15 min'
        WHEN session_duration_minutes < 30 THEN '15-30 min'
        WHEN session_duration_minutes < 60 THEN '30-60 min'
        ELSE '60+ min'
    END AS duration_bucket,
    COUNT(*) AS session_count,
    SUM(has_purchase) AS sessions_with_purchase,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS conversion_rate
FROM session_table
GROUP BY duration_bucket
ORDER BY
    CASE duration_bucket
        WHEN '< 1 min' THEN 1
        WHEN '1-5 min' THEN 2
        WHEN '5-15 min' THEN 3
        WHEN '15-30 min' THEN 4
        WHEN '30-60 min' THEN 5
        ELSE 6
    END
"""

duration_dist = con.execute(duration_dist_query).fetchdf()
duration_dist.to_csv(f"{OUTPUT_DIR}/session_duration_distribution.csv", index=False)
print(duration_dist.to_string(index=False))

# =============================================================================
# ANALYSIS 5: PRODUCTS PER SESSION
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 5: PRODUCTS VIEWED PER SESSION")
print("=" * 80)

products_viewed_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN unique_products_viewed = 1 THEN '1 product'
        WHEN unique_products_viewed BETWEEN 2 AND 3 THEN '2-3 products'
        WHEN unique_products_viewed BETWEEN 4 AND 5 THEN '4-5 products'
        WHEN unique_products_viewed BETWEEN 6 AND 10 THEN '6-10 products'
        WHEN unique_products_viewed BETWEEN 11 AND 20 THEN '11-20 products'
        ELSE '20+ products'
    END AS products_bucket,
    COUNT(*) AS session_count,
    SUM(has_purchase) AS purchases,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS conversion_rate
FROM session_table
GROUP BY products_bucket
ORDER BY
    CASE products_bucket
        WHEN '1 product' THEN 1
        WHEN '2-3 products' THEN 2
        WHEN '4-5 products' THEN 3
        WHEN '6-10 products' THEN 4
        WHEN '11-20 products' THEN 5
        ELSE 6
    END
"""

products_viewed = con.execute(products_viewed_query).fetchdf()
products_viewed.to_csv(f"{OUTPUT_DIR}/products_per_session.csv", index=False)
print(products_viewed.to_string(index=False))

# =============================================================================
# ANALYSIS 6: CART ABANDONMENT
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 6: CART ABANDONMENT")
print("=" * 80)

cart_abandonment_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN has_cart = 1 AND has_purchase = 0 THEN 'Cart Abandoned'
        WHEN has_cart = 1 AND has_purchase = 1 THEN 'Cart Converted'
        ELSE 'No Cart Activity'
    END AS cart_status,
    COUNT(*) AS session_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM session_table
GROUP BY cart_status
ORDER BY session_count DESC
"""

cart_abandonment = con.execute(cart_abandonment_query).fetchdf()
cart_abandonment.to_csv(f"{OUTPUT_DIR}/cart_abandonment.csv", index=False)
print(cart_abandonment.to_string(index=False))

# =============================================================================
# ANALYSIS 7: ENGAGEMENT LEVELS
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 7: ENGAGEMENT LEVELS")
print("=" * 80)

engagement_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN total_events = 1 THEN 'Bounce (1 event)'
        WHEN total_events BETWEEN 2 AND 3 THEN 'Low (2-3 events)'
        WHEN total_events BETWEEN 4 AND 10 THEN 'Medium (4-10 events)'
        WHEN total_events BETWEEN 11 AND 20 THEN 'High (11-20 events)'
        ELSE 'Very High (20+ events)'
    END AS engagement_level,
    COUNT(*) AS session_count,
    SUM(has_purchase) AS purchases,
    ROUND(AVG(session_duration_minutes), 2) AS avg_duration,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS conversion_rate
FROM session_table
GROUP BY engagement_level
ORDER BY
    CASE engagement_level
        WHEN 'Bounce (1 event)' THEN 1
        WHEN 'Low (2-3 events)' THEN 2
        WHEN 'Medium (4-10 events)' THEN 3
        WHEN 'High (11-20 events)' THEN 4
        ELSE 5
    END
"""

engagement = con.execute(engagement_query).fetchdf()
engagement.to_csv(f"{OUTPUT_DIR}/session_engagement.csv", index=False)
print(engagement.to_string(index=False))

# =============================================================================
# ANALYSIS 8: HOURLY SESSION PATTERNS
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 8: HOURLY SESSION PATTERNS")
print("=" * 80)

hourly_sessions_query = BASE_SESSION_CTE + """
SELECT
    session_start_hour AS hour,
    COUNT(*) AS total_sessions,
    SUM(has_purchase) AS sessions_with_purchase,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS conversion_rate,
    ROUND(AVG(session_duration_minutes), 2) AS avg_duration_min
FROM session_table
GROUP BY session_start_hour
ORDER BY session_start_hour
"""

hourly_sessions = con.execute(hourly_sessions_query).fetchdf()
hourly_sessions.to_csv(f"{OUTPUT_DIR}/hourly_session_patterns.csv", index=False)
print(hourly_sessions.to_string(index=False))

# =============================================================================
# ANALYSIS 9: WEEKEND VS WEEKDAY
# =============================================================================

print("\n" + "=" * 80)
print("ANALYSIS 9: WEEKEND VS WEEKDAY SESSIONS")
print("=" * 80)

weekend_sessions_query = BASE_SESSION_CTE + """
SELECT
    CASE
        WHEN is_weekend_session = 1 THEN 'Weekend'
        ELSE 'Weekday'
    END AS day_type,
    COUNT(*) AS session_count,
    SUM(has_purchase) AS sessions_with_purchase,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 2) AS conversion_rate,
    ROUND(AVG(session_duration_minutes), 2) AS avg_duration,
    ROUND(AVG(total_events), 2) AS avg_events,
    ROUND(AVG(unique_products_viewed), 2) AS avg_products
FROM session_table
GROUP BY is_weekend_session
ORDER BY day_type
"""

weekend_sessions = con.execute(weekend_sessions_query).fetchdf()
weekend_sessions.to_csv(f"{OUTPUT_DIR}/weekend_weekday_sessions.csv", index=False)
print(weekend_sessions.to_string(index=False))

# =============================================================================
# MASTER JSON
# =============================================================================

master_json = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "analysis_type": "session_level_behavior_daily_proxy",
    "data_source": PARQUET_PATH,
    "session_definition": "One session = all events for a user within the same calendar day",
    "summary": summary_dict,
    "behavior_comparison": behavior_comparison.to_dict("records"),
    "duration_distribution": duration_dist.to_dict("records"),
    "products_per_session": products_viewed.to_dict("records"),
    "engagement_levels": engagement.to_dict("records"),
    "cart_abandonment": cart_abandonment.to_dict("records"),
    "hourly_patterns": hourly_sessions.to_dict("records"),
    "weekend_weekday": weekend_sessions.to_dict("records"),
}

with open(f"{OUTPUT_DIR}/session_analysis_master.json", "w") as f:
    json.dump(master_json, f, indent=2, default=str)

print("\nSaved master JSON.")

con.close()

print("\n" + "=" * 80)
print("DAILY-PROXY SESSION ANALYSIS COMPLETE")
print("=" * 80)
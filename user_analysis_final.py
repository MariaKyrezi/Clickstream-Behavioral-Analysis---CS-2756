import duckdb
import pandas as pd
import numpy as np
import json
from datetime import datetime
import os

print("=" * 80)
print("USER-LEVEL RFM SEGMENTATION ANALYSIS (SYNCHRONIZED)")
print("=" * 80)

PARQUET_PATH = r"D:\DataMining_Research\preprocessing_results\parquet\*.parquet"
OUTPUT_DIR = "dashboard_data_synced"
RFM_DIR = os.path.join(OUTPUT_DIR, "rfm_analysis")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RFM_DIR, exist_ok=True)

con = duckdb.connect()

# ---------------------------------------------------------------------
# 1. USER-LEVEL TABLE
# Synchronize session logic with daily-proxy definition:
# one session = one user on one calendar day
# ---------------------------------------------------------------------

user_table_query = f"""
SELECT
    user_id,
    MIN(event_time) AS first_event,
    MAX(event_time) AS last_event,
    COUNT(DISTINCT CAST(event_time AS DATE)) AS total_sessions,
    COUNT(*) AS total_events,
    SUM(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS total_views,
    SUM(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS total_carts,
    SUM(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS total_purchases,
    SUM(CASE WHEN event_type = 'purchase' THEN price ELSE 0 END) AS total_revenue,
    ROUND(AVG(CASE WHEN event_type = 'purchase' THEN price END), 2) AS avg_order_value,
    COUNT(DISTINCT CAST(event_time AS DATE)) AS days_active,
    COUNT(DISTINCT product_id) AS unique_products_viewed
FROM '{PARQUET_PATH}'
WHERE user_id IS NOT NULL
GROUP BY user_id
"""

output_csv = f"{RFM_DIR}/user_level_table.csv"
con.execute(f"""
    COPY ({user_table_query})
    TO '{output_csv}' (HEADER, DELIMITER ',')
""")

users_df = pd.read_csv(output_csv)

users_df["first_event"] = pd.to_datetime(users_df["first_event"])
users_df["last_event"] = pd.to_datetime(users_df["last_event"])

print(f"Users loaded: {len(users_df):,}")

# ---------------------------------------------------------------------
# 2. RFM CALCULATION
# Use global dataset max date, not purchaser-only max date
# ---------------------------------------------------------------------

purchasing_users = users_df[users_df["total_purchases"] > 0].copy()
reference_date = users_df["last_event"].max()

purchasing_users["Recency"] = (reference_date - purchasing_users["last_event"]).dt.days
purchasing_users["Frequency"] = purchasing_users["total_purchases"]
purchasing_users["Monetary"] = purchasing_users["total_revenue"]

def score_quintile(series, ascending_good=True):
    """
    Safe 1-5 scoring using ranked values so ties do not break qcut.
    Returns integer scores from 1 to 5.
    """
    ranked = series.rank(method="first")
    bins = pd.qcut(ranked, 5, labels=False) + 1
    if ascending_good:
        return bins.astype(int)
    else:
        return (6 - bins).astype(int)

# Lower recency is better
purchasing_users["R_Score"] = score_quintile(purchasing_users["Recency"], ascending_good=False)
# Higher frequency and monetary are better
purchasing_users["F_Score"] = score_quintile(purchasing_users["Frequency"], ascending_good=True)
purchasing_users["M_Score"] = score_quintile(purchasing_users["Monetary"], ascending_good=True)

purchasing_users["RFM_Score"] = (
    purchasing_users["R_Score"].astype(str)
    + purchasing_users["F_Score"].astype(str)
    + purchasing_users["M_Score"].astype(str)
)

# ---------------------------------------------------------------------
# 3. PURCHASER-ONLY RFM SEGMENTS
# Keep this separate from all-user behavioral segments
# ---------------------------------------------------------------------

def rfm_segment(row):
    r, f, m = int(row["R_Score"]), int(row["F_Score"]), int(row["M_Score"])

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    elif r >= 3 and f >= 4 and m >= 3:
        return "Loyal Customers"
    elif r >= 4 and f >= 2 and m >= 2:
        return "Potential Loyalists"
    elif r >= 4 and f <= 2:
        return "New Customers"
    elif r <= 2 and f >= 4 and m >= 3:
        return "Can't Lose Them"
    elif r <= 2 and f >= 3:
        return "At Risk"
    elif r <= 2 and f <= 2:
        return "Hibernating"
    elif m <= 2:
        return "Price Sensitive"
    else:
        return "Others"

purchasing_users["Segment"] = purchasing_users.apply(rfm_segment, axis=1)

segment_dist = purchasing_users["Segment"].value_counts().reset_index()
segment_dist.columns = ["Segment", "User_Count"]
segment_dist["Percentage"] = (segment_dist["User_Count"] / len(purchasing_users) * 100).round(2)

segment_dist.to_csv(f"{RFM_DIR}/user_segments.csv", index=False)

segment_chars = purchasing_users.groupby("Segment").agg({
    "user_id": "count",
    "Recency": "mean",
    "Frequency": "mean",
    "Monetary": ["mean", "sum"],
    "total_sessions": "mean",
    "days_active": "mean"
}).round(2)

segment_chars.columns = [
    "User_Count",
    "Avg_Recency_Days",
    "Avg_Frequency",
    "Avg_Monetary",
    "Total_Revenue",
    "Avg_Sessions",
    "Avg_Days_Active"
]
segment_chars = segment_chars.reset_index().sort_values("Total_Revenue", ascending=False)
segment_chars.to_csv(f"{RFM_DIR}/segment_characteristics.csv", index=False)

# ---------------------------------------------------------------------
# 4. CLV / REVENUE CONCENTRATION
# ---------------------------------------------------------------------

clv_insights = {
    "total_purchasing_users": int(len(purchasing_users)),
    "total_revenue": float(purchasing_users["Monetary"].sum()),
    "avg_customer_value": float(purchasing_users["Monetary"].mean()),
    "median_customer_value": float(purchasing_users["Monetary"].median()),
    "top_10_percent_revenue": float(
        purchasing_users.nlargest(max(1, int(len(purchasing_users) * 0.1)), "Monetary")["Monetary"].sum()
    ),
    "top_10_percent_share": float(
        purchasing_users.nlargest(max(1, int(len(purchasing_users) * 0.1)), "Monetary")["Monetary"].sum()
        / purchasing_users["Monetary"].sum() * 100
    ),
    "avg_purchases_per_user": float(purchasing_users["Frequency"].mean()),
    "avg_days_active": float(purchasing_users["days_active"].mean())
}

with open(f"{OUTPUT_DIR}/clv_insights.json", "w") as f:
    json.dump(clv_insights, f, indent=2)

# ---------------------------------------------------------------------
# 5. ALL-USER BEHAVIORAL SEGMENTATION
# Make segments mutually exclusive and business-readable
# Keep power-user as a flag, not a main segment
# ---------------------------------------------------------------------

event_p90 = users_df["total_events"].quantile(0.9)
users_df["is_power_user"] = (users_df["total_events"] > event_p90).astype(int)

def behavioral_segment(row):
    if row["total_purchases"] > 0:
        return "Buyers"
    elif row["total_carts"] > 0:
        return "Cart Abandoners"
    elif row["total_views"] > 50:
        return "Window Shoppers"
    elif row["total_events"] <= 5:
        return "Casual Browsers"
    else:
        return "Active Browsers"

users_df["Behavioral_Segment"] = users_df.apply(behavioral_segment, axis=1)

behavioral_dist = users_df["Behavioral_Segment"].value_counts().reset_index()
behavioral_dist.columns = ["Segment", "User_Count"]
behavioral_dist["Percentage"] = (behavioral_dist["User_Count"] / len(users_df) * 100).round(2)
behavioral_dist.to_csv(f"{OUTPUT_DIR}/behavioral_segments.csv", index=False)

# Optional: add power-user counts by segment
power_user_summary = (
    users_df.groupby("Behavioral_Segment")["is_power_user"]
    .sum()
    .reset_index()
    .rename(columns={"is_power_user": "Power_User_Count"})
)
power_user_summary.to_csv(f"{OUTPUT_DIR}/power_user_summary.csv", index=False)

# ---------------------------------------------------------------------
# 6. MASTER JSON
# ---------------------------------------------------------------------

master_json = {
    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "analysis_type": "rfm_user_segmentation_synced",
    "data_source": PARQUET_PATH,
    "session_definition": "Daily-proxy session: one session = one user on one calendar day",
    "total_users": int(len(users_df)),
    "purchasing_users": int(len(purchasing_users)),
    "non_purchasing_users": int((users_df["total_purchases"] == 0).sum()),
    "rfm_segment_distribution": segment_dist.to_dict("records"),
    "rfm_segment_characteristics": segment_chars.to_dict("records"),
    "behavioral_segments": behavioral_dist.to_dict("records"),
    "clv_insights": clv_insights
}

with open(f"{OUTPUT_DIR}/rfm_analysis_master.json", "w") as f:
    json.dump(master_json, f, indent=2, default=str)

con.close()
print("Synchronized user segmentation analysis complete.")
"""
E-commerce Data Preprocessing - Processing Separate CSV Files
Uses DuckDB to query across multiple files without merging
Each file stays separate, analysis works across all files
"""

import duckdb
import os
import json
from datetime import datetime

print("="*80)
print("E-COMMERCE DATA PREPROCESSING")
print("Multi-File Analysis with DuckDB (No Merging)")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Directory containing CSV files
csv_directory = r"E:\Data_Mining" 

# List of CSV files
csv_files = [
    "2019-October-November.csv",
    "2019-December.csv",  
    "2020-January.csv",
    "2020-February.csv",
    "2020-March.csv",
    "2020-April.csv",
]

# Output directory for documentation
output_dir = "preprocessing_results"
os.makedirs(output_dir, exist_ok=True)

# Initialize DuckDB connection
con = duckdb.connect()

# Preprocessing log
preprocessing_log = {
    'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'files': [],
    'metrics': {},
    'decisions': {}
}

# ============================================================================
# STEP 1: VERIFY ALL FILES
# ============================================================================

print("\n" + "="*80)
print("STEP 1: FILE VERIFICATION")
print("="*80)

valid_files = []
total_size_gb = 0

for i, filename in enumerate(csv_files, 1):
    filepath = os.path.join(csv_directory, filename)
    
    if os.path.exists(filepath):
        size_gb = os.path.getsize(filepath) / (1024**3)
        total_size_gb += size_gb
        valid_files.append(filepath)
        print(f"  {i}. ✅ {filename:50s} ({size_gb:6.2f} GB)")
        
        preprocessing_log['files'].append({
            'name': filename,
            'path': filepath,
            'size_gb': round(size_gb, 2),
            'status': 'found'
        })
    else:
        print(f"  {i}.NOT FOUND: {filename}")
        preprocessing_log['files'].append({
            'name': filename,
            'status': 'not_found'
        })

if not valid_files:
    print("\n No valid files found! Check your paths.")
    exit(1)

print(f"\nFound {len(valid_files)} files")
print(f"Total size: {total_size_gb:.2f} GB")

preprocessing_log['metrics']['files_found'] = len(valid_files)
preprocessing_log['metrics']['total_size_gb'] = round(total_size_gb, 2)

# ============================================================================
# STEP 2: ANALYZE EACH FILE SEPARATELY
# ============================================================================

print("\n" + "="*80)
print("STEP 2: INDIVIDUAL FILE ANALYSIS")
print("="*80)

file_stats = []

for i, filepath in enumerate(valid_files, 1):
    filename = os.path.basename(filepath)
    print(f"\n[{i}/{len(valid_files)}] Analyzing: {filename}")
    print("-"*80)
    
    try:
        # Count rows
        row_count_query = f"""
        SELECT COUNT(*) as count 
        FROM read_csv_auto('{filepath}', ignore_errors=true)
        """
        row_count = con.execute(row_count_query).fetchone()[0]
        print(f"  Rows: {row_count:,}")
        
        # Get date range
        date_query = f"""
        SELECT 
            MIN(event_time) as min_date,
            MAX(event_time) as max_date
        FROM read_csv_auto('{filepath}', ignore_errors=true)
        """
        dates = con.execute(date_query).fetchone()
        print(f"  Date range: {dates[0]} to {dates[1]}")
        
        # Event type distribution
        event_query = f"""
        SELECT 
            event_type,
            COUNT(*) as count
        FROM read_csv_auto('{filepath}', ignore_errors=true)
        GROUP BY event_type
        """
        events = con.execute(event_query).fetchdf()
        print(f"  Event types:")
        for _, row in events.iterrows():
            pct = (row['count'] / row_count * 100)
            print(f"    - {row['event_type']:12s}: {row['count']:>10,} ({pct:>5.2f}%)")
        
        # Missing values
        missing_query = f"""
        SELECT 
            COUNT(*) - COUNT(brand) as brand_missing,
            COUNT(*) - COUNT(category_code) as category_missing,
            COUNT(*) - COUNT(price) as price_missing
        FROM read_csv_auto('{filepath}', ignore_errors=true)
        """
        missing = con.execute(missing_query).fetchone()
        print(f"  Missing values:")
        print(f"    - brand: {missing[0]:,} ({missing[0]/row_count*100:.2f}%)")
        print(f"    - category_code: {missing[1]:,} ({missing[1]/row_count*100:.2f}%)")
        print(f"    - price: {missing[2]:,} ({missing[2]/row_count*100:.2f}%)")
        
        file_stats.append({
            'filename': filename,
            'filepath': filepath,
            'rows': row_count,
            'date_range': (str(dates[0]), str(dates[1])),
            'missing_brand': missing[0],
            'missing_category': missing[1],
            'missing_price': missing[2]
        })
        
    except Exception as e:
        print(f" Error analyzing file: {str(e)[:100]}")
        continue

preprocessing_log['metrics']['file_stats'] = file_stats

# ============================================================================
# STEP 3: CROSS-FILE ANALYSIS (WITHOUT MERGING)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: COMBINED ANALYSIS ACROSS ALL FILES")
print("="*80)
print("\nQuerying across all files (no merging required)...")

try:
    # Build UNION ALL for all files
    union_queries = [f"SELECT * FROM read_csv_auto('{fp}', ignore_errors=true)" 
                     for fp in valid_files]
    full_dataset = " UNION ALL ".join(union_queries)
    
    # Total statistics
    print("\n[1] Overall Statistics:")
    total_stats_query = f"""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT product_id) as unique_products,
        COUNT(DISTINCT user_session) as unique_sessions,
        MIN(event_time) as earliest_date,
        MAX(event_time) as latest_date
    FROM ({full_dataset})
    """
    
    stats = con.execute(total_stats_query).fetchone()
    
    print(f"  Total rows: {stats[0]:,}")
    print(f"  Unique users: {stats[1]:,}")
    print(f"  Unique products: {stats[2]:,}")
    print(f"  Unique sessions: {stats[3]:,}")
    print(f"  Date range: {stats[4]} to {stats[5]}")
    
    preprocessing_log['metrics']['total_rows'] = stats[0]
    preprocessing_log['metrics']['unique_users'] = stats[1]
    preprocessing_log['metrics']['unique_products'] = stats[2]
    preprocessing_log['metrics']['unique_sessions'] = stats[3]
    
    # Missing value patterns across all data
    print("\n[2] Missing Value Patterns (All Files):")
    missing_pattern_query = f"""
    SELECT 
        CASE WHEN brand IS NULL THEN 1 ELSE 0 END as brand_missing,
        CASE WHEN category_code IS NULL THEN 1 ELSE 0 END as category_missing,
        COUNT(*) as count
    FROM ({full_dataset})
    GROUP BY brand_missing, category_missing
    ORDER BY count DESC
    """
    
    patterns = con.execute(missing_pattern_query).fetchdf()
    
    print("-"*80)
    for _, row in patterns.iterrows():
        brand_status = "Missing" if row['brand_missing'] == 1 else "Present"
        cat_status = "Missing" if row['category_missing'] == 1 else "Present"
        pct = (row['count'] / stats[0] * 100)
        print(f"  Brand: {brand_status:8s} | Category: {cat_status:8s} | {row['count']:>12,} ({pct:>6.2f}%)")
    
    # Store patterns
    both_missing = patterns[(patterns['brand_missing']==1) & (patterns['category_missing']==1)]
    only_brand = patterns[(patterns['brand_missing']==1) & (patterns['category_missing']==0)]
    only_category = patterns[(patterns['brand_missing']==0) & (patterns['category_missing']==1)]
    
    preprocessing_log['metrics']['missing_patterns'] = {
        'both_missing': int(both_missing['count'].iloc[0]) if len(both_missing) > 0 else 0,
        'only_brand_missing': int(only_brand['count'].iloc[0]) if len(only_brand) > 0 else 0,
        'only_category_missing': int(only_category['count'].iloc[0]) if len(only_category) > 0 else 0
    }
    
    # Event type distribution
    print("\n[3] Overall Event Distribution:")
    event_dist_query = f"""
    SELECT 
        event_type,
        COUNT(*) as count
    FROM ({full_dataset})
    GROUP BY event_type
    ORDER BY count DESC
    """
    
    events = con.execute(event_dist_query).fetchdf()
    for _, row in events.iterrows():
        pct = (row['count'] / stats[0] * 100)
        print(f"  {row['event_type']:12s}: {row['count']:>12,} ({pct:>6.2f}%)")
    
except Exception as e:
    print(f"\nError in combined analysis: {str(e)[:200]}")
    print("Continuing with individual file analysis...")

# ============================================================================
# STEP 4: GENERATE PREPROCESSING STRATEGY
# ============================================================================

print("\n" + "="*80)
print("STEP 4: PREPROCESSING RECOMMENDATIONS")
print("="*80)

# Calculate percentages for decision making
total_rows = preprocessing_log['metrics'].get('total_rows', 0)
patterns = preprocessing_log['metrics'].get('missing_patterns', {})

if total_rows > 0:
    both_pct = (patterns.get('both_missing', 0) / total_rows) * 100
    brand_pct = (patterns.get('only_brand_missing', 0) / total_rows) * 100
    cat_pct = (patterns.get('only_category_missing', 0) / total_rows) * 100
    
    print("\nMissing Value Treatment Strategy:")
    print("-"*80)
    
    # Scenario 1: Both missing
    print(f"\n1. BOTH brand & category missing ({both_pct:.2f}%):")
    if both_pct < 2.0:
        print(f"   → REMOVE these rows")
        print(f"   → Rationale: <2% of data, insufficient information")
        preprocessing_log['decisions']['both_missing'] = 'remove'
    else:
        print(f"   → FILL with 'Unknown'")
        print(f"   → Rationale: Too much data to lose")
        preprocessing_log['decisions']['both_missing'] = 'fill'
    
    # Scenario 2: Only brand missing
    print(f"\n2. ONLY brand missing ({brand_pct:.2f}%):")
    print(f"   → FILL with 'Unknown'")
    print(f"   → Rationale: Category info valuable, likely generic products")
    preprocessing_log['decisions']['only_brand_missing'] = 'fill'
    
    # Scenario 3: Only category missing
    print(f"\n3. ONLY category missing ({cat_pct:.2f}%):")
    print(f"   → INFER from brand mapping")
    print(f"   → Rationale: Brand-to-category relationship exists")
    preprocessing_log['decisions']['only_category_missing'] = 'infer'

# ============================================================================
# STEP 4: WRITE CLEANED DATA TO PARQUET
# ============================================================================

print("\n" + "="*80)
print("STEP 4: WRITING CLEANED DATA TO PARQUET")
print("="*80)

# Create parquet output directory
parquet_dir = os.path.join(output_dir, "parquet")
os.makedirs(parquet_dir, exist_ok=True)

print(f"\nOutput directory: {parquet_dir}")
print("\nProcessing each file and writing to Parquet...")
print("This will take 20-40 minutes for all files...")

response = input("\nProceed with Parquet conversion? (yes/no): ").strip().lower()
if response not in ['yes', 'y']:
    print("Skipped Parquet conversion.")
else:
    import time
    parquet_files = []
    
    for i, filepath in enumerate(valid_files, 1):
        filename = os.path.basename(filepath)
        file_start = time.time()
        
        print(f"\n[{i}/{len(valid_files)}] Processing: {filename}")
        
        try:
            # Output parquet filename (keep same base name)
            parquet_name = filename.replace('.csv', '.parquet')
            parquet_path = os.path.join(parquet_dir, parquet_name)
            
            # Clean and write to Parquet
            clean_query = f"""
            COPY (
                SELECT 
                    event_time,
                    event_type,
                    product_id,
                    category_id,
                    COALESCE(category_code, 'Unknown') as category_code,
                    COALESCE(brand, 'Unknown') as brand,
                    price,
                    user_id,
                    user_session,
                    -- Add tracking columns
                    CASE WHEN brand IS NULL THEN 1 ELSE 0 END as brand_was_missing,
                    CASE WHEN category_code IS NULL THEN 1 ELSE 0 END as category_was_missing,
                    -- Add derived columns
                    CAST(EXTRACT(HOUR FROM event_time) AS INTEGER) as hour,
                    CAST(EXTRACT(DOW FROM event_time) AS INTEGER) as day_of_week,
                    CASE WHEN EXTRACT(DOW FROM event_time) IN (0, 6) THEN 1 ELSE 0 END as is_weekend,
                    DATE_TRUNC('day', event_time) as date
                FROM read_csv_auto('{filepath}', 
                    ignore_errors=true,
                    header=true
                )
                WHERE price > 0  -- Remove invalid prices
                    AND price < 100000  -- Remove unrealistic prices
            ) TO '{parquet_path}' (
                FORMAT PARQUET, 
                COMPRESSION ZSTD,
                ROW_GROUP_SIZE 100000
            )
            """
            
            con.execute(clean_query)
            
            elapsed = time.time() - file_start
            file_size = os.path.getsize(parquet_path) / (1024**3)
            
            print(f"    ✅ Success!")
            print(f"    Time: {elapsed:.1f}s")
            print(f"    Output: {parquet_name} ({file_size:.2f} GB)")
            
            parquet_files.append(parquet_path)
            
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:150]}")
            continue
    
    print(f"\n✅ Converted {len(parquet_files)} files to Parquet")
    print(f"   Location: {parquet_dir}")
    
    # Calculate total size savings
    if parquet_files:
        parquet_total_size = sum(os.path.getsize(f) for f in parquet_files) / (1024**3)
        csv_total_size = sum(os.path.getsize(f) for f in valid_files) / (1024**3)
        savings = csv_total_size - parquet_total_size
        savings_pct = (savings / csv_total_size * 100) if csv_total_size > 0 else 0
        
        print(f"\n   Size comparison:")
        print(f"     Original CSV: {csv_total_size:.2f} GB")
        print(f"     Parquet:      {parquet_total_size:.2f} GB")
        print(f"     Savings:      {savings:.2f} GB ({savings_pct:.1f}%)")
        
        preprocessing_log['metrics']['parquet_conversion'] = {
            'files_converted': len(parquet_files),
            'csv_size_gb': round(csv_total_size, 2),
            'parquet_size_gb': round(parquet_total_size, 2),
            'savings_gb': round(savings, 2),
            'savings_pct': round(savings_pct, 1)
        }

# ============================================================================
# STEP 5: CREATE PARQUET VIEWS
# ============================================================================

print("\n" + "="*80)
print("STEP 5: CREATING PARQUET VIEWS")
print("="*80)

if 'parquet_files' in locals() and parquet_files:
    print("\nCreating views for Parquet files (much faster than CSV)...")
    
    try:
        # Create view from all Parquet files
        parquet_pattern = os.path.join(parquet_dir, "*.parquet")
        
        con.execute(f"""
        CREATE OR REPLACE VIEW ecommerce_parquet AS
        SELECT * FROM read_parquet('{parquet_pattern}')
        """)
        
        print("✅ Created view: ecommerce_parquet")
        
        # Test the view
        test_count = con.execute("SELECT COUNT(*) FROM ecommerce_parquet").fetchone()[0]
        print(f"   Total rows in Parquet: {test_count:,}")
        
        # Show performance comparison
        print("\n   Speed comparison (SELECT COUNT(*)):")
        
        # Time CSV query
        csv_start = time.time()
        csv_count = con.execute(f"SELECT COUNT(*) FROM ecommerce_all").fetchone()[0]
        csv_time = time.time() - csv_start
        
        # Time Parquet query
        parquet_start = time.time()
        parquet_count = con.execute(f"SELECT COUNT(*) FROM ecommerce_parquet").fetchone()[0]
        parquet_time = time.time() - parquet_start
        
        speedup = csv_time / parquet_time if parquet_time > 0 else 0
        
        print(f"     CSV:     {csv_time:.2f}s")
        print(f"     Parquet: {parquet_time:.2f}s")
        print(f"     Speedup: {speedup:.1f}x faster! 🚀")
        
    except Exception as e:
        print(f"❌ Error creating Parquet views: {str(e)[:150]}")
else:
    print("⊘ No Parquet files created, skipping views")

# ============================================================================
# STEP 6: EXAMPLE ANALYSES (USING PARQUET)
# ============================================================================

print("\n" + "="*80)
print("STEP 6: EXAMPLE ANALYSES (USING PARQUET)")
print("="*80)

if 'parquet_files' in locals() and parquet_files:
    
    print("\n[Example 1] Funnel Analysis (from Parquet):")
    try:
        funnel_query = """
        SELECT 
            event_type,
            COUNT(*) as count
        FROM ecommerce_parquet
        GROUP BY event_type
        ORDER BY 
            CASE event_type 
                WHEN 'view' THEN 1 
                WHEN 'cart' THEN 2 
                WHEN 'purchase' THEN 3 
            END
        """
        funnel = con.execute(funnel_query).fetchdf()
        
        for i, row in funnel.iterrows():
            print(f"  {row['event_type']:12s}: {row['count']:>12,}")
            
        if len(funnel) >= 2:
            view_count = funnel[funnel['event_type']=='view']['count'].iloc[0]
            cart_count = funnel[funnel['event_type']=='cart']['count'].iloc[0] if 'cart' in funnel['event_type'].values else 0
            purchase_count = funnel[funnel['event_type']=='purchase']['count'].iloc[0] if 'purchase' in funnel['event_type'].values else 0
            
            view_to_cart = (cart_count / view_count * 100) if view_count > 0 else 0
            cart_to_purchase = (purchase_count / cart_count * 100) if cart_count > 0 else 0
            
            print(f"\n  Conversion Rates:")
            print(f"    View → Cart:      {view_to_cart:.2f}%")
            print(f"    Cart → Purchase:  {cart_to_purchase:.2f}%")
            
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

    print("\n[Example 2] Hourly Pattern Analysis:")
    try:
        hourly_query = """
        SELECT 
            hour,
            COUNT(*) as events,
            COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) as purchases
        FROM ecommerce_parquet
        GROUP BY hour
        ORDER BY hour
        """
        hourly = con.execute(hourly_query).fetchdf()
        
        print("\n  Hour | Total Events | Purchases")
        print("  " + "-"*40)
        for _, row in hourly.head(24).iterrows():
            print(f"  {row['hour']:4d} | {row['events']:>12,} | {row['purchases']:>9,}")
            
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

    print("\n[Example 3] Brand Performance (with tracking):")
    try:
        brand_query = """
        SELECT 
            brand,
            COUNT(*) as total_events,
            SUM(brand_was_missing) as was_filled,
            COUNT(CASE WHEN event_type = 'purchase' THEN 1 END) as purchases
        FROM ecommerce_parquet
        WHERE brand != 'Unknown'
        GROUP BY brand
        ORDER BY total_events DESC
        LIMIT 10
        """
        brands = con.execute(brand_query).fetchdf()
        
        print("\n  Brand              | Events     | Filled | Purchases")
        print("  " + "-"*60)
        for _, row in brands.iterrows():
            print(f"  {row['brand']:18s} | {row['total_events']:>10,} | {row['was_filled']:>6,} | {row['purchases']:>9,}")
            
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

else:
    # Fallback to CSV-based examples
    print("\n[Using CSV files - consider converting to Parquet for better performance]")
    
    print("\n[Example 1] Funnel Analysis:")
    try:
        funnel_query = """
        SELECT 
            event_type,
            COUNT(*) as count
        FROM ecommerce_all
        GROUP BY event_type
        ORDER BY 
            CASE event_type 
                WHEN 'view' THEN 1 
                WHEN 'cart' THEN 2 
                WHEN 'purchase' THEN 3 
            END
        """
        funnel = con.execute(funnel_query).fetchdf()
        
        for i, row in funnel.iterrows():
            print(f"  {row['event_type']:12s}: {row['count']:>12,}")
            
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

    print("\n[Example 2] Top 10 Brands by Events:")
    try:
        brand_query = """
        SELECT 
            brand,
            COUNT(*) as events
        FROM ecommerce_all
        WHERE brand IS NOT NULL
        GROUP BY brand
        ORDER BY events DESC
        LIMIT 10
        """
        brands = con.execute(brand_query).fetchdf()
        
        for _, row in brands.iterrows():
            print(f"  {row['brand']:20s}: {row['events']:>10,}")
            
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")

# ============================================================================
# STEP 7: SAVE DOCUMENTATION
# ============================================================================

print("\n" + "="*80)
print("STEP 7: SAVING DOCUMENTATION")
print("="*80)

preprocessing_log['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Save JSON log
log_file = os.path.join(output_dir, 'preprocessing_log.json')
with open(log_file, 'w') as f:
    json.dump(preprocessing_log, f, indent=2, default=str)
print(f"✅ Saved: {log_file}")

# Save SQL script for future use
sql_file = os.path.join(output_dir, 'analysis_queries.sql')
with open(sql_file, 'w') as f:
    f.write("-- E-commerce Analysis Queries\n")
    f.write("-- Use with DuckDB\n\n")
    f.write("-- Load all files:\n")
    for fp in valid_files:
        f.write(f"-- {fp}\n")
    f.write("\n-- Create union view:\n")
    f.write(f"CREATE VIEW ecommerce_all AS\n")
    f.write(" UNION ALL\n".join([
        f"SELECT * FROM read_csv_auto('{fp}', ignore_errors=true)"
        for fp in valid_files
    ]))
    f.write(";\n")
print(f"✅ Saved: {sql_file}")

# Save summary report
report_file = os.path.join(output_dir, 'preprocessing_summary.txt')
with open(report_file, 'w') as f:
    f.write("="*80 + "\n")
    f.write("E-COMMERCE DATA PREPROCESSING SUMMARY\n")
    f.write("="*80 + "\n\n")
    f.write(f"Files Processed: {len(valid_files)}\n")
    f.write(f"Total Rows: {preprocessing_log['metrics'].get('total_rows', 0):,}\n")
    f.write(f"Date Range: {preprocessing_log['metrics'].get('date_range', 'N/A')}\n")
    f.write(f"\nPreprocessing completed: {preprocessing_log['end_time']}\n")
print(f"✅ Saved: {report_file}")

# Close connection
con.close()

# ============================================================================
# COMPLETION
# ============================================================================

print("\n" + "="*80)
print("✅ PREPROCESSING COMPLETE!")
print("="*80)

print(f"""
Summary:
  Files analyzed: {len(valid_files)}
  Total rows: {preprocessing_log['metrics'].get('total_rows', 0):,}
  Unique users: {preprocessing_log['metrics'].get('unique_users', 0):,}
  Unique products: {preprocessing_log['metrics'].get('unique_products', 0):,}

Output files:
  - {log_file}
  - {sql_file}
  - {report_file}
  {'- Parquet files: ' + parquet_dir if 'parquet_files' in locals() and parquet_files else ''}

Parquet Benefits:
  ✅ 3-5x smaller file size
  ✅ 10-100x faster queries
  ✅ Columnar format (perfect for analytics)
  ✅ Built-in compression
  ✅ Schema embedded in file

Next Steps:
  1. Use Parquet files for all analysis (much faster!)
  2. Upload Parquet files to server (smaller, faster transfer)
  3. Query with DuckDB or Pandas
  
Example usage with Parquet:
  ```python
  import duckdb
  con = duckdb.connect()
  
  # Query Parquet files (10-100x faster than CSV!)
  df = con.execute('''
      SELECT * FROM '{parquet_dir}/*.parquet'
      WHERE event_type = 'purchase'
      LIMIT 1000
  ''').fetchdf()
  
  # Or with pandas (also fast with Parquet)
  import pandas as pd
  df = pd.read_parquet('{parquet_dir}')
  ```

Upload to server:
  rsync -avz --progress {parquet_dir}/ ams1338@nietzsche.cs.pitt.edu:/u/ams1338/data/parquet/
""")

print("="*80)
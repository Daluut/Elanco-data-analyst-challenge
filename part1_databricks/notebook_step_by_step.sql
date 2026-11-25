-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Elanco Data Analyst Challenge: Part 1 (Databricks warm-up)
-- MAGIC
-- MAGIC **How to use:** attach this notebook to Serverless compute (top right), then run each cell with Shift+Enter, top to bottom.
-- MAGIC Screenshot each result for the presentation. Each section says what to look for.

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Q6. Data profile of `samples.nyctaxi.trips`
-- MAGIC
-- MAGIC **Step 1: what columns exist?** Check this first. The brief's revenue formula uses `tip_amount` and `extra`; see whether they are actually here.

-- COMMAND ----------

DESCRIBE TABLE samples.nyctaxi.trips;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Step 2: Databricks' built-in Data Profile.** Run the cell below. Above the results table, click the **+** next to "Table" and choose **Data Profile**.
-- MAGIC Screenshot it: it shows the distribution, nulls, min and max for every column.

-- COMMAND ----------

SELECT * FROM samples.nyctaxi.trips;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Step 3: summary statistics.** How many trips, what dates, and the range of distance and fare.

-- COMMAND ----------

SELECT
  COUNT(*)                                  AS total_trips,
  MIN(tpep_pickup_datetime)                 AS first_pickup,
  MAX(tpep_pickup_datetime)                 AS last_pickup,
  ROUND(MIN(trip_distance), 2)              AS min_distance,
  ROUND(AVG(trip_distance), 2)              AS avg_distance,
  ROUND(percentile_approx(trip_distance, 0.5), 2) AS median_distance,
  ROUND(MAX(trip_distance), 2)              AS max_distance,
  ROUND(MIN(fare_amount), 2)                AS min_fare,
  ROUND(AVG(fare_amount), 2)                AS avg_fare,
  ROUND(percentile_approx(fare_amount, 0.5), 2) AS median_fare,
  ROUND(MAX(fare_amount), 2)                AS max_fare,
  COUNT(DISTINCT pickup_zip)                AS distinct_pickup_zips,
  SUM(CASE WHEN pickup_zip  IS NULL THEN 1 ELSE 0 END) AS null_pickup_zip,
  SUM(CASE WHEN dropoff_zip IS NULL THEN 1 ELSE 0 END) AS null_dropoff_zip,
  SUM(CASE WHEN fare_amount IS NULL THEN 1 ELSE 0 END) AS null_fare
FROM samples.nyctaxi.trips;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Step 4: anomaly counts.** Each column counts trips that look impossible or suspicious. Note any that are above zero; these are your "anomalies found".

-- COMMAND ----------

SELECT
  COUNT(*) AS total_trips,
  SUM(CASE WHEN fare_amount < 0 THEN 1 ELSE 0 END)                       AS negative_fare,
  SUM(CASE WHEN fare_amount = 0 THEN 1 ELSE 0 END)                       AS zero_fare,
  SUM(CASE WHEN trip_distance = 0 THEN 1 ELSE 0 END)                     AS zero_distance,
  SUM(CASE WHEN trip_distance = 0 AND fare_amount > 20 THEN 1 ELSE 0 END) AS zero_distance_but_fare_over_20,
  SUM(CASE WHEN trip_distance > 100 THEN 1 ELSE 0 END)                   AS distance_over_100_miles,
  SUM(CASE WHEN fare_amount > 250 THEN 1 ELSE 0 END)                     AS fare_over_250,
  SUM(CASE WHEN tpep_dropoff_datetime <= tpep_pickup_datetime THEN 1 ELSE 0 END) AS dropoff_not_after_pickup,
  SUM(CASE WHEN timestampdiff(MINUTE, tpep_pickup_datetime, tpep_dropoff_datetime) > 180 THEN 1 ELSE 0 END) AS trip_over_3_hours,
  SUM(CASE WHEN pickup_zip = dropoff_zip AND trip_distance > 20 THEN 1 ELSE 0 END) AS same_zip_but_over_20_miles
FROM samples.nyctaxi.trips;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Step 5: look at some anomalous rows** so you can describe real examples on your slide.

-- COMMAND ----------

SELECT *,
  timestampdiff(MINUTE, tpep_pickup_datetime, tpep_dropoff_datetime) AS duration_minutes
FROM samples.nyctaxi.trips
WHERE fare_amount <= 0
   OR trip_distance = 0
   OR trip_distance > 100
   OR tpep_dropoff_datetime <= tpep_pickup_datetime
   OR timestampdiff(MINUTE, tpep_pickup_datetime, tpep_dropoff_datetime) > 180
ORDER BY fare_amount
LIMIT 50;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Step 6: trips per day.** Click **+ → Visualization → Line** (x = pickup_date, y = trips). Look for gaps, spikes, or odd dates outside the main range.

-- COMMAND ----------

SELECT DATE(tpep_pickup_datetime) AS pickup_date, COUNT(*) AS trips
FROM samples.nyctaxi.trips
GROUP BY 1
ORDER BY 1;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Q7. Revenue, distance and volume by day of week and hour
-- MAGIC
-- MAGIC The brief defines revenue as `fare_amount + tip_amount + extra`. If Step 1 showed that **`tip_amount` and `extra` do not exist** in this table, revenue below = `fare_amount` only.
-- MAGIC **Say this on your slide as a limitation.** It shows you checked the data rather than assuming.
-- MAGIC
-- MAGIC (If those columns *do* exist in your workspace, replace `fare_amount` in the SUM with `fare_amount + COALESCE(tip_amount,0) + COALESCE(extra,0)`.)

-- COMMAND ----------

-- Version A: all trips as recorded
SELECT
  date_format(tpep_pickup_datetime, 'EEEE')  AS day_of_week,
  hour(tpep_pickup_datetime)                 AS hour_of_day,
  ROUND(SUM(fare_amount), 2)                 AS total_revenue,
  ROUND(AVG(trip_distance), 2)               AS avg_trip_distance,
  COUNT(*)                                   AS trip_volume
FROM samples.nyctaxi.trips
GROUP BY 1, 2
ORDER BY total_revenue DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Version B: excluding the anomalies from Q6** (non-positive fares, zero distance, impossible times). Compare the top rows with Version A.
-- MAGIC If the ranking barely changes, say so: the anomalies don't affect the conclusion.

-- COMMAND ----------

SELECT
  date_format(tpep_pickup_datetime, 'EEEE')  AS day_of_week,
  hour(tpep_pickup_datetime)                 AS hour_of_day,
  ROUND(SUM(fare_amount), 2)                 AS total_revenue,
  ROUND(AVG(trip_distance), 2)               AS avg_trip_distance,
  COUNT(*)                                   AS trip_volume
FROM samples.nyctaxi.trips
WHERE fare_amount > 0
  AND trip_distance > 0
  AND tpep_dropoff_datetime > tpep_pickup_datetime
GROUP BY 1, 2
ORDER BY total_revenue DESC;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Heatmap for your slide:** run this and choose **+ → Visualization → Heatmap** (x = hour_of_day, y = day_of_week, colour = total_revenue).

-- COMMAND ----------

SELECT
  dayofweek(tpep_pickup_datetime)            AS day_num,
  date_format(tpep_pickup_datetime, 'EEEE')  AS day_of_week,
  hour(tpep_pickup_datetime)                 AS hour_of_day,
  ROUND(SUM(fare_amount), 2)                 AS total_revenue
FROM samples.nyctaxi.trips
WHERE fare_amount > 0
GROUP BY 1, 2, 3
ORDER BY day_num, hour_of_day;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Q8. Entity relationship diagram for `samples.tpch`
-- MAGIC
-- MAGIC List every table and its columns. The keys (`..._key` columns) show how tables connect. The ERD image is supplied separately for your slide.

-- COMMAND ----------

SHOW TABLES IN samples.tpch;

-- COMMAND ----------

SELECT table_name, column_name, data_type
FROM samples.information_schema.columns
WHERE table_schema = 'tpch'
ORDER BY table_name, ordinal_position;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Row counts per table:** useful on the ERD slide to show the size of each entity.

-- COMMAND ----------

SELECT 'region' AS table_name, COUNT(*) AS row_count FROM samples.tpch.region
UNION ALL SELECT 'nation',   COUNT(*) FROM samples.tpch.nation
UNION ALL SELECT 'customer', COUNT(*) FROM samples.tpch.customer
UNION ALL SELECT 'orders',   COUNT(*) FROM samples.tpch.orders
UNION ALL SELECT 'lineitem', COUNT(*) FROM samples.tpch.lineitem
UNION ALL SELECT 'supplier', COUNT(*) FROM samples.tpch.supplier
UNION ALL SELECT 'part',     COUNT(*) FROM samples.tpch.part
UNION ALL SELECT 'partsupp', COUNT(*) FROM samples.tpch.partsupp;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **Relationship check:** do the keys actually join? Orders with no matching customer would be orphans. Also count customers who never ordered.

-- COMMAND ----------

SELECT
  (SELECT COUNT(*) FROM samples.tpch.orders o
     LEFT JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
     WHERE c.c_custkey IS NULL)                                   AS orders_without_customer,
  (SELECT COUNT(*) FROM samples.tpch.customer c
     WHERE NOT EXISTS (SELECT 1 FROM samples.tpch.orders o WHERE o.o_custkey = c.c_custkey)) AS customers_with_no_orders,
  (SELECT COUNT(*) FROM samples.tpch.customer)                    AS total_customers;

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## Q9. New customers placing an order each quarter
-- MAGIC
-- MAGIC **Definition:** a customer is "new" in the quarter of their *first ever* order.
-- MAGIC Step 1 finds each customer's first order date; step 2 counts customers by the quarter of that date.

-- COMMAND ----------

WITH first_orders AS (
  SELECT o_custkey, MIN(o_orderdate) AS first_order_date
  FROM samples.tpch.orders
  GROUP BY o_custkey
)
SELECT
  CONCAT(year(first_order_date), '-Q', quarter(first_order_date)) AS year_quarter,
  COUNT(*)                                                         AS new_customers,
  SUM(COUNT(*)) OVER (ORDER BY year(first_order_date), quarter(first_order_date)) AS cumulative_customers
FROM first_orders
GROUP BY year(first_order_date), quarter(first_order_date)
ORDER BY year(first_order_date), quarter(first_order_date);

-- COMMAND ----------

-- MAGIC %md
-- MAGIC **What to notice (say this on the slide):** the data starts in a particular quarter, so *every* customer looks "new" at the beginning.
-- MAGIC The first few quarters are inflated because we can't see orders from before the data starts. New-customer counts then fall sharply as the pool of customers who haven't ordered yet runs out.
-- MAGIC Click **+ → Visualization → Bar** (x = year_quarter, y = new_customers) for the chart.

-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Part 1: all results in one table
-- MAGIC Run the cell below (Shift+Enter). When it finishes, click the **download arrow** under the result, choose **Download as CSV**, and upload that file to Claude.
-- MAGIC It can take a minute because it reads the large `tpch` tables.

-- COMMAND ----------

WITH trips AS (
  SELECT *, timestampdiff(MINUTE, tpep_pickup_datetime, tpep_dropoff_datetime) AS dur
  FROM samples.nyctaxi.trips
),
s AS (
  SELECT
    COUNT(*)                                            AS total_trips,
    MIN(tpep_pickup_datetime)                           AS first_pickup,
    MAX(tpep_pickup_datetime)                           AS last_pickup,
    COUNT(DISTINCT DATE(tpep_pickup_datetime))          AS distinct_days,
    ROUND(MIN(trip_distance), 2)                        AS min_distance,
    ROUND(AVG(trip_distance), 2)                        AS avg_distance,
    ROUND(percentile_approx(trip_distance, 0.5), 2)     AS median_distance,
    ROUND(percentile_approx(trip_distance, 0.99), 2)    AS p99_distance,
    ROUND(MAX(trip_distance), 2)                        AS max_distance,
    ROUND(MIN(fare_amount), 2)                          AS min_fare,
    ROUND(AVG(fare_amount), 2)                          AS avg_fare,
    ROUND(percentile_approx(fare_amount, 0.5), 2)       AS median_fare,
    ROUND(percentile_approx(fare_amount, 0.99), 2)      AS p99_fare,
    ROUND(MAX(fare_amount), 2)                          AS max_fare,
    ROUND(AVG(dur), 1)                                  AS avg_duration_min,
    MAX(dur)                                            AS max_duration_min,
    COUNT(DISTINCT pickup_zip)                          AS distinct_pickup_zips,
    COUNT(DISTINCT dropoff_zip)                         AS distinct_dropoff_zips,
    SUM(CASE WHEN pickup_zip  IS NULL THEN 1 ELSE 0 END) AS null_pickup_zip,
    SUM(CASE WHEN dropoff_zip IS NULL THEN 1 ELSE 0 END) AS null_dropoff_zip,
    SUM(CASE WHEN fare_amount IS NULL THEN 1 ELSE 0 END) AS null_fare,
    SUM(CASE WHEN fare_amount < 0 THEN 1 ELSE 0 END)     AS negative_fare,
    SUM(CASE WHEN fare_amount = 0 THEN 1 ELSE 0 END)     AS zero_fare,
    SUM(CASE WHEN trip_distance = 0 THEN 1 ELSE 0 END)   AS zero_distance,
    SUM(CASE WHEN trip_distance = 0 AND dur < 1 THEN 1 ELSE 0 END)          AS zero_distance_under_1_min,
    SUM(CASE WHEN trip_distance = 0 AND fare_amount = 2.5 THEN 1 ELSE 0 END) AS zero_distance_fare_2_50,
    SUM(CASE WHEN trip_distance = 0 AND fare_amount > 20 THEN 1 ELSE 0 END)  AS zero_distance_fare_over_20,
    SUM(CASE WHEN trip_distance > 100 THEN 1 ELSE 0 END)  AS distance_over_100,
    SUM(CASE WHEN fare_amount > 250 THEN 1 ELSE 0 END)    AS fare_over_250,
    SUM(CASE WHEN tpep_dropoff_datetime <= tpep_pickup_datetime THEN 1 ELSE 0 END) AS dropoff_not_after_pickup,
    SUM(CASE WHEN dur > 180 THEN 1 ELSE 0 END)            AS trip_over_3_hours,
    SUM(CASE WHEN dur > 0 AND trip_distance / (dur / 60.0) > 80 THEN 1 ELSE 0 END) AS speed_over_80_mph,
    ROUND(SUM(fare_amount), 2)                            AS total_fare_all,
    ROUND(SUM(CASE WHEN fare_amount > 0 AND trip_distance > 0
                    AND tpep_dropoff_datetime > tpep_pickup_datetime THEN fare_amount END), 2) AS total_fare_clean,
    SUM(CASE WHEN fare_amount > 0 AND trip_distance > 0
              AND tpep_dropoff_datetime > tpep_pickup_datetime THEN 1 ELSE 0 END)          AS trips_clean
  FROM trips
),
q6 AS (
  SELECT 1 AS part, CAST(pos AS BIGINT) AS n, 'Q6 profile and anomalies' AS section, kv.m AS metric, kv.v AS value
  FROM s
  LATERAL VIEW posexplode(array(
    named_struct('m','total_trips','v',CAST(total_trips AS STRING)),
    named_struct('m','first_pickup','v',CAST(first_pickup AS STRING)),
    named_struct('m','last_pickup','v',CAST(last_pickup AS STRING)),
    named_struct('m','distinct_days','v',CAST(distinct_days AS STRING)),
    named_struct('m','min_distance','v',CAST(min_distance AS STRING)),
    named_struct('m','avg_distance','v',CAST(avg_distance AS STRING)),
    named_struct('m','median_distance','v',CAST(median_distance AS STRING)),
    named_struct('m','p99_distance','v',CAST(p99_distance AS STRING)),
    named_struct('m','max_distance','v',CAST(max_distance AS STRING)),
    named_struct('m','min_fare','v',CAST(min_fare AS STRING)),
    named_struct('m','avg_fare','v',CAST(avg_fare AS STRING)),
    named_struct('m','median_fare','v',CAST(median_fare AS STRING)),
    named_struct('m','p99_fare','v',CAST(p99_fare AS STRING)),
    named_struct('m','max_fare','v',CAST(max_fare AS STRING)),
    named_struct('m','avg_duration_min','v',CAST(avg_duration_min AS STRING)),
    named_struct('m','max_duration_min','v',CAST(max_duration_min AS STRING)),
    named_struct('m','distinct_pickup_zips','v',CAST(distinct_pickup_zips AS STRING)),
    named_struct('m','distinct_dropoff_zips','v',CAST(distinct_dropoff_zips AS STRING)),
    named_struct('m','null_pickup_zip','v',CAST(null_pickup_zip AS STRING)),
    named_struct('m','null_dropoff_zip','v',CAST(null_dropoff_zip AS STRING)),
    named_struct('m','null_fare','v',CAST(null_fare AS STRING)),
    named_struct('m','negative_fare','v',CAST(negative_fare AS STRING)),
    named_struct('m','zero_fare','v',CAST(zero_fare AS STRING)),
    named_struct('m','zero_distance','v',CAST(zero_distance AS STRING)),
    named_struct('m','zero_distance_under_1_min','v',CAST(zero_distance_under_1_min AS STRING)),
    named_struct('m','zero_distance_fare_2_50','v',CAST(zero_distance_fare_2_50 AS STRING)),
    named_struct('m','zero_distance_fare_over_20','v',CAST(zero_distance_fare_over_20 AS STRING)),
    named_struct('m','distance_over_100','v',CAST(distance_over_100 AS STRING)),
    named_struct('m','fare_over_250','v',CAST(fare_over_250 AS STRING)),
    named_struct('m','dropoff_not_after_pickup','v',CAST(dropoff_not_after_pickup AS STRING)),
    named_struct('m','trip_over_3_hours','v',CAST(trip_over_3_hours AS STRING)),
    named_struct('m','speed_over_80_mph','v',CAST(speed_over_80_mph AS STRING)),
    named_struct('m','total_fare_all_trips','v',CAST(total_fare_all AS STRING)),
    named_struct('m','total_fare_clean_trips','v',CAST(total_fare_clean AS STRING)),
    named_struct('m','trips_clean','v',CAST(trips_clean AS STRING))
  )) e AS pos, kv
),
cells AS (
  SELECT date_format(tpep_pickup_datetime, 'EEEE') AS dow, hour(tpep_pickup_datetime) AS hr,
         ROUND(SUM(fare_amount), 2) AS rev, ROUND(AVG(trip_distance), 2) AS dist, COUNT(*) AS vol
  FROM trips GROUP BY 1, 2
),
cells_ranked AS (
  SELECT *, row_number() OVER (ORDER BY rev DESC) AS rk, COUNT(*) OVER () AS n_cells FROM cells
),
cells_clean AS (
  SELECT date_format(tpep_pickup_datetime, 'EEEE') AS dow, hour(tpep_pickup_datetime) AS hr,
         ROUND(SUM(fare_amount), 2) AS rev, ROUND(AVG(trip_distance), 2) AS dist, COUNT(*) AS vol,
         row_number() OVER (ORDER BY SUM(fare_amount) DESC) AS rk
  FROM trips
  WHERE fare_amount > 0 AND trip_distance > 0 AND tpep_dropoff_datetime > tpep_pickup_datetime
  GROUP BY 1, 2
),
fo AS (
  SELECT o_custkey, MIN(o_orderdate) AS d FROM samples.tpch.orders GROUP BY o_custkey
)
SELECT part, n, section, metric, value FROM (
  SELECT * FROM q6

  UNION ALL
  SELECT 2, CAST(rk AS BIGINT), 'Q7 top 15 and bottom 5 day-hour (all trips)',
         concat('#', rk, ' ', dow, ' ', lpad(CAST(hr AS STRING), 2, '0'), ':00'),
         concat('revenue=', rev, ' | avg_distance=', dist, ' | trips=', vol)
  FROM cells_ranked WHERE rk <= 15 OR rk > n_cells - 5

  UNION ALL
  SELECT 3, CAST(rk AS BIGINT), 'Q7 top 10 day-hour (anomalies excluded)',
         concat('#', rk, ' ', dow, ' ', lpad(CAST(hr AS STRING), 2, '0'), ':00'),
         concat('revenue=', rev, ' | avg_distance=', dist, ' | trips=', vol)
  FROM cells_clean WHERE rk <= 10

  UNION ALL
  SELECT 4, CAST(dayofweek(tpep_pickup_datetime) AS BIGINT), 'Q7 totals by day of week',
         date_format(tpep_pickup_datetime, 'EEEE'),
         concat('revenue=', ROUND(SUM(fare_amount), 2), ' | avg_distance=', ROUND(AVG(trip_distance), 2), ' | trips=', COUNT(*))
  FROM trips GROUP BY dayofweek(tpep_pickup_datetime), date_format(tpep_pickup_datetime, 'EEEE')

  UNION ALL
  SELECT 5, CAST(hour(tpep_pickup_datetime) AS BIGINT), 'Q7 totals by hour of day',
         lpad(CAST(hour(tpep_pickup_datetime) AS STRING), 2, '0'),
         concat('revenue=', ROUND(SUM(fare_amount), 2), ' | avg_distance=', ROUND(AVG(trip_distance), 2), ' | trips=', COUNT(*))
  FROM trips GROUP BY hour(tpep_pickup_datetime)

  UNION ALL SELECT 8, 1, 'Q8 row counts', 'region',   CAST(COUNT(*) AS STRING) FROM samples.tpch.region
  UNION ALL SELECT 8, 2, 'Q8 row counts', 'nation',   CAST(COUNT(*) AS STRING) FROM samples.tpch.nation
  UNION ALL SELECT 8, 3, 'Q8 row counts', 'customer', CAST(COUNT(*) AS STRING) FROM samples.tpch.customer
  UNION ALL SELECT 8, 4, 'Q8 row counts', 'orders',   CAST(COUNT(*) AS STRING) FROM samples.tpch.orders
  UNION ALL SELECT 8, 5, 'Q8 row counts', 'lineitem', CAST(COUNT(*) AS STRING) FROM samples.tpch.lineitem
  UNION ALL SELECT 8, 6, 'Q8 row counts', 'supplier', CAST(COUNT(*) AS STRING) FROM samples.tpch.supplier
  UNION ALL SELECT 8, 7, 'Q8 row counts', 'part',     CAST(COUNT(*) AS STRING) FROM samples.tpch.part
  UNION ALL SELECT 8, 8, 'Q8 row counts', 'partsupp', CAST(COUNT(*) AS STRING) FROM samples.tpch.partsupp
  UNION ALL SELECT 8, 9, 'Q8 relationship checks', 'orders_without_customer', CAST(COUNT(*) AS STRING)
    FROM samples.tpch.orders o LEFT ANTI JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
  UNION ALL SELECT 8, 10, 'Q8 relationship checks', 'customers_with_no_orders', CAST(COUNT(*) AS STRING)
    FROM samples.tpch.customer c LEFT ANTI JOIN samples.tpch.orders o ON o.o_custkey = c.c_custkey
  UNION ALL SELECT 8, 11, 'Q8 relationship checks', 'first_order_date', CAST(MIN(o_orderdate) AS STRING) FROM samples.tpch.orders
  UNION ALL SELECT 8, 12, 'Q8 relationship checks', 'last_order_date',  CAST(MAX(o_orderdate) AS STRING) FROM samples.tpch.orders

  UNION ALL
  SELECT 9, CAST(year(d) * 10 + quarter(d) AS BIGINT), 'Q9 new customers per quarter',
         concat(year(d), '-Q', quarter(d)), CAST(COUNT(*) AS STRING)
  FROM fo GROUP BY year(d), quarter(d)

  UNION ALL
  SELECT 10, CAST(year(o_orderdate) * 10 + quarter(o_orderdate) AS BIGINT), 'Q9 context: all orders per quarter',
         concat(year(o_orderdate), '-Q', quarter(o_orderdate)), CAST(COUNT(*) AS STRING)
  FROM samples.tpch.orders GROUP BY year(o_orderdate), quarter(o_orderdate)
)
ORDER BY part, n;

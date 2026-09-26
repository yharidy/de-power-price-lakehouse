-- Silver, stage 1: explode the day-ahead price payload into one row per
-- 15-minute interval.
CREATE OR REFRESH STREAMING TABLE price_clean_staged
(
    CONSTRAINT valid_price EXPECT (day_ahead_price IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT valid_timestamp EXPECT (timestamp_utc IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Exploded, not-yet-deduplicated day-ahead price records for the DE-LU bidding zone.'
AS
SELECT
  country,
  bidding_zone,
  unit,
  to_timestamp(generated_at) AS generated_at_utc,
  to_timestamp(data_record.timestamp) AS timestamp_utc,
  data_record.values.day_ahead_price AS day_ahead_price
FROM STREAM(IDENTIFIER('${bronze_price_table}'))
LATERAL VIEW OUTER explode(data) AS data_record;

-- Silver, stage 2: deduplicate on timestamp_utc, keeping the most
-- recently generated record per key. 
CREATE OR REFRESH STREAMING TABLE price_clean
COMMENT 'Cleaned, deduplicated day-ahead electricity price (EUR/MWh) for the DE-LU bidding zone, one row per 15-minute interval.';

CREATE FLOW price_clean_flow AS AUTO CDC INTO price_clean
FROM STREAM(price_clean_staged)
KEYS (timestamp_utc)
SEQUENCE BY generated_at_utc
STORED AS SCD TYPE 1;
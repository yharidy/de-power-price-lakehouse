CREATE OR REFRESH STREAMING TABLE public_power_clean_staged
(
    CONSTRAINT valid_value EXPECT (value IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT valid_timestamp EXPECT (timestamp_utc IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Exploded, not-yet-deduplicated generation records by production type (MW) for Germany.'
AS
SELECT
  country,
  unit,
  to_timestamp(generated_at) AS generated_at_utc,
  to_timestamp(data_record.timestamp) AS timestamp_utc,
  value_type,
  value
FROM STREAM(IDENTIFIER('${bronze_public_power_table}'))
LATERAL VIEW OUTER explode(data) AS data_record
LATERAL VIEW OUTER explode(
  from_json(to_json(data_record.values), 'map<string,double>')
) AS value_type, value;


-- Silver, stage 2: deduplicate on (timestamp_utc, value_type), keeping
-- the most recently generated record per key.
CREATE OR REFRESH STREAMING TABLE public_power_clean
COMMENT 'Cleaned, deduplicated generation by production type (MW) for Germany, one row per (timestamp, production_type).';
 
CREATE FLOW public_power_clean_flow AS AUTO CDC INTO public_power_clean
FROM STREAM(public_power_clean_staged)
KEYS (timestamp_utc, value_type)
SEQUENCE BY generated_at_utc
STORED AS SCD TYPE 1;
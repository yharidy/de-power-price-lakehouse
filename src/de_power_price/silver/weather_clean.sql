-- Silver, stage 1: explode weather observations and join each one to its
-- reporting station's metadata.
CREATE OR REFRESH STREAMING TABLE weather_clean_staged
(
    CONSTRAINT valid_temperature EXPECT (temperature IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT valid_timestamp EXPECT (timestamp_utc IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Exploded, not-yet-deduplicated hourly weather observations with reporting station metadata.'
AS
WITH exploded AS (
  SELECT
    w,
    element_at(filter(sources, s -> s.id = w.source_id), 1) AS station,
    _ingested_at
  FROM STREAM(IDENTIFIER('${bronze_weather_table}'))
  LATERAL VIEW OUTER explode(weather) AS w
)
SELECT
  to_timestamp(w.timestamp) AS timestamp_utc,
  station.station_name,
  station.lat,
  station.lon,
  w.temperature,
  w.precipitation,
  w.wind_direction,
  w.wind_speed,
  w.condition,
  w.relative_humidity,
  w.cloud_cover,
  _ingested_at
FROM exploded;

-- Silver, stage 2: deduplicate on (timestamp_utc, station_name), keeping
-- the most recently ingested record per key.
CREATE OR REFRESH STREAMING TABLE weather_clean
COMMENT 'Cleaned, deduplicated hourly weather observations with reporting station metadata, one row per (timestamp, station).';

CREATE FLOW weather_clean_flow AS AUTO CDC INTO weather_clean
FROM STREAM(weather_clean_staged)
KEYS (timestamp_utc, station_name)
SEQUENCE BY _ingested_at
STORED AS SCD TYPE 1;
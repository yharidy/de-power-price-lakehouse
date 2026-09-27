-- Gold: pivot generation from long format (silver) to wide format.
CREATE OR REFRESH MATERIALIZED VIEW public_power_pivoted
AS
SELECT *
FROM (
  SELECT timestamp_utc, value_type, value FROM IDENTIFIER('${catalog}.${silver_schema}.public_power_clean')
)
PIVOT (
  first(value) FOR value_type IN (
    'wind_onshore', 'wind_offshore', 'solar', 'fossil_gas',
    'fossil_hard_coal', 'fossil_brown_coal_lignite',
    'renewable_share_of_generation', 'renewable_share_of_load',
    'load', 'residual_load'
  )
)
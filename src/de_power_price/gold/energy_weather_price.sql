-- Join power generation, price and weather data
CREATE OR REFRESH MATERIALIZED VIEW energy_weather_price AS
SELECT power.*,
  price.day_ahead_price,   
  weather.station_name,
  weather.lat,
  weather.lon,
  weather.temperature,
  weather.precipitation,
  weather.wind_direction,
  weather.wind_speed,
  weather.condition,
  weather.relative_humidity,
  weather.cloud_cover
FROM public_power_pivoted AS power
INNER JOIN IDENTIFIER('${catalog}.${silver_schema}.price_clean') AS price
  ON power.timestamp_utc = price.timestamp_utc
LEFT JOIN IDENTIFIER('${catalog}.${silver_schema}.weather_clean') AS weather
  ON date_trunc('hour', power.timestamp_utc) = date_trunc('hour', weather.timestamp_utc)


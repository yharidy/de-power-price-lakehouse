CREATE OR REPLACE VIEW negative_prices 
AS
SELECT * 
FROM energy_weather_price
WHERE day_ahead_price < 0.0
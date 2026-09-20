# Map of env => catalog name, e.g. { dev = "power_dev", prod = "power_prod" }
# output "catalog_names" {
#   description = "Catalog name per environment"
#   value       = { for env, c in databricks_catalog.env : env => c.name }
# }

# Map of e.g. "dev_bronze" to "de_power_price_dev.bronze"
output "schema_full_names" {
  description = "Fully qualified schema names (catalog.schema)"
  value       = { for key, schema in databricks_schema.layer : key => "${schema.catalog_name}.${schema.name}" }
}

# Map of env => landing volume path, e.g. /Volumes/power_dev/bronze/landing
output "landing_volume_paths" {
  description = "Path to the landing volume within each catalog (bronze layer)"
  value = {
    for env, volume in databricks_volume.landing : env => "/Volumes/${volume.catalog_name}/${volume.schema_name}/${volume.name}"
  }
}

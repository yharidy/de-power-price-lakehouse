# Databricks' Free tier doesn't create a dedicated maetastore. Terraform can't create catalogs on the shared metastore.
# resource "databricks_catalog" "env" {
#   for_each = toset(var.environment)
#   name     = "de_power_price_${each.key}"
#   comment  = "DE power price lakehouse (${each.key})"
# }

resource "databricks_schema" "layer" {
  for_each = { # build all combinations of env and layer
    for p in setproduct(var.environment, var.layers) :
    "${p[0]}_${p[1]}" => { env = p[0], layer = p[1] } # "dev_bronze"  = { env = "dev",  layer = "bronze" }
  }
  catalog_name = var.catalog_name
  name         = each.key
}

resource "databricks_volume" "landing" {
  for_each     = toset(var.environment)
  catalog_name = var.catalog_name
  schema_name  = databricks_schema.layer["${each.key}_bronze"].name
  name         = "landing"
  volume_type  = "MANAGED"
}

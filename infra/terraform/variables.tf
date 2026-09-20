variable "databricks_profile" {
  type        = string
  description = "Profile name in ~/.databrickscfg"
  default     = "free"
}

variable "layers" {
  default = ["bronze", "silver", "gold"]
}

variable "environment" {
  default = ["dev", "prod"]
}

variable "catalog_name" {
  type        = string
  description = "Existing catalog to create schemas in"

}

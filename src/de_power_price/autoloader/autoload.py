import argparse
import logging
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def run_autoloader(spark: SparkSession, source_path: Path, checkpoint_root: Path, target_table: str, schema_hints: str | None = None):
    # enable Change Data Feed
    spark.conf.set(
        "spark.databricks.delta.properties.defaults.enableChangeDataFeed", "true")
    checkpoint_location = str(checkpoint_root / "_checkpoints")
    schema_location = str(checkpoint_root / "_schema")

    reader = spark.readStream.format("cloudFiles").option("cloudFiles.format", "json").option("cloudFiles.schemaLocation", schema_location).option(
        "cloudFiles.inferColumnTypes", "true").option("cloudFiles.schemaEvolutionMode", "addNewColumns")
    if schema_hints:
        reader.option("cloudFiles.schemaHints", schema_hints)

    df = reader.load(str(source_path))
    df = df.select("*", F.col("_metadata.file_name").alias("_source_filename"),
                   F.col("_metadata.file_path").alias("_source_file_path"),
                   F.col("_metadata.file_modification_time").alias(
                       "_source_file_modified_at"),
                   F.current_timestamp().alias("_ingested_at"))

    query = df.writeStream.option("checkpointLocation", checkpoint_location).trigger(
        availableNow=True).toTable(target_table)

    query.awaitTermination()
    logger.info(f"Finished ingesting {source_path!s}->{target_table}")


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-path", required=True,
                        help="Directory storing the files to be ingested.")
    parser.add_argument("--checkpoint-root", required=True,
                        help="Root directory where checkpoints in a _checkpoints subdirectory and schemas are stored in a _schema subdirectory.")
    parser.add_argument("--target-table", required=True,
                        help="Fully qualified name of target table (catalog.schema.table)")
    parser.add_argument(
        "--schema-hints", default=None,
        help='e.g. "values map<string,double>" (optional)',
    )
    args = parser.parse_args()
    source_path = Path(args.source_path)
    if not source_path.exists():
        raise ValueError(f"Source path {source_path} does not exist.")
    checkpoint_root = Path(args.checkpoint_root)

    # create session
    spark = SparkSession.builder.getOrCreate()
    run_autoloader(
        spark,
        source_path,
        checkpoint_root,
        args.target_table,
        schema_hints=args.schema_hints
    )


if __name__ == "__main__":
    cli()

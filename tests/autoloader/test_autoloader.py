from unittest.mock import MagicMock, call, patch

import pytest

from de_power_price.autoloader import autoload


class TestRunAutoLoaderOptions:
    @pytest.fixture(autouse=True)
    def mock_spark_functions(self):
        with patch("de_power_price.autoloader.autoload.F") as mock_F:
            mock_F.col.return_value = MagicMock()
            mock_F.current_timestamp.return_value = MagicMock()
            yield mock_F

    def _build_mock_spark(self):
        spark = MagicMock()
        reader = MagicMock()
        reader.format.return_value = reader
        reader.option.return_value = reader
        reader.load.return_value = MagicMock()  # the "DataFrame"
        spark.readStream = reader
        return spark, reader

    def test_schema_hints_applied_when_provided(self, tmp_path):
        spark, reader = self._build_mock_spark()
        df = reader.load.return_value
        df.select.return_value = df
        writer = df.writeStream
        writer.option.return_value = writer
        writer.trigger.return_value = writer
        writer.toTable.return_value = MagicMock()

        autoload.run_autoloader(
            spark,
            tmp_path / "src",
            tmp_path / "ckpt",
            "cat.schema.table",
            schema_hints="values map<string,double>",
        )
        assert call("cloudFiles.schemaHints", "values map<string,double>"
                    ) in reader.option.call_args_list

    def test_schema_hints_omitted_when_not_provided(self, tmp_path):
        spark, reader = self._build_mock_spark()
        df = reader.load.return_value
        df.select.return_value = df
        writer = df.writeStream
        writer.option.return_value = writer
        writer.trigger.return_value = writer
        writer.toTable.return_value = MagicMock()

        autoload.run_autoloader(
            spark, tmp_path / "src", tmp_path / "ckpt", "cat.schema.table"
        )

        option_keys = {c.args[0] for c in reader.option.call_args_list}
        assert "cloudFiles.schemaHints" not in option_keys

    def test_checkpoint_and_schema_locations_are_strings_under_checkpoint_root(
        self, tmp_path
    ):
        spark, reader = self._build_mock_spark()
        df = reader.load.return_value
        df.select.return_value = df
        writer = df.writeStream
        writer.option.return_value = writer
        writer.trigger.return_value = writer
        writer.toTable.return_value = MagicMock()

        checkpoint_root = tmp_path / "ckpt"
        autoload.run_autoloader(
            spark, tmp_path / "src", checkpoint_root, "cat.schema.table"
        )

        option_calls = {
            c.args[0]: c.args[1] for c in reader.option.call_args_list
        }
        assert option_calls["cloudFiles.schemaLocation"] == str(
            checkpoint_root / "_schema"
        )
        writer_option_calls = {
            c.args[0]: c.args[1] for c in writer.option.call_args_list
        }
        assert writer_option_calls["checkpointLocation"] == str(
            checkpoint_root / "_checkpoints"
        )
        # both must be strings, not Path objects
        assert isinstance(option_calls["cloudFiles.schemaLocation"], str)
        assert isinstance(writer_option_calls["checkpointLocation"], str)

    def test_trigger_is_available_now_not_continuous(self, tmp_path):
        spark, reader = self._build_mock_spark()
        df = reader.load.return_value
        df.select.return_value = df
        writer = df.writeStream
        writer.option.return_value = writer
        writer.trigger.return_value = writer
        writer.toTable.return_value = MagicMock()

        autoload.run_autoloader(
            spark, tmp_path / "src", tmp_path / "ckpt", "cat.schema.table"
        )

        writer.trigger.assert_called_once_with(availableNow=True)

    def test_target_table_passed_through(self, tmp_path):
        spark, reader = self._build_mock_spark()
        df = reader.load.return_value
        df.select.return_value = df
        writer = df.writeStream
        writer.option.return_value = writer
        writer.trigger.return_value = writer
        writer.toTable.return_value = MagicMock()

        autoload.run_autoloader(
            spark, tmp_path / "src", tmp_path / "ckpt", "cat.bronze.price_raw"
        )

        writer.toTable.assert_called_once_with("cat.bronze.price_raw")

import unittest
from unittest.mock import patch

from scripts import register_glue_tables


class RegisterGlueTablesTests(unittest.TestCase):
    def test_sample_schema_rejects_empty_s3_path(self):
        with patch.object(register_glue_tables.wr.s3, "list_objects", return_value=[]):
            with self.assertRaisesRegex(ValueError, "No Parquet files found"):
                register_glue_tables._sample_schema("s3://bucket/curated/fact_sales/")


if __name__ == "__main__":
    unittest.main()

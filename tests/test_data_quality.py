import unittest

import pandas as pd

from src.etl.data_quality import has_blocking_failures, run_quality_checks


class DataQualityTests(unittest.TestCase):
    def test_warning_checks_do_not_block_pipeline(self):
        fact = pd.DataFrame(
            {
                "Fact_ID": [1, 2],
                "Customer_ID": ["C1", "C1"],
                "Product_ID": [10, 10],
                "Date_Key": [202001, 202001],
                "Geo_Key": ["G1", "G1"],
                "Revenue": [100.0, 100.0],
                "Profit": [20.0, 20.0],
                "Quantity_Sold": [1, 1],
                "Unit_Sale_Price": [100.0, 100.0],
                "Quarter": ["Q1", "Q1"],
                "Year": [2020, 2020],
                "Is_Full_Year": [False, False],
            }
        )
        tables = {
            "FACT_Sales": fact,
            "DIM_Customer": pd.DataFrame({"Customer_ID": ["C1"]}),
            "DIM_Product": pd.DataFrame({"Product_ID": [10]}),
            "DIM_Date": pd.DataFrame({"Date_Key": [202001], "Year": [2020], "Quarter": ["Q1"]}),
            "DIM_Geography": pd.DataFrame({"Geo_Key": ["G1"]}),
        }

        report = run_quality_checks(tables)

        duplicate_warning = report.loc[
            report["check_name"] == "fact_sales_possible_duplicate_transactions"
        ].iloc[0]
        self.assertEqual(duplicate_warning["level"], "WARNING")
        self.assertEqual(duplicate_warning["status"], "FAIL")
        self.assertFalse(has_blocking_failures(report))

    def test_error_checks_block_pipeline(self):
        fact = pd.DataFrame(
            {
                "Fact_ID": [1],
                "Customer_ID": [None],
                "Product_ID": [10],
                "Date_Key": [202001],
                "Geo_Key": ["G1"],
                "Revenue": [100.0],
                "Profit": [20.0],
                "Quarter": ["Q1"],
                "Year": [2020],
                "Is_Full_Year": [False],
            }
        )
        tables = {
            "FACT_Sales": fact,
            "DIM_Customer": pd.DataFrame({"Customer_ID": ["C1"]}),
            "DIM_Product": pd.DataFrame({"Product_ID": [10]}),
            "DIM_Date": pd.DataFrame({"Date_Key": [202001], "Year": [2020], "Quarter": ["Q1"]}),
            "DIM_Geography": pd.DataFrame({"Geo_Key": ["G1"]}),
        }

        report = run_quality_checks(tables)

        self.assertTrue(has_blocking_failures(report))


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

from src.data_loading import add_quarter_index
from src.feature_engineering import make_quarterly_series


class SmokeTests(unittest.TestCase):
    def test_quarter_index_and_series(self):
        fact = pd.DataFrame(
            {
                "Year_Quarter": ["2019-Q1", "2019-Q2", "2019-Q1"],
                "Year": [2019, 2019, 2019],
                "Quarter_Num": [1, 2, 1],
                "Revenue": [100, 200, 50],
                "Profit": [10, 20, 5],
            }
        )
        fact, quarter_order = add_quarter_index(fact)
        self.assertEqual(list(quarter_order["Quarter_Idx"]), [1, 2])
        qdf = make_quarterly_series(fact)
        self.assertEqual(float(qdf.loc[qdf["Year_Quarter"] == "2019-Q1", "Revenue"].iloc[0]), 150)
        self.assertEqual(float(qdf.loc[qdf["Year_Quarter"] == "2019-Q1", "Profit"].iloc[0]), 15)


if __name__ == "__main__":
    unittest.main()


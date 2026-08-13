#!/usr/bin/env python3
"""路网动态调节系数计算器回归测试。"""

import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.net_risk.config.config_manager import ConfigManager
from src.net_risk.risk_calculation.dynamic_coefficient_calculator import (
    DynamicCoefficientCalculator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DynamicCoefficientCalculatorTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "net_risk.ini"
        shutil.copy2(PROJECT_ROOT / "config" / "net_risk.ini", self.config_path)
        self.config_manager = ConfigManager(str(self.config_path))

    def test_loads_thresholds_parsed_by_config_manager(self):
        calculator = DynamicCoefficientCalculator(self.config_manager)

        self.assertEqual(
            self.config_manager.get_saturation_thresholds(),
            calculator.saturation_thresholds,
        )
        self.assertEqual(
            sorted(
                self.config_manager.get_equilibrium_thresholds(),
                key=lambda item: item["min"],
                reverse=True,
            ),
            calculator.equilibrium_thresholds,
        )

    def test_equilibrium_threshold_can_raise_dynamic_coefficient(self):
        calculator = DynamicCoefficientCalculator(self.config_manager)
        merged_data = pd.DataFrame(
            [
                {
                    "company": "渝东公司",
                    "peak_hour_flow": 10.0,
                    "design_flow": 100.0,
                    "length": 1.0,
                    "saturation": 0.10,
                },
                {
                    "company": "渝东公司",
                    "peak_hour_flow": 35.0,
                    "design_flow": 100.0,
                    "length": 1.0,
                    "saturation": 0.35,
                },
            ]
        )

        dynamic_coefficients, _, equilibrium = (
            calculator.calculate_dynamic_coefficient(merged_data)
        )

        self.assertAlmostEqual(0.444444, equilibrium["渝东公司"], places=6)
        self.assertGreater(dynamic_coefficients["渝东公司"], 1.0)


if __name__ == "__main__":
    unittest.main()

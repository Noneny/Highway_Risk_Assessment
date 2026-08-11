#!/usr/bin/env python3
"""路网风险配置管理器测试。"""

import shutil
import tempfile
import unittest
from pathlib import Path

from src.net_risk.config.config_manager import ConfigManager


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "net_risk.ini"
        shutil.copy2(PROJECT_ROOT / "config" / "net_risk.ini", self.config_path)
        self.config_manager = ConfigManager(str(self.config_path))

    def test_config_manager_initialization(self):
        self.assertTrue(self.config_path.exists())

    def test_get_all_config(self):
        config = self.config_manager.get_all_config()
        self.assertIn("database", config)
        self.assertIn("paths", config)
        self.assertIn("period", config)

    def test_database_config_uses_unified_output_configuration(self):
        database = self.config_manager.get_database_config()
        self.assertIn("host", database)
        self.assertIn("database", database)
        self.assertIn("net_table", database)

    def test_update_config_persists_value(self):
        self.config_manager.update_config("SETTINGS", "log_level", "DEBUG")
        reloaded = ConfigManager(str(self.config_path))
        self.assertEqual("DEBUG", reloaded.get_settings()["log_level"])

    def test_save_config_adds_section(self):
        self.config_manager.save_config({"TEST": {"test_key": "test_value"}})
        reloaded = ConfigManager(str(self.config_path))
        self.assertEqual("test_value", reloaded.config.get("TEST", "test_key"))


if __name__ == "__main__":
    unittest.main()

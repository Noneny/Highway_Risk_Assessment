import configparser
import os
from pathlib import Path
from typing import Dict, Any, Optional

from src.db_config import get_belong_date, DB_CONFIG_PATH

BASE_DIR = Path(__file__).parent.parent.parent.resolve()
DEFAULT_CONFIG_PATH = str(BASE_DIR / "config" / "input_db.ini")


class InputConfigManager:
    DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_PATH

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = configparser.ConfigParser()
        self.base_dir = Path(self.config_path).parent.parent.resolve() if self.config_path else BASE_DIR
        self._ensure_config_exists()
        self._load_config()

    def _ensure_config_exists(self):
        config_file = Path(self.config_path)
        if not config_file.exists():
            print(f"配置文件 {self.config_path} 不存在，创建默认配置...")
            config_file.parent.mkdir(parents=True, exist_ok=True)
            self._create_default_config()

    def _create_default_config(self):
        self.config['DATABASE'] = {
            'host': 'localhost',
            'port': '3306',
            'user': 'root',
            'password': '',
            'database': 'freeway_risk_input1',
            'charset': 'utf8mb4',
        }
        self.config['EXPORT'] = {
            'belong_date': '2025-12-01',
            'point_alert_dir': 'data/input/weather_warnings',
            'other_dir': 'data/input',
        }
        self.config['ETC_TRAFFIC'] = {
            'input_dir': '../ETC_Data',
            'output_file': 'data/input/traffic_data/双月门架数据全量合并.csv',
            'output_filename': '双月门架数据全量合并.csv',
        }
        self.config['SETTINGS'] = {
            'encoding': 'utf-8-sig',
            'use_progress_bar': 'True',
            'remove_old_output': 'True',
            'dtype_str': 'True',
            'clean_data': 'True',
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        print(f"已创建默认配置文件: {self.config_path}")

    def _load_config(self):
        self.config.read(self.config_path, encoding='utf-8')

    def resolve_path(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()

    def get_database_config(self) -> Dict[str, Any]:
        section = 'DATABASE'
        if not self.config.has_section(section):
            return {}
        def env(name: str, fallback: str) -> str:
            value = os.getenv(name)
            return value if value not in (None, '') else fallback

        return {
            'host': env('RISK_INPUT_DB_HOST', self.config.get(section, 'host', fallback='localhost')),
            'port': int(env('RISK_INPUT_DB_PORT', str(self.config.getint(section, 'port', fallback=3306)))),
            'user': env('RISK_INPUT_DB_USER', self.config.get(section, 'user', fallback='root')),
            'password': env('RISK_INPUT_DB_PASSWORD', self.config.get(section, 'password', fallback='')),
            'database': env(
                'RISK_INPUT_DB_NAME',
                self.config.get(section, 'database', fallback='freeway_risk_input1'),
            ),
            'charset': env(
                'RISK_INPUT_DB_CHARSET', self.config.get(section, 'charset', fallback='utf8mb4')
            ),
        }

    def get_export_config(self) -> Dict[str, Any]:
        section = 'EXPORT'
        if not self.config.has_section(section):
            return {}
        return {
            'belong_date': get_belong_date(),
            'point_alert_dir': self.config.get(section, 'point_alert_dir', fallback='data/input/weather_warnings'),
            'other_dir': self.config.get(section, 'other_dir', fallback='data/input'),
        }

    def get_etc_traffic_config(self) -> Dict[str, Any]:
        section = 'ETC_TRAFFIC'
        if not self.config.has_section(section):
            return {}
        return {
            'input_dir': self.config.get(section, 'input_dir', fallback='../ETC_Data'),
            'output_file': self.config.get(section, 'output_file', fallback='data/input/traffic_data/双月门架数据全量合并.csv'),
            'output_filename': self.config.get(section, 'output_filename', fallback='双月门架数据全量合并.csv'),
        }

    def get_settings(self) -> Dict[str, Any]:
        section = 'SETTINGS'
        if not self.config.has_section(section):
            return {}
        return {
            'encoding': self.config.get(section, 'encoding', fallback='utf-8-sig'),
            'use_progress_bar': self.config.getboolean(section, 'use_progress_bar', fallback=True),
            'remove_old_output': self.config.getboolean(section, 'remove_old_output', fallback=True),
            'dtype_str': self.config.getboolean(section, 'dtype_str', fallback=True),
            'clean_data': self.config.getboolean(section, 'clean_data', fallback=True),
        }

    def update_belong_date(self, new_date: str) -> bool:
        try:
            from datetime import datetime
            datetime.strptime(new_date, '%Y-%m-%d')
        except ValueError:
            print(f"日期格式错误，请使用YYYY-MM-DD格式")
            return False
        config = configparser.ConfigParser()
        config.read(DB_CONFIG_PATH, encoding='utf-8')
        if 'DATES' not in config:
            config['DATES'] = {}
        config['DATES']['belong_date'] = new_date
        with open(DB_CONFIG_PATH, 'w', encoding='utf-8') as f:
            config.write(f)
        print(f"已更新归属日期为: {new_date}")
        return True


_input_config_manager: Optional[InputConfigManager] = None


def get_input_config_manager(config_path: Optional[str] = None) -> InputConfigManager:
    global _input_config_manager
    if _input_config_manager is None:
        _input_config_manager = InputConfigManager(config_path)
    return _input_config_manager

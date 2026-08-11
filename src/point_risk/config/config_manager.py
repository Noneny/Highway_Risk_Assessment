"""
配置管理器 - 统一管理项目配置
整合所有分散的配置文件到一个 config.ini 文件中
"""

import configparser
import os
from pathlib import Path
from typing import Dict, Any, Optional

from src.db_config import get_belong_date

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CONFIG_PATH = str(BASE_DIR / "config" / "point_risk.ini")


class ConfigManager:
    """配置管理器类"""

    DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_PATH

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = configparser.ConfigParser()
        self.config.optionxform = str
        self._ensure_config_exists()
        self._load_config()

    def _ensure_config_exists(self):
        """确保配置文件存在，如果不存在则创建默认配置"""
        config_file = Path(self.config_path)

        if not config_file.exists():
            print(f"配置文件 {self.config_path} 不存在，创建默认配置...")
            config_file.parent.mkdir(parents=True, exist_ok=True)
            self._create_default_config()

    def _create_default_config(self):
        """创建默认配置文件"""
        # 文件路径配置
        self.config['PATHS'] = {
            # 输入文件
            'structure_excel': 'data/input/结构物监测基础信息表(1019)带门架方向.xlsx',
            'weather_json_pattern': 'data/input/weather_warnings/*.json',
            'gantry_excel': 'data/input/东南东北渝东门架信息(1).xlsx',
            'traffic_data_dir': 'data/input/traffic_data/',
            'traffic_risk_file1': 'data/input/2025年12月门架流量统计结果.xlsx',
            'traffic_risk_file2': 'data/input/2025年12月门架流量统计结果.xlsx',

            # 中间输出文件
            'base_risk_output': 'data/temp/结构点-基础风险值-动态风险值表.xlsx',
            'weather_warning_output': 'data/temp/new结构点预警天数统计.xlsx',
            'weather_updated_risk_output': 'data/temp/结构点-基础风险值-动态风险值表_更新.xlsx',
            'traffic_stat_output': 'data/temp/2025年12月门架流量统计结果.xlsx',
            'gantry_risk_output': 'data/temp/双月门架风险评估表.xlsx',
            'traffic_updated_risk_output': 'data/temp/结构点-基础风险值-动态风险值表_更新2.xlsx',

            # 最终输出文件
            'final_risk_output': 'data/output/全结构点通行风险值评价表.xlsx'
        }

        # 风险参数配置
        self.config['RISK_PARAMS'] = {
            # 基础风险映射
            'level_1_risk': '83',
            'level_2_risk': '72',
            'level_3_risk': '55',
            'level_4_risk': '48',

            # 气象预警风险叠加参数
            'weather_warnings_0': '1.0',
            'weather_warnings_1_10': '1.05',
            'weather_warnings_11_20': '1.08',
            'weather_warnings_above_20': '1.12',

            # 流量风险参数
            'reduction_base': '0.98',
            'risk_threshold': '1.0',

            # 最终风险等级阈值
            'low_risk_max': '60',
            'medium_risk_max': '80',
            'high_risk_max': '100'
        }

        # 气象预警参数
        self.config['WEATHER_PARAMS'] = {
            'warning_radius': '5',  # 预警半径(公里)
        }

        # 流量处理参数
        self.config['TRAFFIC_PARAMS'] = {
            'chunksize': '50000',
            'use_chunks': 'True',
            'auto_chunk_threshold_mb': '100',
            'truck_types': '一型货车,二型货车,三型货车,四型货车,五型货车,六型货车',
            'peak_hour_capacity': '3000',
            'min_speed': '5',
            'max_speed': '200',
            'min_time_diff_hours': '0.001',
            'congestion_high': '0.95',
            'congestion_medium': '0.85',
            'congestion_low': '0.6',
            'large_vehicle_ratio_high_low': '0.4',
            'large_vehicle_ratio_high_high': '0.6',
            'large_vehicle_ratio_medium_low': '0.3',
            'large_vehicle_ratio_medium_high': '0.7',
            'large_vehicle_ratio_low_low': '0.2',
            'large_vehicle_ratio_low_high': '0.8',
            'discrete_speed_high': '40',
            'discrete_speed_medium': '30',
            'discrete_speed_low': '20'
        }

        # ETC门架与附近结构点映射
        self.config['ETC_POINT_MAPPING'] = {
            '龙洞河特大桥右线': 'G004250001000220010',
            'G42沪蓉高速奉巫段K1318+385至K1318+560段检测点': 'G004250001000310010',
        }

        # 通用设置
        self.config['SETTINGS'] = {
            'drop_na': 'True',
            'encoding': 'utf-8'
        }

        # 写入配置文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

        print(f"已创建默认配置文件: {self.config_path}")
        print("请根据实际情况修改配置文件中的设置。")

    def _load_config(self):
        """加载配置文件"""
        self.config.optionxform = str
        self.config.read(self.config_path, encoding='utf-8')

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置（从统一 output_db.ini 读取）"""
        from src.db_config import get_output_db_config
        return get_output_db_config()

    def get_paths_config(self) -> Dict[str, str]:
        """获取文件路径配置"""
        return dict(self.config['PATHS'])

    def get_risk_params(self) -> Dict[str, Any]:
        """获取风险参数配置"""
        section = 'RISK_PARAMS'
        if not self.config.has_section(section):
            return {}

        return {
            'level_1_risk': self.config.getfloat(section, 'level_1_risk', fallback=83.0),
            'level_2_risk': self.config.getfloat(section, 'level_2_risk', fallback=72.0),
            'level_3_risk': self.config.getfloat(section, 'level_3_risk', fallback=55.0),
            'level_4_risk': self.config.getfloat(section, 'level_4_risk', fallback=48.0),
            'weather_warnings_0': self.config.getfloat(section, 'weather_warnings_0', fallback=1.0),
            'weather_warnings_1_10': self.config.getfloat(section, 'weather_warnings_1_10', fallback=1.05),
            'weather_warnings_11_20': self.config.getfloat(section, 'weather_warnings_11_20', fallback=1.08),
            'weather_warnings_above_20': self.config.getfloat(section, 'weather_warnings_above_20', fallback=1.12),
            'reduction_base': self.config.getfloat(section, 'reduction_base', fallback=0.98),
            'risk_threshold': self.config.getfloat(section, 'risk_threshold', fallback=1.0),
            'low_risk_max': self.config.getfloat(section, 'low_risk_max', fallback=60.0),
            'medium_risk_max': self.config.getfloat(section, 'medium_risk_max', fallback=80.0),
            'high_risk_max': self.config.getfloat(section, 'high_risk_max', fallback=100.0)
        }

    def get_weather_params(self) -> Dict[str, Any]:
        """获取气象预警参数"""
        section = 'WEATHER_PARAMS'
        if not self.config.has_section(section):
            return {'belong_date': get_belong_date()}

        return {
            'warning_radius': self.config.getfloat(section, 'warning_radius', fallback=5.0),
            'belong_date': get_belong_date()
        }

    def get_traffic_params(self) -> Dict[str, Any]:
        """获取流量处理参数"""
        section = 'TRAFFIC_PARAMS'
        if not self.config.has_section(section):
            return {}

        return {
            'chunksize': self.config.getint(section, 'chunksize', fallback=50000),
            'use_chunks': self.config.getboolean(section, 'use_chunks', fallback=True),
            'auto_chunk_threshold_mb': self.config.getint(section, 'auto_chunk_threshold_mb', fallback=100),
            'truck_types': self.config.get(section, 'truck_types',
                                          fallback='一型货车,二型货车,三型货车,四型货车,五型货车,六型货车').split(','),
            'peak_hour_capacity': self.config.getint(section, 'peak_hour_capacity', fallback=3000),
            'min_speed': self.config.getfloat(section, 'min_speed', fallback=5.0),
            'max_speed': self.config.getfloat(section, 'max_speed', fallback=200.0),
            'min_time_diff_hours': self.config.getfloat(section, 'min_time_diff_hours', fallback=0.001),
            'congestion_high': self.config.getfloat(section, 'congestion_high', fallback=0.95),
            'congestion_medium': self.config.getfloat(section, 'congestion_medium', fallback=0.85),
            'congestion_low': self.config.getfloat(section, 'congestion_low', fallback=0.6),
            'large_vehicle_ratio_high_low': self.config.getfloat(section, 'large_vehicle_ratio_high_low', fallback=0.4),
            'large_vehicle_ratio_high_high': self.config.getfloat(section, 'large_vehicle_ratio_high_high', fallback=0.6),
            'large_vehicle_ratio_medium_low': self.config.getfloat(section, 'large_vehicle_ratio_medium_low', fallback=0.3),
            'large_vehicle_ratio_medium_high': self.config.getfloat(section, 'large_vehicle_ratio_medium_high', fallback=0.7),
            'large_vehicle_ratio_low_low': self.config.getfloat(section, 'large_vehicle_ratio_low_low', fallback=0.2),
            'large_vehicle_ratio_low_high': self.config.getfloat(section, 'large_vehicle_ratio_low_high', fallback=0.8),
            'discrete_speed_high': self.config.getfloat(section, 'discrete_speed_high', fallback=40.0),
            'discrete_speed_medium': self.config.getfloat(section, 'discrete_speed_medium', fallback=30.0),
            'discrete_speed_low': self.config.getfloat(section, 'discrete_speed_low', fallback=20.0)
        }

    def get_etc_point_mapping(self) -> Dict[str, str]:
        """
        获取结构点与附近ETC门架的映射关系

        Returns:
            {nearby_point: etc_id}
        """
        section = 'ETC_POINT_MAPPING'
        if not self.config.has_section(section):
            return {}

        mapping = {}
        for key in self.config[section]:
            value = self.config.get(section, key)
            if value and value.strip():
                mapping[key] = value.strip()
        return mapping

    def get_settings(self) -> Dict[str, Any]:
        """获取通用设置"""
        section = 'SETTINGS'
        if not self.config.has_section(section):
            return {}

        return {
            'drop_na': self.config.getboolean(section, 'drop_na', fallback=True),
            'encoding': self.config.get(section, 'encoding', fallback='utf-8')
        }

    def get_all_config(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        return {
            'database': self.get_database_config(),
            'paths': self.get_paths_config(),
            'risk_params': self.get_risk_params(),
            'weather_params': self.get_weather_params(),
            'traffic_params': self.get_traffic_params(),
            'settings': self.get_settings()
        }

    def save_config(self, config_dict: Dict[str, Dict[str, Any]]):
        """
        保存配置到文件

        Args:
            config_dict: 配置字典，格式为 {section_name: {key: value}}
        """
        for section, items in config_dict.items():
            if not self.config.has_section(section):
                self.config.add_section(section)

            for key, value in items.items():
                self.config.set(section, key, str(value))

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

        print(f"配置已保存到: {self.config_path}")

    def update_config(self, section: str, key: str, value: Any):
        """
        更新单个配置项

        Args:
            section: 配置节名称
            key: 配置键
            value: 配置值
        """
        if not self.config.has_section(section):
            self.config.add_section(section)

        self.config.set(section, key, str(value))

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

        print(f"已更新配置: {section}.{key} = {value}")


# 单例模式实例
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """
    获取配置管理器实例（单例模式）

    Args:
        config_path: 配置文件路径

    Returns:
        ConfigManager实例
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path)

    return _config_manager
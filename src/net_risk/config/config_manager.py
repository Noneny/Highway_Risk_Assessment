"""
配置管理器 - 统一管理项目配置
整合所有分散的配置文件到一个 config.ini 文件中
"""

import configparser
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import math

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CONFIG_PATH = str(BASE_DIR / "config" / "net_risk.ini")


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
            'traffic_flow_path': 'data/input/12-1双月门架风险评估表_路段信息.xlsx',
            'road_risk_path': 'data/input/路段通行风险评估.xlsx',
            'event_data_path': 'data/input/25年12月-2026年1月交通事故.xlsx',
            'output_dir': 'data/output',
            'output_filename': '路网通行风险评估结果',
            'intermediate_filename': '中间计算数据',
            'save_intermediate_data': 'True'
        }

        # 风险阈值配置
        self.config['RISK_THRESHOLDS'] = {
            'reference_density': '5.12',
            'risk_compression_ratio': '0.7627',  # 270/354
            'arrival_threshold': '0.9',
            'recovery_threshold': '0.9',
            'arrival_coef_high': '0.95',
            'arrival_coef_low': '1.02',
            'recovery_coef_high': '0.95',
            'recovery_coef_low': '1.02'
        }

        # 饱和度调节系数阈值
        self.config['SATURATION_THRESHOLDS'] = {
            '1_max': '0.6',
            '1_coef': '1.00',
            '2_max': '0.8',
            '2_coef': '1.00',
            '3_max': '1.0',
            '3_coef': '1.10',
            '4_max': 'inf',
            '4_coef': '1.20'
        }

        # 均衡性调节系数阈值
        self.config['EQUILIBRIUM_THRESHOLDS'] = {
            '1_min': '0.6',
            '1_coef': '1.00',
            '2_min': '0.5',
            '2_coef': '1.00',
            '3_min': '0.4',
            '3_coef': '1.05',
            '4_min': '0.3',
            '4_coef': '1.10',
            '5_min': '0.0',
            '5_coef': '1.20'
        }

        # 风险等级阈值
        self.config['RISK_LEVELS'] = {
            '1_min': '100',
            '1_level': '高风险',
            '2_min': '80',
            '2_level': '较高风险',
            '3_min': '60',
            '3_level': '一般风险',
            '4_min': '0',
            '4_level': '低风险'
        }

        # 通用设置
        self.config['SETTINGS'] = {
            'encoding': 'utf-8',
            'log_level': 'INFO',
            'parallel_processing': 'False'
        }

        # 写入配置文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

        print(f"已创建默认配置文件: {self.config_path}")
        print("请根据实际情况修改配置文件中的设置。")

    def _load_config(self):
        """加载配置文件"""
        self.config.read(self.config_path, encoding='utf-8')

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置（从统一 output_db.ini 读取）"""
        from src.db_config import get_output_db_config
        db = get_output_db_config()
        # 数据库连接器使用 'net_table' 键名，此处做兼容映射
        db['net_table'] = db.get('net_risk_evaluation_table', 'net_risk_evaluation')
        return db

    def get_paths_config(self) -> Dict[str, str]:
        """获取文件路径配置"""
        return dict(self.config['PATHS'])

    def get_period_config(self) -> Dict[str, str]:
        """获取评估周期配置（从 output_db.ini 读取，兼容旧版 INI）"""
        from src.db_config import get_belong_date
        if self.config.has_section('PERIOD'):
            return dict(self.config['PERIOD'])
        return {'start_date': get_belong_date()}

    def get_road_base_info(self) -> Dict[str, Dict[str, Any]]:
        """获取路段基础信息"""
        road_info = {}
        valid_attrs = ['length', 'design_flow', 'company']

        if self.config.has_section('ROAD_BASE_INFO'):
            for key, value in self.config.items('ROAD_BASE_INFO'):
                if '_' in key:
                    found_attr = None
                    road_name = key
                    
                    for attr in valid_attrs:
                        if key.endswith('_' + attr):
                            road_name = key[:-len(attr)-1]
                            found_attr = attr
                            break
                    
                    if found_attr:
                        if road_name not in road_info:
                            road_info[road_name] = {}
                        
                        if found_attr == 'company':
                            road_info[road_name][found_attr] = value
                        else:
                            try:
                                road_info[road_name][found_attr] = float(value)
                            except ValueError:
                                road_info[road_name][found_attr] = 0.0

        return road_info

    def get_network_topology(self) -> Dict[str, Dict[str, float]]:
        """获取路网拓扑特征"""
        topology = {}

        if self.config.has_section('NETWORK_TOPOLOGY'):
            for key, value in self.config.items('NETWORK_TOPOLOGY'):
                if '_' in key:
                    # 处理特殊格式: 公司名_adjacent_roads -> adjacent_roads
                    if '_adjacent_' in key:
                        parts = key.split('_adjacent_')
                        if len(parts) == 2:
                            company = parts[0]
                            if company not in topology:
                                topology[company] = {}
                            topology[company]['adjacent_roads'] = float(value)
                    # 处理普通格式: 公司名_attr (attr可能是total_length, nodes, area)
                    else:
                        # 尝试匹配常见属性后缀
                        attr_suffixes = ['_total_length', '_length', '_nodes', '_area']
                        matched = False
                        for suffix in attr_suffixes:
                            if key.endswith(suffix):
                                # 去掉公司名和下划线
                                company = key[:-len(suffix)]
                                if company not in topology:
                                    topology[company] = {}
                                
                                # 映射到正确的内部键名
                                if suffix in ['_total_length', '_length']:
                                    topology[company]['total_length'] = float(value)
                                else:
                                    attr_name = suffix[1:]  # 去掉下划线
                                    topology[company][attr_name] = float(value)
                                matched = True
                                break

        filtered_topology = {}
        for k, v in topology.items():
            if v and ('nodes' in v or 'adjacent_roads' in v):
                if 'nodes' not in v:
                    v['nodes'] = 1
                if 'adjacent_roads' not in v:
                    v['adjacent_roads'] = 0
                if 'total_length' not in v:
                    v['total_length'] = 0
                if 'area' not in v:
                    v['area'] = 1
                filtered_topology[k] = v

        return filtered_topology

    def get_road_order(self) -> List[str]:
        """获取路段顺序"""
        road_order = []

        if self.config.has_section('ROAD_ORDER'):
            # 按数字键排序获取路段顺序
            keys = sorted([k for k in self.config['ROAD_ORDER'].keys() if k.isdigit()], key=int)
            for key in keys:
                road_name = self.config.get('ROAD_ORDER', key)
                road_order.append(road_name)

        return road_order

    def get_road_to_route_mapping(self) -> Dict[str, str]:
        """获取路段到路线映射"""
        mapping = {}

        if self.config.has_section('ROAD_TO_ROUTE'):
            for road_name, route_name in self.config.items('ROAD_TO_ROUTE'):
                mapping[road_name] = route_name

        return mapping

    def get_risk_thresholds(self) -> Dict[str, Any]:
        """获取风险阈值配置"""
        section = 'RISK_THRESHOLDS'
        if not self.config.has_section(section):
            return {}

        return {
            'reference_density': self.config.getfloat(section, 'reference_density', fallback=5.12),
            'risk_compression_ratio': self.config.getfloat(section, 'risk_compression_ratio', fallback=270/354),
            'arrival_threshold': self.config.getfloat(section, 'arrival_threshold', fallback=0.9),
            'recovery_threshold': self.config.getfloat(section, 'recovery_threshold', fallback=0.9),
            'arrival_coef_high': self.config.getfloat(section, 'arrival_coef_high', fallback=0.95),
            'arrival_coef_low': self.config.getfloat(section, 'arrival_coef_low', fallback=1.02),
            'recovery_coef_high': self.config.getfloat(section, 'recovery_coef_high', fallback=0.95),
            'recovery_coef_low': self.config.getfloat(section, 'recovery_coef_low', fallback=1.02)
        }

    def get_saturation_thresholds(self) -> List[Dict[str, float]]:
        """获取饱和度调节系数阈值列表"""
        thresholds = []

        if self.config.has_section('SATURATION_THRESHOLDS'):
            # 查找所有编号的阈值
            max_keys = [k for k in self.config['SATURATION_THRESHOLDS'].keys() if k.endswith('_max')]

            for max_key in sorted(max_keys, key=lambda x: int(x.split('_')[0])):
                prefix = max_key.split('_')[0]
                max_val_str = self.config.get('SATURATION_THRESHOLDS', max_key)
                coef_key = f"{prefix}_coef"

                if self.config.has_option('SATURATION_THRESHOLDS', coef_key):
                    # 处理无穷大值
                    if max_val_str.lower() == 'inf':
                        max_val = float('inf')
                    else:
                        max_val = float(max_val_str)

                    coef_val = self.config.getfloat('SATURATION_THRESHOLDS', coef_key)

                    thresholds.append({
                        'max': max_val,
                        'coef': coef_val
                    })

        return thresholds

    def get_equilibrium_thresholds(self) -> List[Dict[str, float]]:
        """获取均衡性调节系数阈值列表"""
        thresholds = []

        if self.config.has_section('EQUILIBRIUM_THRESHOLDS'):
            # 查找所有编号的阈值
            min_keys = [k for k in self.config['EQUILIBRIUM_THRESHOLDS'].keys() if k.endswith('_min')]

            for min_key in sorted(min_keys, key=lambda x: int(x.split('_')[0])):
                prefix = min_key.split('_')[0]
                min_val = self.config.getfloat('EQUILIBRIUM_THRESHOLDS', min_key)
                coef_key = f"{prefix}_coef"

                if self.config.has_option('EQUILIBRIUM_THRESHOLDS', coef_key):
                    coef_val = self.config.getfloat('EQUILIBRIUM_THRESHOLDS', coef_key)

                    thresholds.append({
                        'min': min_val,
                        'coef': coef_val
                    })

        return thresholds

    def get_risk_levels(self) -> List[Dict[str, Any]]:
        """获取风险等级阈值列表"""
        risk_levels = []

        if self.config.has_section('RISK_LEVELS'):
            # 查找所有编号的阈值
            min_keys = [k for k in self.config['RISK_LEVELS'].keys() if k.endswith('_min')]

            for min_key in sorted(min_keys, key=lambda x: int(x.split('_')[0])):
                prefix = min_key.split('_')[0]
                min_val = self.config.getfloat('RISK_LEVELS', min_key)
                level_key = f"{prefix}_level"

                if self.config.has_option('RISK_LEVELS', level_key):
                    level_val = self.config.get('RISK_LEVELS', level_key)

                    risk_levels.append({
                        'min': min_val,
                        'level': level_val
                    })

        return risk_levels

    def get_settings(self) -> Dict[str, Any]:
        """获取通用设置"""
        section = 'SETTINGS'
        if not self.config.has_section(section):
            return {}

        return {
            'encoding': self.config.get(section, 'encoding', fallback='utf-8'),
            'log_level': self.config.get(section, 'log_level', fallback='INFO'),
            'parallel_processing': self.config.getboolean(section, 'parallel_processing', fallback=False)
        }

    def get_all_config(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        return {
            'database': self.get_database_config(),
            'paths': self.get_paths_config(),
            'period': self.get_period_config(),
            'road_base_info': self.get_road_base_info(),
            'network_topology': self.get_network_topology(),
            'road_order': self.get_road_order(),
            'road_to_route': self.get_road_to_route_mapping(),
            'risk_thresholds': self.get_risk_thresholds(),
            'saturation_thresholds': self.get_saturation_thresholds(),
            'equilibrium_thresholds': self.get_equilibrium_thresholds(),
            'risk_levels': self.get_risk_levels(),
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
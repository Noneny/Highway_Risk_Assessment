"""
配置管理器 - 统一管理项目配置
整合所有分散的配置文件到一个 config.ini 文件中
"""

import configparser
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.db_config import get_belong_date

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CONFIG_PATH = str(BASE_DIR / "config" / "line_risk.ini")


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
        """创建默认配置文件（与 line_settings.yaml 保持一致）"""
        # 文件路径配置
        self.config['PATHS'] = {
            'input_dir': 'data/input',
            'output_dir': 'data/output',
            'temp_dir': 'data/temp',
            'points_file': '全结构点通行风险值评价表.xlsx',
            'template_file': '路段评价模板.xlsx',
            'gantry_file': '东南东北渝东门架信息(1).xlsx',
            'weather_file': '气象预警.xlsx',
            'accidents_file': '交通事故.xlsx',
            'etc_data_dir': 'traffic_data',
            'output_file': '路段通行风险评价总表.xlsx'
        }

        # 基础风险参数
        self.config['BASE_RISK'] = {
            'struct_score_max_theory': '132.82',
            'struct_score_target_scale': '16.0',
            'weather_score_unit': '16.0',
            'alignment_score_unit': '16.0',
            'ice_months': '12,1,2',
            'fog_months': '10,11,12,1,2,3'
        }

        # 动态风险参数
        self.config['DYNAMIC_RISK'] = {
            'min_speed': '5.0',
            'max_speed': '180.0',
            'max_time_gap': '1.0',
            'small_vehicles': '一型客车,二型客车,一型货车,一型专项作业车',
            'truck_types': '一型货车,二型货车,三型货车,四型货车,五型货车,六型货车',
            'large_ratio_high_low': '0.40',
            'large_ratio_high_high': '0.60',
            'large_ratio_medium_low': '0.30',
            'large_ratio_medium_high': '0.70',
            'large_ratio_low_low': '0.20',
            'large_ratio_low_high': '0.80',
            'congestion_high': '0.95',
            'congestion_medium': '0.85',
            'congestion_low': '0.60',
            'longitudinal_high': '20',
            'longitudinal_medium': '5',
            'weather_title_aliases': 'bt,预警信息,预警标题,title,warnContent',
            'weather_authority_aliases': 'fbdw,发布单位,dept,source',
            'weather_time_aliases': 'fbsj,发布时间,time,date',
            'exclude_keywords': '解除,防范,测试,科普,未来,防御',
            'type_keywords': '大雾,团雾,暴雨,高温,大风,积雪,道路结冰,冰雹,雷电,暴雪,霜冻,寒潮,沙尘暴,地质灾害,山洪',
            'weather_coefficient_high': '1.05',
            'weather_coefficient_medium': '1.02',
            'weather_coefficient_low': '1.00',
            'etc_chunk_size': '200000',
            'etc_excel_stream': 'False',
        }

        # 附加风险参数
        self.config['EXTRA_RISK'] = {
            'accident_scoring_ratios': '1.5,1.2,0.8,0.5',
            'accident_scoring_scores': '9,7,5,3,1',
            'special_roads': '沪渝支线长寿湖段',
            'special_road_coefficient': '1.10',
        }

        # 风险等级参数
        self.config['RISK_LEVEL'] = {
            'thresholds': '100,80,60',
            'labels': '一级,二级,三级,四级',
        }

        # 映射关系
        self.config['MAPPINGS'] = {
            'direction': '左线=上行,右线=下行,上行=上行,下行=下行,up=上行,down=下行,Up=上行,Down=下行',
            'direction_map': '左线=上行,右线=下行,上行=上行,下行=下行,up=上行,down=下行,Up=上行,Down=下行',
            'accident_direction_map': '上行=上行,下行=下行,up=上行,down=下行,Up=上行,Down=下行',
            'road_name_map': '城开路=城开路,石忠路=沪渝石忠段,奉溪路=奉溪高速,万利路=万利高速,长万路=沪蓉万梁段,云奉路=沪蓉奉云段,酉黔路=包茂黔酉段,酉沿路=酉沿高速,武彭路=包茂黄彭段,黔恩路=黔恩高速,奉巫路=沪蓉巫奉段,彭黔路=包茂彭黔段,万达路=万达高速,万开路=万开路,万云路=沪蓉云万段,丰忠路=丰忠高速,酉洪路=包茂酉洪段',
            'accident_road_map': 'G50沪渝高速石忠段=沪渝石忠段,G50沪渝高速长垫段=沪渝长垫段,G42沪蓉高速梁万段=沪蓉万梁段,G42沪蓉高速奉巫段=沪蓉巫奉段,G42沪蓉高速奉节段=沪蓉奉云段,G42沪蓉高速万云段=沪蓉云万段,G65包茂高速黄彭段=包茂黄彭段,G65包茂高速彭黔段=包茂彭黔段,G65包茂高速黔酉段=包茂黔酉段,G65包茂高速酉洪段=包茂酉洪段,S19梁开高速=梁开高速,G5515张南高速黔恩段=黔恩高速,S26酉沿高速=酉沿高速,G6911安来高速奉溪段=奉溪高速,S10巫梁高速巫云开段（巫溪枢纽至沙市互通）=巫云开高速一期,G69银百高速万开段=万开路,G69银百高速城开段=城开路,G5012万达高速万开段=万达高速,G5012万达高速开开段=万达高速,G5012恩广高速万利段=万利高速',
        }

        # 评估参数（留空，由代码自动生成）
        self.config['EVALUATION'] = {
        }

        # 静态风险参数
        self.config['STATIC_RISKS'] = {
            'ice_prone_roads': '沪渝支线长寿湖段=1,沪蓉万梁段=1,沪渝石忠段=1,包茂彭黔段=1,包茂黔酉段=1,包茂酉洪段=1,黔恩高速=1,酉沿高速=1,沪蓉巫奉段=2,城开路=1,奉溪高速=1',
            'fog_prone_roads': '沪渝支线长寿湖段=1,沪蓉万梁段=3,沪蓉梁垫段=2,沪渝石忠段=2,沪渝长垫段=1,丰忠高速=1,包茂黄彭段=1,包茂彭黔段=2,包茂黔酉段=2,包茂酉洪段=1,黔恩高速=1,酉沿高速=1,沪蓉巫奉段=3,城开路=1,奉溪高速=1,万达高速=1',
            'bad_alignment_roads': '',
        }

        # 通用设置
        self.config['SETTINGS'] = {
            'encoding': 'utf-8',
            'drop_na': 'True',
            'log_level': 'INFO',
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
        # 数据库连接器使用 'table' 键名，此处做兼容映射
        db['table'] = db.get('line_risk_evaluation_table', 'line_risk_evaluation')
        return db

    def get_paths_config(self) -> Dict[str, str]:
        """获取文件路径配置"""
        section = 'PATHS'
        if not self.config.has_section(section):
            return {}

        config = dict(self.config[section])
        # 确保路径相对于项目根目录
        base_dir = Path(self.config_path).parent.parent

        # 处理相对路径
        for key, value in config.items():
            if value and not os.path.isabs(value):
                # 对于input_dir等目录，构建相对于项目根的完整路径
                if key in ['input_dir', 'output_dir', 'temp_dir']:
                    config[key] = str(base_dir / value)
                else:
                    config[key] = value

        return config

    def get_base_risk_params(self) -> Dict[str, Any]:
        """获取基础风险参数"""
        section = 'BASE_RISK'
        if not self.config.has_section(section):
            return {}

        return {
            'struct_score_max_theory': self.config.getfloat(section, 'struct_score_max_theory', fallback=100.0),
            'struct_score_target_scale': self.config.getfloat(section, 'struct_score_target_scale', fallback=100.0),
            'weather_score_unit': self.config.getfloat(section, 'weather_score_unit', fallback=10.0),
            'alignment_score_unit': self.config.getfloat(section, 'alignment_score_unit', fallback=10.0),
            'ice_months': [int(x.strip()) for x in self.config.get(section, 'ice_months', fallback='11,12,1,2,3').split(',')],
            'fog_months': [int(x.strip()) for x in self.config.get(section, 'fog_months', fallback='9,10,11,12,1,2,3,4,5').split(',')]
        }

    def get_dynamic_risk_params(self) -> Dict[str, Any]:
        """获取动态风险参数"""
        section = 'DYNAMIC_RISK'
        if not self.config.has_section(section):
            return {}

        return {
            'truck_types': self.config.get(section, 'truck_types',
                                          fallback='一型货车,二型货车,三型货车,四型货车,五型货车,六型货车').split(','),
            'peak_hour_capacity': self.config.getint(section, 'peak_hour_capacity', fallback=3000),
            'min_speed': self.config.getfloat(section, 'min_speed', fallback=5.0),
            'max_speed': self.config.getfloat(section, 'max_speed', fallback=200.0),
            'max_time_gap': self.config.getfloat(section, 'max_time_gap', fallback=0.0833),  # 5分钟 (0.0833小时)
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
            'discrete_speed_low': self.config.getfloat(section, 'discrete_speed_low', fallback=20.0),
            'weather_warning_radius': self.config.getfloat(section, 'weather_warning_radius', fallback=5.0),
            'longitudinal_high': self.config.getfloat(section, 'longitudinal_high', fallback=20.0),
            'longitudinal_medium': self.config.getfloat(section, 'longitudinal_medium', fallback=5.0)
        }

    def get_extra_risk_params(self) -> Dict[str, Any]:
        """获取附加风险参数"""
        section = 'EXTRA_RISK'
        if not self.config.has_section(section):
            return {}

        special_roads_str = self.config.get(section, 'special_roads', fallback='')
        special_roads_list = [s.strip() for s in special_roads_str.split(',') if s.strip()] if special_roads_str else []

        return {
            'accident_per_km_threshold': self.config.getfloat(section, 'accident_per_km_threshold', fallback=1.0),
            'road_attribute_coefficient': self.config.getfloat(section, 'road_attribute_coefficient', fallback=1.1),
            'accident_scoring_ratios': self.config.get(section, 'accident_scoring_ratios', fallback='1.5,1.2,0.8,0.5'),
            'accident_scoring_scores': self.config.get(section, 'accident_scoring_scores', fallback='9,7,5,3,1'),
            'special_attributes': {
                'tourism_or_freight_roads': special_roads_list,
                'coefficient': self.config.getfloat(section, 'special_road_coefficient', fallback=1.10),
            },
        }

    def get_risk_level_params(self) -> Dict[str, Any]:
        """获取风险等级参数"""
        section = 'RISK_LEVEL'
        if not self.config.has_section(section):
            return {}

        thresholds_str = self.config.get(section, 'thresholds', fallback='100,80,60')
        thresholds = [float(x.strip()) for x in thresholds_str.split(',') if x.strip()]

        labels_str = self.config.get(section, 'labels', fallback='高风险,较高风险,一般风险,低风险')
        labels = [x.strip() for x in labels_str.split(',') if x.strip()]

        return {
            'thresholds': thresholds,
            'labels': labels,
            'coefficient_threshold': self.config.getfloat(section, 'coefficient_threshold', fallback=1.05)
        }

    def get_mappings(self) -> Dict[str, Dict[str, str]]:
        """获取映射关系"""
        section = 'MAPPINGS'
        if not self.config.has_section(section):
            return {}

        mappings = {}

        def parse_map_string(map_str: str) -> Dict[str, str]:
            """解析逗号分隔的键值对字符串"""
            result = {}
            if not map_str:
                return result
            for item in map_str.split(','):
                if '=' in item:
                    original, standardized = item.split('=', 1)
                    result[original.strip()] = standardized.strip()
            return result

        # 1. 方向映射
        direction_map_str = self.config.get(section, 'direction_map', fallback='')
        direction_map = parse_map_string(direction_map_str)

        # 2. 事故方向映射
        accident_direction_map_str = self.config.get(section, 'accident_direction_map', fallback='')
        accident_direction_map = parse_map_string(accident_direction_map_str)

        # 3. 路段名称映射
        road_name_map_str = self.config.get(section, 'road_name_map', fallback='')
        road_name_map = parse_map_string(road_name_map_str)

        # 4. 事故路段映射
        accident_road_map_str = self.config.get(section, 'accident_road_map', fallback='')
        accident_road_map = parse_map_string(accident_road_map_str)

        mappings['road_name_map'] = road_name_map
        mappings['direction_map'] = direction_map
        mappings['accident_direction_map'] = accident_direction_map
        mappings['accident_road_map'] = accident_road_map

        return mappings

    def get_evaluation_params(self) -> Dict[str, str]:
        """获取评估参数，belong_date 从 output_db.ini 读取，start_date/end_date 自动计算"""
        from calendar import monthrange
        from datetime import datetime
        belong_date = get_belong_date()
        dt = datetime.strptime(belong_date, '%Y-%m-%d')
        year, month = dt.year, dt.month
        if month == 12:
            next_year, next_month = year + 1, 1
        else:
            next_year, next_month = year, month + 1
        last_day = monthrange(next_year, next_month)[1]
        end_date = f"{next_year}-{next_month:02d}-{last_day:02d}"
        return {
            'belong_date': belong_date,
            'start_date': belong_date,
            'end_date': end_date,
        }

    def get_static_risks(self) -> Dict[str, Dict[str, int]]:
        """获取静态风险配置"""
        section = 'STATIC_RISKS'
        if not self.config.has_section(section):
            return {}

        static_risks = {}

        # 易结冰路段
        ice_str = self.config.get(section, 'ice_prone_roads', fallback='')
        ice_map = {}
        if ice_str:
            for item in ice_str.split(','):
                if '=' in item:
                    road, count = item.split('=', 1)
                    ice_map[road.strip()] = int(count.strip())
        static_risks['ice_prone_roads'] = ice_map

        # 团雾路段
        fog_str = self.config.get(section, 'fog_prone_roads', fallback='')
        fog_map = {}
        if fog_str:
            for item in fog_str.split(','):
                if '=' in item:
                    road, count = item.split('=', 1)
                    fog_map[road.strip()] = int(count.strip())
        static_risks['fog_prone_roads'] = fog_map

        # 不良线形路段
        alignment_str = self.config.get(section, 'bad_alignment_roads', fallback='')
        alignment_map = {}
        if alignment_str:
            for item in alignment_str.split(','):
                if '=' in item:
                    road, count = item.split('=', 1)
                    alignment_map[road.strip()] = int(count.strip())
        static_risks['bad_alignment_roads'] = alignment_map

        return static_risks

    def get_settings(self) -> Dict[str, Any]:
        """获取通用设置"""
        section = 'SETTINGS'
        if not self.config.has_section(section):
            return {}

        return {
            'encoding': self.config.get(section, 'encoding', fallback='utf-8'),
            'drop_na': self.config.getboolean(section, 'drop_na', fallback=True),
            'chunksize': self.config.getint(section, 'chunksize', fallback=50000),
            'use_chunks': self.config.getboolean(section, 'use_chunks', fallback=True),
            'auto_chunk_threshold_mb': self.config.getint(section, 'auto_chunk_threshold_mb', fallback=100)
        }

    def get_all_config(self) -> Dict[str, Dict[str, Any]]:
        """获取所有配置"""
        return {
            'database': self.get_database_config(),
            'paths': self.get_paths_config(),
            'base_risk': self.get_base_risk_params(),
            'dynamic_risk': self.get_dynamic_risk_params(),
            'extra_risk': self.get_extra_risk_params(),
            'risk_level': self.get_risk_level_params(),
            'mappings': self.get_mappings(),
            'evaluation': self.get_evaluation_params(),
            'static_risks': self.get_static_risks(),
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
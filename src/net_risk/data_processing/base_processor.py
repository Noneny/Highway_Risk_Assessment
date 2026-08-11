"""
基础数据处理抽象类
定义数据处理器的通用接口和功能
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pathlib import Path
import os


class BaseDataProcessor(ABC):
    """基础数据处理抽象类"""

    def __init__(self, config_manager):
        """
        初始化数据处理器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()
        self.processed_data = None

    @abstractmethod
    def load_data(self, file_path: str) -> pd.DataFrame:
        """
        加载数据

        Args:
            file_path: 文件路径

        Returns:
            DataFrame数据
        """
        pass

    @abstractmethod
    def process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        处理数据

        Args:
            data: 原始数据

        Returns:
            处理后的数据
        """
        pass

    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        验证数据

        Args:
            data: 待验证的数据

        Returns:
            验证是否通过
        """
        pass

    def save_processed_data(self, output_path: str):
        """
        保存处理后的数据

        Args:
            output_path: 输出文件路径
        """
        if self.processed_data is not None and not self.processed_data.empty:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            self.processed_data.to_excel(output_path, index=False)
            print(f"✅ 已保存处理后的数据到: {output_path}")
        else:
            print("⚠️  无数据可保存")

    def get_processed_data(self) -> Optional[pd.DataFrame]:
        """
        获取处理后的数据

        Returns:
            处理后的数据，如果未处理则为None
        """
        return self.processed_data

    def standardize_column_names(self, df: pd.DataFrame, data_type: str = 'generic') -> pd.DataFrame:
        """
        标准化列名

        Args:
            df: 原始DataFrame
            data_type: 数据类型，如'traffic_flow', 'road_risk', 'event_data'

        Returns:
            标准化后的DataFrame
        """
        df = df.copy()

        if data_type == 'traffic_flow':
            # 处理门架流量数据的列名标准化
            if '路段名称' not in df.columns:
                road_cols = [col for col in df.columns if '路段' in col or 'road' in col.lower()]
                if road_cols:
                    df['路段名称'] = df[road_cols[0]]
                    print(f"    使用 '{road_cols[0]}' 作为路段名称")

            if '日均高峰小时流量' not in df.columns:
                flow_cols = [col for col in df.columns if '流量' in col or 'flow' in col.lower()]
                if flow_cols:
                    df['日均高峰小时流量'] = df[flow_cols[0]]
                    print(f"    使用 '{flow_cols[0]}' 作为流量")

        elif data_type == 'road_risk':
            # 处理路段风险数据的列名标准化
            if '路段' in df.columns:
                df['road_name'] = df['路段'].ffill()
                print("    使用列'路段'作为路段名称")
            else:
                road_cols = [col for col in df.columns if '路段' in col or 'road' in col.lower()]
                if road_cols:
                    df['road_name'] = df[road_cols[0]].ffill()
                    print(f"    使用列'{road_cols[0]}'作为路段名称")
                else:
                    df['road_name'] = df.iloc[:, 0].ffill()
                    print("    使用第一列作为路段名称")

            if '路段风险总评' in df.columns:
                df['risk_value'] = df['路段风险总评']
                print("    使用列'路段风险总评'作为风险值")
            else:
                risk_cols = [col for col in df.columns if '风险' in col or 'risk' in col.lower()]
                if risk_cols:
                    df['risk_value'] = df[risk_cols[0]]
                    print(f"    使用列'{risk_cols[0]}'作为风险值")
                else:
                    df['risk_value'] = df.iloc[:, -1]
                    print("    使用最后一列作为风险值")

        elif data_type == 'event_data':
            # 处理事件数据的列名标准化
            # 列名统一转为大写
            df.columns = [col.upper() if isinstance(col, str) else col for col in df.columns]

        return df

    def normalize_road_name(self, event_road_name: str, road_keywords: Dict[str, List[str]]) -> Optional[str]:
        """
        标准化路段名称

        Args:
            event_road_name: 原始路段名称
            road_keywords: 路段关键词映射

        Returns:
            标准化后的路段名称，如果无法匹配则返回None
        """
        if pd.isna(event_road_name) or not isinstance(event_road_name, str):
            return None

        import re
        cleaned_name = event_road_name.strip()

        # 从配置中获取路段基础信息
        road_base_info = self.config.get('road_base_info', {})

        # 精确匹配
        if cleaned_name in road_base_info:
            return cleaned_name

        # 去除英文字母数字等干扰，提取纯中文部分
        chinese_part = re.sub(r'[A-Za-z0-9\- ]+', '', cleaned_name)

        # 关键词匹配
        for standard_road, keywords in road_keywords.items():
            if any(keyword in chinese_part for keyword in keywords):
                return standard_road

        # 核心名称包含匹配
        for standard_road in road_base_info:
            core_name = standard_road.replace('高速', '').replace('段', '').replace('一期', '')
            if core_name and core_name in chinese_part:
                return standard_road

        return None

    def get_road_keywords(self) -> Dict[str, List[str]]:
        """
        获取路段关键词映射

        Returns:
            路段关键词映射字典
        """
        # 从原代码中提取的关键词映射
        return {
            '沪渝支线长寿湖段': ['长寿湖'],
            '沪蓉万梁段': ['万梁', '梁万'],
            '沪蓉梁垫段': ['梁垫', '垫梁'],
            '沪渝石忠段': ['石忠', '忠石'],
            '沪渝长垫段': ['长垫', '垫长'],
            '丰忠高速': ['丰忠', '忠丰'],
            '梁开高速': ['梁开', '开梁'],
            '包茂黄彭段': ['黄彭', '彭黄'],
            '包茂彭黔段': ['彭黔', '黔彭'],
            '包茂黔酉段': ['黔酉', '酉黔'],
            '包茂酉洪段': ['酉洪', '洪酉'],
            '黔恩高速': ['黔恩', '恩黔'],
            '酉沿高速': ['酉沿', '沿酉'],
            '沪蓉巫奉段': ['巫奉', '奉巫'],
            '沪蓉奉云段': ['奉云', '云奉'],
            '沪蓉云万段': ['云万', '万云'],
            '万开路': ['万开', '开万'],
            '城开路': ['城开', '开城'],
            '奉溪高速': ['奉溪', '溪奉'],
            '巫云开高速一期': ['巫云开', '云开巫'],
            '万达高速': ['万达', '达万'],
            '万利高速': ['万利', '利万'],
        }

    def check_file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在

        Args:
            file_path: 文件路径

        Returns:
            文件是否存在
        """
        exists = os.path.exists(file_path)
        if not exists:
            print(f"⚠️  文件不存在: {file_path}")
        return exists
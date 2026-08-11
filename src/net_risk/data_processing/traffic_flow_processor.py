"""
门架流量数据处理器
处理门架流量数据的加载、处理和标准化
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from .base_processor import BaseDataProcessor
import os


class TrafficFlowProcessor(BaseDataProcessor):
    """门架流量数据处理器"""

    def __init__(self, config_manager):
        """
        初始化流量数据处理器

        Args:
            config_manager: 配置管理器实例
        """
        super().__init__(config_manager)
        self.config = config_manager.get_all_config()
        self.processed_data = None

    def load_data(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        加载门架流量数据

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            原始数据DataFrame
        """
        if file_path is None:
            file_path = self.config['paths'].get('traffic_flow_path')

        if not self.check_file_exists(file_path):
            print(f"❌ 错误: 门架流量文件不存在: {file_path}")
            return pd.DataFrame(columns=['路段名称', '日均高峰小时流量'])

        try:
            raw_data = pd.read_excel(file_path)
            print(f"✅ 读取到 {len(raw_data)} 条门架记录")
            return raw_data
        except Exception as e:
            print(f"❌ 读取门架流量数据失败: {e}")
            return pd.DataFrame(columns=['路段名称', '日均高峰小时流量'])

    def process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        处理门架流量数据

        Args:
            data: 原始门架流量数据

        Returns:
            处理后的流量数据
        """
        print("  >> 正在处理门架流量数据...")

        if data.empty:
            print("    ⚠️ 警告：门架流量数据为空")
            self.processed_data = pd.DataFrame(columns=['road_name', 'peak_hour_flow'])
            return self.processed_data

        # 标准化列名
        raw_data = self.standardize_column_names(data, 'traffic_flow')

        # 剔除路段名称为空的行
        raw_data = raw_data.dropna(subset=['路段名称'])
        print(f"    剔除空路段名称后剩余 {len(raw_data)} 条记录")

        # 标准化路段名称
        road_keywords = self.get_road_keywords()
        raw_data['standard_road_name'] = raw_data['路段名称'].apply(
            lambda x: self.normalize_road_name(x, road_keywords)
        )
        matched = raw_data['standard_road_name'].notna().sum()
        print(f"    路段名称标准化成功：{matched} / {len(raw_data)} 条匹配")

        raw_data = raw_data[raw_data['standard_road_name'].notna()]
        if len(raw_data) == 0:
            print("    ⚠️ 警告：无有效门架数据，流量表为空")
            self.processed_data = pd.DataFrame(columns=['road_name', 'peak_hour_flow'])
            return self.processed_data

        # 按标准化路段名称分组，取流量均值
        traffic_flow_data = raw_data.groupby('standard_road_name')['日均高峰小时流量'].mean().reset_index()
        traffic_flow_data.columns = ['road_name', 'peak_hour_flow']
        self.processed_data = traffic_flow_data

        print(f"    ✅ 完成路段流量计算：共 {len(self.processed_data)} 个路段")
        return self.processed_data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        验证流量数据

        Args:
            data: 待验证的数据

        Returns:
            验证是否通过
        """
        if data.empty:
            print("⚠️  验证失败：流量数据为空")
            return False

        # 检查必需列
        required_cols = ['road_name', 'peak_hour_flow']
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            print(f"❌ 验证失败：缺少必需列 {missing_cols}")
            return False

        # 检查数据有效性
        invalid_flows = data[data['peak_hour_flow'] <= 0].shape[0]
        if invalid_flows > 0:
            print(f"⚠️  警告：有 {invalid_flows} 条记录的流量值小于等于0")

        # 检查路段名称唯一性
        duplicates = data['road_name'].duplicated().sum()
        if duplicates > 0:
            print(f"⚠️  警告：有 {duplicates} 个重复的路段名称")

        print(f"✅ 流量数据验证通过：{len(data)} 条记录")
        return True

    def get_traffic_flow_dict(self) -> Dict[str, float]:
        """
        获取路段流量字典

        Returns:
            路段名称到流量值的映射字典
        """
        if self.processed_data is None or self.processed_data.empty:
            return {}

        return dict(zip(self.processed_data['road_name'], self.processed_data['peak_hour_flow']))

    def get_road_names(self) -> list:
        """
        获取已处理的路段名称列表

        Returns:
            路段名称列表
        """
        if self.processed_data is None or self.processed_data.empty:
            return []

        return self.processed_data['road_name'].tolist()

    def get_total_flow(self) -> float:
        """
        获取总流量

        Returns:
            总流量值
        """
        if self.processed_data is None or self.processed_data.empty:
            return 0.0

        return self.processed_data['peak_hour_flow'].sum()

    def run_full_process(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        执行完整的流量数据处理流程

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            处理后的流量数据
        """
        print(">> 开始处理门架流量数据")

        # 加载数据
        raw_data = self.load_data(file_path)

        # 处理数据
        processed_data = self.process_data(raw_data)

        # 验证数据
        if not self.validate_data(processed_data):
            print("⚠️  流量数据处理验证失败，但将继续流程")

        return processed_data
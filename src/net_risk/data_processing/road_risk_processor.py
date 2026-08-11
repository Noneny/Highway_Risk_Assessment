"""
路段风险数据处理器
处理路段风险数据的加载、处理和标准化
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from .base_processor import BaseDataProcessor
import os


class RoadRiskProcessor(BaseDataProcessor):
    """路段风险数据处理器"""

    def __init__(self, config_manager):
        """
        初始化路段风险数据处理器

        Args:
            config_manager: 配置管理器实例
        """
        super().__init__(config_manager)
        self.config = config_manager.get_all_config()
        self.processed_data = None
        self.risk_compression_ratio = self.config['risk_thresholds'].get('risk_compression_ratio', 270 / 354)

    def load_data(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        加载路段风险数据

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            原始数据DataFrame
        """
        if file_path is None:
            file_path = self.config['paths'].get('road_risk_path')

        if not self.check_file_exists(file_path):
            print(f"❌ 错误: 路段风险文件不存在: {file_path}")
            return pd.DataFrame(columns=['road_name', 'risk_value'])

        try:
            raw_data = pd.read_excel(file_path)
            print(f"✅ 读取到 {len(raw_data)} 条路段风险记录")
            return raw_data
        except Exception as e:
            print(f"❌ 读取路段风险数据失败: {e}")
            return pd.DataFrame(columns=['road_name', 'risk_value'])

    def process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        处理路段风险数据

        Args:
            data: 原始路段风险数据

        Returns:
            处理后的风险数据
        """
        print("  >> 正在处理路段风险数据...")

        if data.empty:
            print("    ⚠️ 警告：路段风险数据为空")
            self.processed_data = pd.DataFrame(columns=['road_name', 'risk_value'])
            self.road_order = []
            return self.processed_data

        # 标准化列名
        raw_data = self.standardize_column_names(data, 'road_risk')

        # 标准化路段名称
        road_keywords = self.get_road_keywords()
        raw_data['standard_road_name'] = raw_data['road_name'].apply(
            lambda x: self.normalize_road_name(x, road_keywords)
        )
        matched = raw_data['standard_road_name'].notna().sum()
        print(f"    路段名称标准化成功：{matched} / {len(raw_data)} 条匹配")

        raw_data = raw_data[raw_data['standard_road_name'].notna()]
        if len(raw_data) == 0:
            print("    ⚠️ 警告：无有效路段风险数据")
            self.processed_data = pd.DataFrame(columns=['road_name', 'risk_value'])
            self.road_order = []
            return self.processed_data

        # 提取路段顺序（按首次出现去重，保留输入文件中的原始排序）
        self.road_order = raw_data['standard_road_name'].unique().tolist()
        print(f"    路段排序提取完成：共 {len(self.road_order)} 个路段")

        # 取每个路段的最大风险值并压缩
        max_risk_by_road = {}
        for road_name in raw_data['standard_road_name'].unique():
            risk_values = raw_data[raw_data['standard_road_name'] == road_name]['risk_value'].tolist()
            if risk_values:
                max_risk = max(risk_values)
                compressed_risk = max_risk * self.risk_compression_ratio
                max_risk_by_road[road_name] = compressed_risk
            else:
                max_risk_by_road[road_name] = 0.0

        self.processed_data = pd.DataFrame({
            'road_name': list(max_risk_by_road.keys()),
            'risk_value': list(max_risk_by_road.values())
        })

        print(f"    ✅ 完成路段风险提取：共 {len(self.processed_data)} 个路段")
        print(f"    风险压缩比例: {self.risk_compression_ratio:.4f}")
        return self.processed_data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        验证路段风险数据

        Args:
            data: 待验证的数据

        Returns:
            验证是否通过
        """
        if data.empty:
            print("⚠️  验证失败：路段风险数据为空")
            return False

        # 检查必需列
        required_cols = ['road_name', 'risk_value']
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            print(f"❌ 验证失败：缺少必需列 {missing_cols}")
            return False

        # 检查风险值范围
        risk_values = data['risk_value']
        if risk_values.min() < 0:
            print(f"⚠️  警告：有 {len(data[risk_values < 0])} 条记录的风险值小于0")

        # 检查路段名称唯一性
        duplicates = data['road_name'].duplicated().sum()
        if duplicates > 0:
            print(f"⚠️  警告：有 {duplicates} 个重复的路段名称")

        print(f"✅ 路段风险数据验证通过：{len(data)} 条记录")
        print(f"    风险值范围: {risk_values.min():.2f} - {risk_values.max():.2f}")
        return True

    def get_road_risk_dict(self) -> Dict[str, float]:
        """
        获取路段风险字典

        Returns:
            路段名称到风险值的映射字典
        """
        if self.processed_data is None or self.processed_data.empty:
            return {}

        return dict(zip(self.processed_data['road_name'], self.processed_data['risk_value']))

    def get_road_order(self) -> list:
        """
        获取路段排序（按输入文件中首次出现的顺序）

        Returns:
            路段名称列表，按输入文件中的原始排序
        """
        return getattr(self, 'road_order', [])

    def get_average_risk(self) -> float:
        """
        获取平均风险值

        Returns:
            平均风险值
        """
        if self.processed_data is None or self.processed_data.empty:
            return 0.0

        return self.processed_data['risk_value'].mean()

    def get_max_risk(self) -> float:
        """
        获取最大风险值

        Returns:
            最大风险值
        """
        if self.processed_data is None or self.processed_data.empty:
            return 0.0

        return self.processed_data['risk_value'].max()

    def get_high_risk_roads(self, threshold: float = 80.0) -> pd.DataFrame:
        """
        获取高风险路段

        Args:
            threshold: 高风险阈值

        Returns:
            高风险路段DataFrame
        """
        if self.processed_data is None or self.processed_data.empty:
            return pd.DataFrame()

        high_risk = self.processed_data[self.processed_data['risk_value'] >= threshold]
        return high_risk

    def run_full_process(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        执行完整的路段风险数据处理流程

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            处理后的路段风险数据
        """
        print(">> 开始处理路段风险数据")

        # 加载数据
        raw_data = self.load_data(file_path)

        # 处理数据
        processed_data = self.process_data(raw_data)

        # 验证数据
        if not self.validate_data(processed_data):
            print("⚠️  路段风险数据处理验证失败，但将继续流程")

        return processed_data
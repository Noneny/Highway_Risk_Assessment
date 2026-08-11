"""
交通事故事件数据处理器
处理交通事故数据的加载、处理和标准化
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from .base_processor import BaseDataProcessor
import os
from datetime import datetime


class EventDataProcessor(BaseDataProcessor):
    """交通事故事件数据处理器"""

    def __init__(self, config_manager):
        """
        初始化事件数据处理器

        Args:
            config_manager: 配置管理器实例
        """
        super().__init__(config_manager)
        self.config = config_manager.get_all_config()
        self.processed_data = None

    def load_data(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        加载交通事故事件数据

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            原始数据DataFrame
        """
        if file_path is None:
            file_path = self.config['paths'].get('event_data_path')

        if not self.check_file_exists(file_path):
            print(f"❌ 错误: 事件数据文件不存在: {file_path}")
            return pd.DataFrame()

        try:
            event_data = pd.read_excel(file_path, sheet_name=0)
            print(f"✅ 读取到 {len(event_data)} 条事件记录")
            return event_data
        except Exception as e:
            print(f"❌ 读取事件数据失败: {e}")
            return pd.DataFrame()

    def process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        处理交通事故事件数据

        Args:
            data: 原始事件数据

        Returns:
            处理后的事件数据
        """
        print("  >> 正在处理交通事故事件数据...")

        if data.empty:
            print("    ⚠️ 事件数据为空")
            self.processed_data = pd.DataFrame()
            return self.processed_data

        # 标准化列名
        raw_data = self.standardize_column_names(data, 'event_data')

        # 检查必需列
        required_cols = ['ROAD_NAME', 'HAPPEN_TIME', 'RELEASE_TIME']
        if not all(col in raw_data.columns for col in required_cols):
            print(f"    ❌ 缺少必需列: {required_cols}")
            missing = [col for col in required_cols if col not in raw_data.columns]
            print(f"    缺少的列: {missing}")
            self.processed_data = pd.DataFrame()
            return self.processed_data

        # 剔除空值
        raw_data = raw_data.dropna(subset=required_cols)
        print(f"    剔除空值后剩余 {len(raw_data)} 条事件")

        # 标准化路段名称
        road_keywords = self.get_road_keywords()
        raw_data['NORMALIZED_ROAD_NAME'] = raw_data['ROAD_NAME'].apply(
            lambda x: self.normalize_road_name(x, road_keywords)
        )
        matched = raw_data['NORMALIZED_ROAD_NAME'].notna().sum()
        print(f"    路段名称标准化匹配：{matched} / {len(raw_data)} 条")
        raw_data = raw_data[raw_data['NORMALIZED_ROAD_NAME'].notna()]

        if len(raw_data) == 0:
            print("    ⚠️ 无有效事件数据")
            self.processed_data = pd.DataFrame()
            return self.processed_data

        # 时间格式转换
        raw_data['HAPPEN_TIME'] = pd.to_datetime(raw_data['HAPPEN_TIME'], errors='coerce')
        raw_data['RELEASE_TIME'] = pd.to_datetime(raw_data['RELEASE_TIME'], errors='coerce')

        # 剔除无效时间
        raw_data = raw_data.dropna(subset=['HAPPEN_TIME', 'RELEASE_TIME'])
        print(f"    有效时间转换后剩余 {len(raw_data)} 条事件")

        # 计算处理时长（分钟）
        raw_data['HANDLING_TIME_MINUTES'] = (
            (raw_data['RELEASE_TIME'] - raw_data['HAPPEN_TIME']).dt.total_seconds() / 60
        )

        # 过滤不合理的处理时长（例如负数或过长的时间）
        raw_data = raw_data[raw_data['HANDLING_TIME_MINUTES'] > 0]
        raw_data = raw_data[raw_data['HANDLING_TIME_MINUTES'] <= 1440]  # 最多24小时

        print(f"    处理时长计算完成，平均时长: {raw_data['HANDLING_TIME_MINUTES'].mean():.2f} 分钟")
        print(f"    最终有效事件数: {len(raw_data)} 条")

        self.processed_data = raw_data
        return self.processed_data

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        验证事件数据

        Args:
            data: 待验证的数据

        Returns:
            验证是否通过
        """
        if data.empty:
            print("⚠️  验证失败：事件数据为空")
            return False

        # 检查必需列
        required_cols = ['NORMALIZED_ROAD_NAME', 'HAPPEN_TIME', 'RELEASE_TIME', 'HANDLING_TIME_MINUTES']
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            print(f"❌ 验证失败：缺少必需列 {missing_cols}")
            return False

        # 检查时间合理性
        invalid_times = data[data['HAPPEN_TIME'] > data['RELEASE_TIME']].shape[0]
        if invalid_times > 0:
            print(f"⚠️  警告：有 {invalid_times} 条记录的发生时间晚于恢复时间")

        # 检查处理时长范围
        handling_times = data['HANDLING_TIME_MINUTES']
        min_time = handling_times.min()
        max_time = handling_times.max()
        avg_time = handling_times.mean()

        print(f"✅ 事件数据验证通过：{len(data)} 条记录")
        print(f"    处理时长范围: {min_time:.1f} - {max_time:.1f} 分钟，平均: {avg_time:.1f} 分钟")
        return True

    def get_events_by_company(self, company: str) -> pd.DataFrame:
        """
        获取指定公司的事件数据

        Args:
            company: 公司名称

        Returns:
            该公司的事件数据
        """
        if self.processed_data is None or self.processed_data.empty:
            return pd.DataFrame()

        # 获取属于该公司的路段
        road_base_info = self.config.get('road_base_info', {})
        company_roads = [
            road for road, info in road_base_info.items()
            if info.get('company') == company
        ]

        # 筛选事件
        company_events = self.processed_data[
            self.processed_data['NORMALIZED_ROAD_NAME'].isin(company_roads)
        ]

        return company_events

    def get_events_by_road(self, road_name: str) -> pd.DataFrame:
        """
        获取指定路段的事件数据

        Args:
            road_name: 路段名称

        Returns:
            该路段的事件数据
        """
        if self.processed_data is None or self.processed_data.empty:
            return pd.DataFrame()

        road_events = self.processed_data[
            self.processed_data['NORMALIZED_ROAD_NAME'] == road_name
        ]

        return road_events

    def calculate_arrival_rate(self, company: str, threshold_minutes: float = 30.0) -> float:
        """
        计算30分钟到达率

        Args:
            company: 公司名称
            threshold_minutes: 到达时间阈值（分钟）

        Returns:
            到达率（0-1之间）
        """
        company_events = self.get_events_by_company(company)

        if company_events.empty:
            return 0.0

        # 统计在阈值时间内到达的事件数
        arrival_count = company_events[company_events['HANDLING_TIME_MINUTES'] <= threshold_minutes].shape[0]
        total_count = len(company_events)

        return arrival_count / total_count if total_count > 0 else 0.0

    def calculate_recovery_rate(self, company: str, threshold_minutes: float = 60.0) -> float:
        """
        计算1小时恢复通行率

        Args:
            company: 公司名称
            threshold_minutes: 恢复时间阈值（分钟）

        Returns:
            恢复率（0-1之间）
        """
        company_events = self.get_events_by_company(company)

        if company_events.empty:
            return 0.0

        # 统计在阈值时间内恢复的事件数
        recovery_count = company_events[company_events['HANDLING_TIME_MINUTES'] <= threshold_minutes].shape[0]
        total_count = len(company_events)

        return recovery_count / total_count if total_count > 0 else 0.0

    def get_event_statistics(self) -> Dict[str, Any]:
        """
        获取事件数据统计信息

        Returns:
            统计信息字典
        """
        if self.processed_data is None or self.processed_data.empty:
            return {
                'total_events': 0,
                'avg_handling_time': 0.0,
                'min_handling_time': 0.0,
                'max_handling_time': 0.0,
                'arrival_rate_30min': 0.0,
                'recovery_rate_60min': 0.0,
                'events_by_company': {}
            }

        stats = {
            'total_events': len(self.processed_data),
            'avg_handling_time': self.processed_data['HANDLING_TIME_MINUTES'].mean(),
            'min_handling_time': self.processed_data['HANDLING_TIME_MINUTES'].min(),
            'max_handling_time': self.processed_data['HANDLING_TIME_MINUTES'].max()
        }

        # 按公司统计
        road_base_info = self.config.get('road_base_info', {})
        companies = ['渝东公司', '东南公司', '东北公司']

        events_by_company = {}
        for company in companies:
            company_events = self.get_events_by_company(company)
            events_by_company[company] = {
                'count': len(company_events),
                'arrival_rate_30min': self.calculate_arrival_rate(company, 30.0),
                'recovery_rate_60min': self.calculate_recovery_rate(company, 60.0)
            }

        stats['events_by_company'] = events_by_company

        # 示范路网（所有事件）
        demo_events = self.processed_data
        stats['arrival_rate_30min'] = self.calculate_arrival_rate_for_network('示范路网', 30.0)
        stats['recovery_rate_60min'] = self.calculate_recovery_rate_for_network('示范路网', 60.0)

        return stats

    def calculate_arrival_rate_for_network(self, network: str, threshold_minutes: float = 30.0) -> float:
        """
        计算路网的30分钟到达率

        Args:
            network: 路网名称（示范路网或公司名称）
            threshold_minutes: 到达时间阈值（分钟）

        Returns:
            到达率（0-1之间）
        """
        if self.processed_data is None or self.processed_data.empty:
            return 0.0

        if network == '示范路网':
            # 示范路网包含所有事件
            events = self.processed_data
        else:
            events = self.get_events_by_company(network)

        if events.empty:
            return 0.0

        arrival_count = events[events['HANDLING_TIME_MINUTES'] <= threshold_minutes].shape[0]
        total_count = len(events)

        return arrival_count / total_count if total_count > 0 else 0.0

    def calculate_recovery_rate_for_network(self, network: str, threshold_minutes: float = 60.0) -> float:
        """
        计算路网的1小时恢复通行率

        Args:
            network: 路网名称（示范路网或公司名称）
            threshold_minutes: 恢复时间阈值（分钟）

        Returns:
            恢复率（0-1之间）
        """
        if self.processed_data is None or self.processed_data.empty:
            return 0.0

        if network == '示范路网':
            # 示范路网包含所有事件
            events = self.processed_data
        else:
            events = self.get_events_by_company(network)

        if events.empty:
            return 0.0

        recovery_count = events[events['HANDLING_TIME_MINUTES'] <= threshold_minutes].shape[0]
        total_count = len(events)

        return recovery_count / total_count if total_count > 0 else 0.0

    def run_full_process(self, file_path: Optional[str] = None) -> pd.DataFrame:
        """
        执行完整的事件数据处理流程

        Args:
            file_path: 文件路径，如果为None则从配置中读取

        Returns:
            处理后的事件数据
        """
        print(">> 开始处理交通事故事件数据")

        # 加载数据
        raw_data = self.load_data(file_path)

        # 处理数据
        processed_data = self.process_data(raw_data)

        # 验证数据
        if not self.validate_data(processed_data):
            print("⚠️  事件数据处理验证失败，但将继续流程")

        return processed_data
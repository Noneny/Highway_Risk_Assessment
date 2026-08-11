"""
数据合并器
合并流量、风险和基础信息数据，为风险评估准备完整的数据集
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from .base_processor import BaseDataProcessor


class DataMerger:
    """数据合并器"""

    def __init__(self, config_manager, traffic_flow_data: pd.DataFrame,
                 road_risk_data: pd.DataFrame, event_data: pd.DataFrame):
        """
        初始化数据合并器

        Args:
            config_manager: 配置管理器实例
            traffic_flow_data: 门架流量数据
            road_risk_data: 路段风险数据
            event_data: 事件数据
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        self.traffic_flow_data = traffic_flow_data
        self.road_risk_data = road_risk_data
        self.event_data = event_data

        self.merged_data = None
        self.road_base_info = self.config.get('road_base_info', {})
        self.road_to_route = self.config.get('road_to_route', {})

    def merge_all_data(self) -> pd.DataFrame:
        """
        合并所有数据

        Returns:
            合并后的完整数据
        """
        print("\n>> 正在合并所有数据...")

        # 1. 合并流量和风险数据
        merged = self._merge_flow_and_risk()

        if merged.empty:
            print("❌ 错误：流量和风险数据合并后为空，无法继续")
            self.merged_data = pd.DataFrame()
            return self.merged_data

        # 2. 添加基础信息
        merged = self._add_basic_info(merged)

        # 3. 添加路线名称
        merged = self._add_route_info(merged)

        # 4. 计算饱和度
        merged = self._calculate_saturation(merged)

        # 5. 按公司分组
        merged = self._group_by_company(merged)

        # 6. 计算权重
        merged = self._calculate_weights(merged)

        print(f"✅ 数据合并完成：共 {len(merged)} 个路段")
        self.merged_data = merged
        return self.merged_data

    def _merge_flow_and_risk(self) -> pd.DataFrame:
        """
        合并流量和风险数据（外连接保留所有路段）

        Returns:
            合并后的数据
        """
        if self.traffic_flow_data.empty and self.road_risk_data.empty:
            print("⚠️  警告：流量数据和风险数据均为空，返回空DataFrame")
            return pd.DataFrame()

        # 按road_name外连接合并，确保不丢失任何路段
        if self.traffic_flow_data.empty:
            merged = self.road_risk_data.copy()
            merged['peak_hour_flow'] = 0.0
        elif self.road_risk_data.empty:
            merged = self.traffic_flow_data.copy()
            merged['risk_value'] = 0.0
        else:
            merged = pd.merge(self.traffic_flow_data, self.road_risk_data, on='road_name', how='outer')

        # 填充缺失值
        if 'peak_hour_flow' in merged.columns:
            merged['peak_hour_flow'] = merged['peak_hour_flow'].fillna(0.0)
        if 'risk_value' in merged.columns:
            merged['risk_value'] = merged['risk_value'].fillna(0.0)

        # 统计匹配情况
        flow_ok = (merged['peak_hour_flow'] > 0).sum()
        risk_ok = (merged['risk_value'] > 0).sum()
        missing_flow = merged[merged['peak_hour_flow'] == 0]['road_name'].tolist()
        missing_risk = merged[merged['risk_value'] == 0]['road_name'].tolist()
        if missing_flow:
            print(f"    ⚠️  缺少交通流数据的路段({len(missing_flow)}个): {', '.join(missing_flow)}")
        if missing_risk:
            print(f"    ⚠️  缺少风险数据的路段({len(missing_risk)}个): {', '.join(missing_risk)}")

        print(f"    流量和风险数据合并：{len(merged)} 个路段")
        return merged

    def _add_basic_info(self, merged: pd.DataFrame) -> pd.DataFrame:
        """
        添加基础信息

        Args:
            merged: 合并后的数据

        Returns:
            添加基础信息后的数据
        """
        merged = merged.copy()

        # 添加路段长度、设计流量、所属公司
        for attr in ['length', 'design_flow', 'company']:
            merged[attr] = merged['road_name'].map(
                lambda x: self.road_base_info.get(x, {}).get(attr, 0.0 if attr != 'company' else '')
            )

        # 检查是否有缺失的基础信息
        missing_info = merged[merged['company'] == ''].shape[0]
        if missing_info > 0:
            print(f"    ⚠️ 警告：{missing_info} 个路段缺少基础信息（长度、设计流量、公司）")

        return merged

    def _add_route_info(self, merged: pd.DataFrame) -> pd.DataFrame:
        """
        添加路线名称信息

        Args:
            merged: 合并后的数据

        Returns:
            添加路线信息后的数据
        """
        merged = merged.copy()

        # 添加路线名称
        merged['route_name'] = merged['road_name'].map(self.road_to_route)

        # 检查是否有缺失的路线信息
        missing_route = merged[merged['route_name'].isna()].shape[0]
        if missing_route > 0:
            print(f"    ⚠️ 警告：{missing_route} 个路段缺少路线名称信息")

        return merged

    def _calculate_saturation(self, merged: pd.DataFrame) -> pd.DataFrame:
        """
        计算饱和度

        Args:
            merged: 合并后的数据

        Returns:
            添加饱和度后的数据
        """
        merged = merged.copy()

        # 避免除零错误
        merged['design_flow'] = merged['design_flow'].replace(0, 1.0)

        # 计算饱和度 = 实际流量 / 设计流量
        merged['saturation'] = merged['peak_hour_flow'] / merged['design_flow']

        # 处理异常值
        merged['saturation'] = merged['saturation'].clip(0, 10)  # 限制在0-10之间

        # 统计饱和度分布
        saturation_stats = merged['saturation'].describe()
        print(f"    饱和度统计：平均={saturation_stats['mean']:.3f}, 最大={saturation_stats['max']:.3f}")

        return merged

    def _group_by_company(self, merged: pd.DataFrame) -> pd.DataFrame:
        """
        按公司分组

        Args:
            merged: 合并后的数据

        Returns:
            分组后的数据
        """
        # 确保公司字段不为空
        merged = merged.copy()
        merged = merged[merged['company'] != '']

        # 按公司统计
        company_stats = merged.groupby('company').agg({
            'road_name': 'count',
            'peak_hour_flow': 'sum',
            'length': 'sum'
        }).rename(columns={
            'road_name': 'road_count',
            'peak_hour_flow': 'total_flow',
            'length': 'total_length'
        })

        print("\n    按公司统计：")
        for company, stats in company_stats.iterrows():
            print(f"      {company}: {int(stats['road_count'])} 个路段，总流量 {stats['total_flow']:.0f}，总长度 {stats['total_length']:.2f}km")

        return merged

    def _calculate_weights(self, merged: pd.DataFrame) -> pd.DataFrame:
        """
        计算权重系数

        Args:
            merged: 合并后的数据

        Returns:
            添加权重后的数据
        """
        merged = merged.copy()

        # 按公司计算总流量，避免除零
        total_flow_by_company = merged.groupby('company')['peak_hour_flow'].transform('sum').replace(0, 1.0)

        # 计算权重 = 路段流量 / 公司总流量
        merged['weight'] = merged['peak_hour_flow'] / total_flow_by_company

        # 处理权重异常
        merged['weight'] = merged['weight'].fillna(0)

        # 归一化权重（确保每个公司内的权重和为1）
        weight_sum_by_company = merged.groupby('company')['weight'].transform('sum').replace(0, 1.0)
        merged['weight'] = merged['weight'] / weight_sum_by_company

        # 检查权重
        weight_stats = merged.groupby('company')['weight'].agg(['sum', 'mean', 'std'])
        print("\n    权重统计：")
        for company, stats in weight_stats.iterrows():
            print(f"      {company}: 权重和={stats['sum']:.3f}, 平均权重={stats['mean']:.3f}")

        return merged

    def get_merged_data(self) -> pd.DataFrame:
        """
        获取合并后的数据

        Returns:
            合并后的数据
        """
        return self.merged_data

    def get_data_by_company(self, company: str) -> pd.DataFrame:
        """
        获取指定公司的数据

        Args:
            company: 公司名称

        Returns:
            该公司的数据
        """
        if self.merged_data is None or self.merged_data.empty:
            return pd.DataFrame()

        if company == '示范路网':
            # 示范路网包含所有公司的数据
            return self.merged_data
        else:
            return self.merged_data[self.merged_data['company'] == company]

    def get_company_list(self) -> List[str]:
        """
        获取公司列表

        Returns:
            公司名称列表
        """
        if self.merged_data is None or self.merged_data.empty:
            return []

        companies = self.merged_data['company'].unique().tolist()
        return companies

    def get_network_data(self, network: str) -> pd.DataFrame:
        """
        获取路网数据

        Args:
            network: 路网名称（'渝东公司', '东南公司', '东北公司', '示范路网'）

        Returns:
            路网数据
        """
        if self.merged_data is None or self.merged_data.empty:
            return pd.DataFrame()

        if network == '示范路网':
            return self.merged_data
        else:
            return self.merged_data[self.merged_data['company'] == network]

    def get_saturation_stats(self) -> Dict[str, Dict[str, float]]:
        """
        获取饱和度统计信息

        Returns:
            饱和度统计字典
        """
        if self.merged_data is None or self.merged_data.empty:
            return {}

        companies = ['渝东公司', '东南公司', '东北公司']
        stats = {}

        for company in companies:
            company_data = self.get_data_by_company(company)
            if not company_data.empty:
                # 计算加权平均饱和度
                numerator = (company_data['peak_hour_flow'] * company_data['length']).sum()
                denominator = (company_data['design_flow'] * company_data['length']).sum()
                avg_saturation = numerator / denominator if denominator > 0 else 0.0

                # 计算均衡性系数
                saturations = company_data['saturation'].values
                if len(saturations) > 0:
                    X_bar = np.mean(saturations)
                    if X_bar > 0:
                        sigma = np.std(saturations, ddof=0)
                        E = 1 - (sigma / X_bar)
                        E = max(0, min(1, E))
                    else:
                        E = 0
                else:
                    E = 0

                stats[company] = {
                    'avg_saturation': avg_saturation,
                    'equilibrium_coefficient': E,
                    'road_count': len(company_data),
                    'total_flow': company_data['peak_hour_flow'].sum(),
                    'total_length': company_data['length'].sum()
                }

        return stats

    def validate_merged_data(self) -> bool:
        """
        验证合并后的数据

        Returns:
            验证是否通过
        """
        if self.merged_data is None or self.merged_data.empty:
            print("❌ 验证失败：合并数据为空")
            return False

        # 检查必需列
        required_cols = ['road_name', 'peak_hour_flow', 'risk_value', 'length',
                        'design_flow', 'company', 'saturation', 'weight']
        missing_cols = [col for col in required_cols if col not in self.merged_data.columns]

        if missing_cols:
            print(f"❌ 验证失败：缺少必需列 {missing_cols}")
            return False

        # 检查数据有效性
        invalid_saturation = self.merged_data[self.merged_data['saturation'] < 0].shape[0]
        if invalid_saturation > 0:
            print(f"⚠️  警告：有 {invalid_saturation} 条记录的饱和度小于0")

        # 检查权重和
        weight_sums = self.merged_data.groupby('company')['weight'].sum()
        for company, weight_sum in weight_sums.items():
            if abs(weight_sum - 1.0) > 0.01:  # 允许1%的误差
                print(f"⚠️  警告：{company} 的权重和不为1 ({weight_sum:.3f})")

        print(f"✅ 合并数据验证通过：{len(self.merged_data)} 条记录，{len(self.merged_data['company'].unique())} 个公司")
        return True
"""
基础风险计算器
计算路网的基础风险（路段风险、路网密度、连通度）
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
from ..models.data_models import BasicRiskComponents, NetworkTopology


class BasicRiskCalculator:
    """基础风险计算器"""

    def __init__(self, config_manager):
        """
        初始化基础风险计算器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        # 获取配置参数
        self.network_topology = self.config.get('network_topology', {})
        self.reference_density = self.config['risk_thresholds'].get('reference_density', 5.12)

        # 初始化结果存储
        self.basic_risk_results = {}
        self.risk_components = {}
        self.merged_data = None

    def calculate_basic_risk(self, merged_data: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, BasicRiskComponents]]:
        """
        计算基础风险

        Args:
            merged_data: 合并后的数据

        Returns:
            Tuple[基础风险字典, 风险组件字典]
        """
        print("\n========== 计算基础风险 ==========")

        self.merged_data = merged_data

        if merged_data is None or merged_data.empty:
            print("❌ 错误：合并数据为空，无法计算基础风险")
            return {}, {}

        # 检查必需列
        required_cols = ['road_name', 'risk_value', 'peak_hour_flow', 'company', 'weight']
        missing_cols = [col for col in required_cols if col not in merged_data.columns]
        if missing_cols:
            print(f"❌ 错误：合并数据缺少必需列 {missing_cols}")
            return {}, {}

        basic_risk = {}
        risk_components = {}

        # 计算各公司的风险
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        for company in companies:
            print(f"\n   ----- 路网: {company} -----")

            if company == '示范路网':
                company_data = merged_data[merged_data['company'].isin(['渝东公司', '东南公司', '东北公司'])].copy()
            else:
                company_data = merged_data[merged_data['company'] == company].copy()

            # 计算基础风险的三个组成部分
            R, C, B = self._calculate_risk_components(company, company_data)

            # 按值大小分配F1,F2,F3
            basic_risk_value, components = self._calculate_basic_risk_value(R, C, B, company)

            basic_risk[company] = basic_risk_value
            risk_components[company] = components

            print(f"     路段风险加权平均 R = {R:.4f}")
            print(f"     连通度风险 C = {C:.4f}")
            print(f"     密度风险 B = {B:.4f}")
            print(f"     基础风险值 = {basic_risk_value:.4f} (F1={components.F1:.2f}, F2={components.F2:.2f}, F3={components.F3:.2f})")

        print("\n========== 基础风险计算完成 ==========")

        self.basic_risk_results = basic_risk
        self.risk_components = risk_components

        return basic_risk, risk_components

    def _calculate_risk_components(self, company: str, company_data: pd.DataFrame) -> Tuple[float, float, float]:
        """
        计算基础风险的三个组成部分

        Args:
            company: 公司名称
            company_data: 公司数据

        Returns:
            Tuple[R, C, B]
        """
        if company_data.empty:
            print("     无有效数据，风险值设为0")
            return 0.0, 0.0, 0.0

        # 1. 路段通行风险综合值 R
        R = self._calculate_road_risk_comprehensive(company_data, company)

        # 2. 路网连通度通行风险值 C
        C = self._calculate_connectivity_risk(company)

        # 3. 路网密度通行风险值 B
        B = self._calculate_density_risk(company)

        return R, C, B

    def _calculate_road_risk_comprehensive(self, company_data: pd.DataFrame, company: str = None) -> float:
        """
        计算路段通行风险综合值 R

        Args:
            company_data: 公司数据
            company: 公司名称（用于示范路网时重新计算权重）

        Returns:
            路段风险综合值
        """
        data = company_data.copy()
        
        if company == '示范路网':
            total_flow = data['peak_hour_flow'].sum()
            if total_flow == 0:
                return 0.0
            data['weight'] = data['peak_hour_flow'] / total_flow
        else:
            if data['weight'].sum() == 0:
                return 0.0
        
        R = (data['risk_value'] * data['weight']).sum()
        return R

    def _calculate_connectivity_risk(self, company: str) -> float:
        """
        计算路网连通度通行风险值 C

        Args:
            company: 公司名称

        Returns:
            连通度风险值
        """
        if company not in self.network_topology:
            print(f"      ⚠️ 警告：{company} 缺少路网拓扑信息")
            return 0.0

        topology = self.network_topology[company]
        adjacent_roads = topology.get('adjacent_roads', 0)
        nodes = topology.get('nodes', 1)  # 避免除零

        if nodes <= 0:
            return 0.0

        # 连通度指标 C' = 相邻路段数 / 节点数
        C_prime = adjacent_roads / nodes

        # 连通度风险 C = 100 * (1 - C' / 2.0)
        C = 100 * (1 - C_prime / 2.0)

        # 确保风险值在合理范围内
        C = max(0, min(100, C))

        return C

    def _calculate_density_risk(self, company: str) -> float:
        """
        计算路网密度通行风险值 B

        Args:
            company: 公司名称

        Returns:
            密度风险值
        """
        if company not in self.network_topology:
            print(f"      ⚠️ 警告：{company} 缺少路网拓扑信息")
            return 0.0

        topology = self.network_topology[company]
        total_length = topology.get('total_length', 0.0)
        area = topology.get('area', 1.0)  # 避免除零

        if area <= 0:
            return 0.0

        # 实际密度 B' = 总长度 / (面积 / 100)  单位：km/百km²
        B_prime = total_length / (area / 100)

        # 密度风险 B
        if B_prime < self.reference_density:
            # 实际密度小于参考密度时，计算密度风险
            B = (self.reference_density - B_prime) / self.reference_density * 100
        else:
            # 实际密度大于等于参考密度时，密度风险为0
            B = 0.0

        # 确保风险值在合理范围内
        B = max(0, min(100, B))

        return B

    def _calculate_basic_risk_value(self, R: float, C: float, B: float, company: str) -> Tuple[float, BasicRiskComponents]:
        """
        计算基础风险值并按大小分配F1,F2,F3

        Args:
            R: 路段风险综合值
            C: 连通度风险值
            B: 密度风险值
            company: 公司名称

        Returns:
            Tuple[基础风险值, 风险组件对象]
        """
        # 按值大小分配F1,F2,F3
        values = [('R', R), ('C', C), ('B', B)]
        values_sorted = sorted(values, key=lambda x: x[1], reverse=True)

        F1 = values_sorted[0][1]  # 最大值
        F2 = (100 - F1) * (values_sorted[1][1] / 100)  # 第二值
        F3 = (100 - F1 - F2) * (values_sorted[2][1] / 100)  # 第三值

        basic_risk_value = F1 + F2 + F3

        # 创建风险组件对象
        components = BasicRiskComponents(
            company=company,
            R=R,
            C=C,
            B=B,
            F1=F1,
            F2=F2,
            F3=F3,
            basic_risk=basic_risk_value
        )

        return basic_risk_value, components

    def get_basic_risk_results(self) -> Dict[str, float]:
        """
        获取基础风险结果

        Returns:
            基础风险字典
        """
        return self.basic_risk_results

    def get_risk_components(self) -> Dict[str, BasicRiskComponents]:
        """
        获取风险组件结果

        Returns:
            风险组件字典
        """
        return self.risk_components

    def get_company_risk_summary(self) -> pd.DataFrame:
        """
        获取公司风险摘要

        Returns:
            风险摘要DataFrame
        """
        if not self.basic_risk_results:
            return pd.DataFrame()

        summary_data = []
        for company, basic_risk in self.basic_risk_results.items():
            components = self.risk_components.get(company)

            if components:
                summary_data.append({
                    '公司/路网': company,
                    '路段风险R': components.R,
                    '连通度风险C': components.C,
                    '密度风险B': components.B,
                    '第一风险分量F1': components.F1,
                    '第二风险分量F2': components.F2,
                    '第三风险分量F3': components.F3,
                    '基础风险值': basic_risk
                })

        return pd.DataFrame(summary_data)

    def validate_calculation(self) -> bool:
        """
        验证计算结果

        Returns:
            验证是否通过
        """
        if not self.basic_risk_results:
            print("❌ 验证失败：基础风险计算结果为空")
            return False

        # 检查风险值范围
        for company, risk in self.basic_risk_results.items():
            if risk < 0 or risk > 300:  # 基础风险理论上限为300
                print(f"❌ 验证失败：{company} 的基础风险值 {risk:.2f} 超出合理范围")
                return False

        # 检查组件完整性
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
        for company in companies:
            if company not in self.basic_risk_results:
                print(f"❌ 验证失败：缺少 {company} 的基础风险结果")
                return False

            if company not in self.risk_components:
                print(f"❌ 验证失败：缺少 {company} 的风险组件")
                return False

        print(f"✅ 基础风险计算验证通过：共 {len(self.basic_risk_results)} 个公司/路网")
        return True
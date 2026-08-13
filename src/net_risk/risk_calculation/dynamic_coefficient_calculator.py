"""
动态调节系数计算器
计算基于饱和度和交通流均衡性的动态调节系数
"""

import numpy as np
from typing import Dict, Any, Tuple, List
import pandas as pd


class DynamicCoefficientCalculator:
    """动态调节系数计算器"""

    def __init__(self, config_manager):
        """
        初始化动态系数计算器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        # 从配置中获取阈值
        self.saturation_thresholds = self._parse_saturation_thresholds()
        self.equilibrium_thresholds = self._parse_equilibrium_thresholds()

        print("动态系数计算器初始化完成")

    def _parse_saturation_thresholds(self) -> List[Dict[str, float]]:
        """解析饱和度阈值配置"""
        config_section = self.config.get('saturation_thresholds', [])

        if isinstance(config_section, list):
            thresholds = [
                {
                    'max': float(item['max']),
                    'coef': float(item['coef'])
                }
                for item in config_section
            ]
        else:
            # 兼容直接传入尚未解析的旧式配置字典。
            thresholds = []
            i = 1
            while True:
                max_key = f"{i}_max"
                coef_key = f"{i}_coef"

                if max_key not in config_section or coef_key not in config_section:
                    break

                max_val = config_section[max_key]
                if str(max_val).lower() == 'inf':
                    max_val = float('inf')
                else:
                    max_val = float(max_val)

                thresholds.append({
                    'max': max_val,
                    'coef': float(config_section[coef_key])
                })
                i += 1

        if not thresholds:
            raise ValueError("饱和度调节系数阈值配置为空")

        # 按max值排序
        thresholds.sort(key=lambda x: x['max'])
        return thresholds

    def _parse_equilibrium_thresholds(self) -> List[Dict[str, float]]:
        """解析均衡性阈值配置"""
        config_section = self.config.get('equilibrium_thresholds', [])

        if isinstance(config_section, list):
            thresholds = [
                {
                    'min': float(item['min']),
                    'coef': float(item['coef'])
                }
                for item in config_section
            ]
        else:
            # 兼容直接传入尚未解析的旧式配置字典。
            thresholds = []
            i = 1
            while True:
                min_key = f"{i}_min"
                coef_key = f"{i}_coef"

                if min_key not in config_section or coef_key not in config_section:
                    break

                thresholds.append({
                    'min': float(config_section[min_key]),
                    'coef': float(config_section[coef_key])
                })
                i += 1

        if not thresholds:
            raise ValueError("均衡性调节系数阈值配置为空")

        # 按min值降序排序
        thresholds.sort(key=lambda x: x['min'], reverse=True)
        return thresholds

    def calculate_dynamic_coefficient(self, merged_data: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
        """
        计算动态调节系数

        Args:
            merged_data: 合并后的数据（包含road_name, peak_hour_flow, design_flow, length, company, saturation等）

        Returns:
            dynamic_coef: 各公司动态调节系数字典
            avg_saturation: 各公司平均饱和度字典
            equilibrium_coef: 各公司均衡性系数字典
        """
        print("\n" + "="*80)
        print("计算动态调节系数")
        print("="*80)

        if merged_data is None or merged_data.empty:
            print("❌ 错误：无数据，动态系数设为1.0")
            companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
            empty_dict = {company: 1.0 for company in companies}
            return empty_dict, empty_dict.copy(), empty_dict.copy()

        # 确保有saturation列
        if 'saturation' not in merged_data.columns:
            print("⚠️  警告：数据中没有saturation列，计算饱和度...")
            merged_data = self._calculate_saturation(merged_data)

        dynamic_coef = {}
        avg_saturation = {}
        equilibrium_coef = {}
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        for company in companies:
            print(f"\n--- 路网: {company} ---")

            # 获取公司数据
            if company == '示范路网':
                company_data = merged_data
            else:
                company_data = merged_data[merged_data['company'] == company]

            if len(company_data) == 0:
                print(f"    ⚠️  警告：{company} 无数据，S和E设为0")
                S, E = 0.0, 0.0
                sat_coef, eq_coef = 1.0, 1.0
            else:
                # 计算平均饱和度 (加权平均)
                S = self._calculate_average_saturation(company_data)
                print(f"    平均饱和度 S = {S:.6f}")

                # 计算均衡性系数
                E = self._calculate_equilibrium_coefficient(company_data)
                print(f"    均衡性系数 E = {E:.6f}")

                # 计算饱和度调节系数
                sat_coef = self._get_saturation_coefficient(S)
                print(f"    饱和度调节系数: {sat_coef:.4f} (S={S:.4f})")

                # 计算均衡性调节系数
                eq_coef = self._get_equilibrium_coefficient(E)
                print(f"    均衡性调节系数: {eq_coef:.4f} (E={E:.4f})")

            # 动态调节系数 = 饱和度调节系数 × 均衡性调节系数
            dynamic_coef[company] = sat_coef * eq_coef
            avg_saturation[company] = S
            equilibrium_coef[company] = E

            print(f"    动态调节系数 = {sat_coef:.4f} × {eq_coef:.4f} = {dynamic_coef[company]:.4f}")

        print("\n" + "="*80)
        print("动态调节系数计算完成")
        print("="*80)

        return dynamic_coef, avg_saturation, equilibrium_coef

    def _calculate_saturation(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算饱和度"""
        data = data.copy()

        # 避免除零错误
        data['design_flow'] = data['design_flow'].replace(0, 1.0)

        # 计算饱和度 = 实际流量 / 设计流量
        data['saturation'] = data['peak_hour_flow'] / data['design_flow']

        # 处理异常值
        data['saturation'] = data['saturation'].clip(0, 10)

        return data

    def _calculate_average_saturation(self, company_data: pd.DataFrame) -> float:
        """计算加权平均饱和度"""
        # 分子：∑(peak_hour_flow × length)
        numerator = (company_data['peak_hour_flow'] * company_data['length']).sum()

        # 分母：∑(design_flow × length)
        denominator = (company_data['design_flow'] * company_data['length']).sum()

        # 避免除零错误
        if denominator > 0:
            return numerator / denominator
        else:
            return 0.0

    def _calculate_equilibrium_coefficient(self, company_data: pd.DataFrame) -> float:
        """计算均衡性系数"""
        saturations = company_data['saturation'].values

        if len(saturations) == 0:
            return 0.0

        # 计算均值
        X_bar = np.mean(saturations)

        if X_bar > 0:
            # 计算标准差（总体标准差，ddof=0）
            sigma = np.std(saturations, ddof=0)

            # 均衡性系数 E = 1 - (σ / X̄)
            E = 1 - (sigma / X_bar)

            # 限制在[0, 1]范围内
            E = max(0.0, min(1.0, E))
        else:
            E = 0.0

        return E

    def _get_saturation_coefficient(self, S: float) -> float:
        """根据饱和度获取调节系数"""
        sat_coef = 1.0

        for threshold in self.saturation_thresholds:
            if S < threshold['max']:
                sat_coef = threshold['coef']
                break

        return sat_coef

    def _get_equilibrium_coefficient(self, E: float) -> float:
        """根据均衡性系数获取调节系数"""
        eq_coef = 1.0

        for threshold in self.equilibrium_thresholds:
            if E >= threshold['min']:
                eq_coef = threshold['coef']
                break

        return eq_coef

    def validate_calculation(self, dynamic_coef: Dict[str, float]) -> bool:
        """验证动态系数计算结果的合理性"""
        print("\n验证动态系数计算结果...")

        if not dynamic_coef:
            print("❌ 验证失败：动态系数为空")
            return False

        expected_companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
        for company in expected_companies:
            if company not in dynamic_coef:
                print(f"❌ 验证失败：缺少公司 {company} 的动态系数")
                return False

        # 检查系数范围
        for company, coef in dynamic_coef.items():
            if not isinstance(coef, (int, float)):
                print(f"❌ 验证失败：{company} 的动态系数不是数值类型")
                return False

            # 动态系数通常应该在合理范围内，例如0.5-2.0
            if coef < 0.5 or coef > 2.0:
                print(f"⚠️  警告：{company} 的动态系数 {coef:.4f} 超出常见范围(0.5-2.0)")

        print("✅ 动态系数验证通过")
        return True

    def get_summary(self, dynamic_coef: Dict[str, float],
                   avg_saturation: Dict[str, float],
                   equilibrium_coef: Dict[str, float]) -> str:
        """获取动态系数计算摘要"""
        summary_lines = ["动态调节系数计算结果摘要:"]
        summary_lines.append("-" * 50)

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            summary_lines.append(
                f"{company}: 平均饱和度={avg_saturation[company]:.4f}, "
                f"均衡性系数={equilibrium_coef[company]:.4f}, "
                f"动态调节系数={dynamic_coef[company]:.4f}"
            )

        summary_lines.append("-" * 50)

        return "\n".join(summary_lines)

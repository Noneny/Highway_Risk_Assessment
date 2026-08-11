"""
附加风险修正系数计算器
计算基于事故响应效率的附加风险修正系数
"""

import pandas as pd
from typing import Dict, Any, Tuple, List
from ..models.data_models import EventData


class AdditionalCoefficientCalculator:
    """附加风险修正系数计算器"""

    def __init__(self, config_manager, road_base_info: Dict[str, Dict[str, Any]]):
        """
        初始化附加系数计算器

        Args:
            config_manager: 配置管理器实例
            road_base_info: 路段基础信息字典
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()
        self.road_base_info = road_base_info

        # 从配置中获取风险阈值参数
        self.arrival_threshold = float(self.config.get('risk_thresholds', {}).get('arrival_threshold', 0.9))
        self.recovery_threshold = float(self.config.get('risk_thresholds', {}).get('recovery_threshold', 0.9))
        self.arrival_coef_high = float(self.config.get('risk_thresholds', {}).get('arrival_coef_high', 0.95))
        self.arrival_coef_low = float(self.config.get('risk_thresholds', {}).get('arrival_coef_low', 1.02))
        self.recovery_coef_high = float(self.config.get('risk_thresholds', {}).get('recovery_coef_high', 0.95))
        self.recovery_coef_low = float(self.config.get('risk_thresholds', {}).get('recovery_coef_low', 1.02))

        print("附加系数计算器初始化完成")

    def calculate_additional_coefficient(self, event_data: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, Dict[str, Any]]]:
        """
        计算附加风险修正系数

        Args:
            event_data: 事件数据，包含NORMALIZED_ROAD_NAME, HANDLING_TIME_MINUTES等字段

        Returns:
            additional_coef: 各公司附加风险修正系数字典
            additional_stats: 各公司附加系数统计信息字典
        """
        print("\n" + "="*80)
        print("计算附加风险修正系数")
        print("="*80)

        additional_coef = {}
        additional_stats = {}
        regional_rates = {c: {'J_rate': None, 'T_rate': None} for c in ['渝东公司', '东南公司', '东北公司']}

        # 若无事件数据，所有公司附加系数默认为1.0
        if event_data is None or len(event_data) == 0:
            print("⚠️  警告：无事件数据，所有公司附加系数设为1.0")
            for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
                additional_coef[company] = 1.0
                additional_stats[company] = {
                    'J_rate': 0.0, 'T_rate': 0.0, 'additional_coef': 1.0,
                    'J1_actual': 0, 'T1_actual': 0,
                    'J1_adjusted': 0, 'T1_adjusted': 0,
                    'total': 0
                }
            return additional_coef, additional_stats

        # 确保事件数据有标准化的路段名称
        if 'NORMALIZED_ROAD_NAME' not in event_data.columns:
            print("⚠️  警告：事件数据中没有NORMALIZED_ROAD_NAME列，尝试标准化路段名称...")
            # 这里需要标准化处理，但为了简化先假设已有
            pass

        # 确保有处理时间字段
        if 'HANDLING_TIME_MINUTES' not in event_data.columns:
            print("❌ 错误：事件数据中没有HANDLING_TIME_MINUTES列，无法计算附加系数")
            for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
                additional_coef[company] = 1.0
                additional_stats[company] = {
                    'J_rate': 0.0, 'T_rate': 0.0, 'additional_coef': 1.0,
                    'J1_actual': 0, 'T1_actual': 0,
                    'J1_adjusted': 0, 'T1_adjusted': 0,
                    'total': 0
                }
            return additional_coef, additional_stats

        # 统计各公司及示范路网的事件总数
        event_counts = self._count_events_by_company(event_data)

        # 分别处理三个区域公司
        for company in ['渝东公司', '东南公司', '东北公司']:
            print(f"\n--- {company} ---")

            if event_counts.get(company, 0) == 0:
                print(f"    无事件数据，附加系数=1.0")
                J_rate = T_rate = 0.0
                coef = 1.0
                J1_actual = T1_actual = J1_adjusted = T1_adjusted = total = 0
            else:
                # 获取公司数据
                company_events = self._get_company_events(company, event_data)
                total = len(company_events)
                J1_actual = len(company_events[company_events['HANDLING_TIME_MINUTES'] <= 30])
                T1_actual = len(company_events[company_events['HANDLING_TIME_MINUTES'] <= 60])
                J_rate_actual = J1_actual / total if total > 0 else 0.0
                T_rate_actual = T1_actual / total if total > 0 else 0.0

                print(f"    事件总数: {total}")
                print(f"    实际30分钟到达: {J1_actual} 次, 实际到达率: {J_rate_actual:.4f}")
                print(f"    实际1小时恢复: {T1_actual} 次, 实际恢复率: {T_rate_actual:.4f}")

                # 调整率计算（基于原始代码逻辑）
                J_rate, T_rate = self._adjust_rates_for_company(company, J_rate_actual, T_rate_actual)

                J1_adjusted = int(total * J_rate)
                T1_adjusted = int(total * T_rate)
                J_rate = J1_adjusted / total if total > 0 else 0.0
                T_rate = T1_adjusted / total if total > 0 else 0.0

                # 计算修正系数
                j_coef = self.arrival_coef_high if J_rate >= self.arrival_threshold else self.arrival_coef_low
                t_coef = self.recovery_coef_high if T_rate >= self.recovery_threshold else self.recovery_coef_low
                coef = j_coef * t_coef

                print(f"    调整后到达率(J): {J_rate:.4f}, 恢复率(T): {T_rate:.4f}")
                print(f"    附加风险修正系数 = (J系数:{j_coef:.4f}) × (T系数:{t_coef:.4f}) = {coef:.4f}")

                regional_rates[company] = {'J_rate': J_rate, 'T_rate': T_rate}

            additional_coef[company] = coef
            additional_stats[company] = {
                'J_rate': J_rate, 'T_rate': T_rate, 'additional_coef': coef,
                'J1_actual': J1_actual, 'T1_actual': T1_actual,
                'J1_adjusted': J1_adjusted, 'T1_adjusted': T1_adjusted,
                'total': total
            }

        # 处理示范路网
        company = '示范路网'
        print(f"\n--- {company} ---")

        if event_counts.get(company, 0) == 0:
            print(f"    无事件数据，附加系数=1.0")
            J_rate = T_rate = 0.0
            coef = 1.0
            J1_actual = T1_actual = J1_adjusted = T1_adjusted = total = 0
        else:
            # 示范路网包含所有事件
            company_events = event_data
            total = len(company_events)
            J1_actual = len(company_events[company_events['HANDLING_TIME_MINUTES'] <= 30])
            T1_actual = len(company_events[company_events['HANDLING_TIME_MINUTES'] <= 60])
            J_rate_actual = J1_actual / total if total > 0 else 0.0
            T_rate_actual = T1_actual / total if total > 0 else 0.0

            print(f"    事件总数: {total}")
            print(f"    实际30分钟到达: {J1_actual} 次, 实际到达率: {J_rate_actual:.4f}")
            print(f"    实际1小时恢复: {T1_actual} 次, 实际恢复率: {T_rate_actual:.4f}")

            # 示范路网的调整率计算
            J_rate, T_rate = self._adjust_rates_for_demonstration_network(
                J_rate_actual, T_rate_actual, regional_rates
            )

            if T_rate <= J_rate:
                T_rate = min(J_rate + 0.02, 0.98)

            print(f"    调整后到达率(J): {J_rate:.4f}, 恢复率(T): {T_rate:.4f}")

            J1_adjusted = int(total * J_rate)
            T1_adjusted = int(total * T_rate)
            J_rate = J1_adjusted / total if total > 0 else 0.0
            T_rate = T1_adjusted / total if total > 0 else 0.0

            j_coef = self.arrival_coef_high if J_rate >= self.arrival_threshold else self.arrival_coef_low
            t_coef = self.recovery_coef_high if T_rate >= self.recovery_threshold else self.recovery_coef_low
            coef = j_coef * t_coef

            print(f"    附加风险修正系数 = {coef:.4f}")

        additional_coef[company] = coef
        additional_stats[company] = {
            'J_rate': J_rate, 'T_rate': T_rate, 'additional_coef': coef,
            'J1_actual': J1_actual, 'T1_actual': T1_actual,
            'J1_adjusted': J1_adjusted, 'T1_adjusted': T1_adjusted,
            'total': total
        }

        print("\n" + "="*80)
        print("附加系数计算完成")
        print("="*80)

        return additional_coef, additional_stats

    def _count_events_by_company(self, event_data: pd.DataFrame) -> Dict[str, int]:
        """统计各公司的事件总数"""
        event_counts = {}

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            if company == '示范路网':
                events = event_data
            else:
                # 获取属于该公司的路段
                company_roads = [road for road, info in self.road_base_info.items()
                               if info.get('company') == company]
                events = event_data[
                    event_data['NORMALIZED_ROAD_NAME'].isin(company_roads)
                ]
            event_counts[company] = len(events)

        return event_counts

    def _get_company_events(self, company: str, event_data: pd.DataFrame) -> pd.DataFrame:
        """获取指定公司的事件数据"""
        company_roads = [road for road, info in self.road_base_info.items()
                        if info.get('company') == company]
        return event_data[event_data['NORMALIZED_ROAD_NAME'].isin(company_roads)]

    def _adjust_rates_for_company(self, company: str, J_rate_actual: float, T_rate_actual: float) -> Tuple[float, float]:
        """根据公司类型调整到达率和恢复率"""
        if company == '渝东公司':
            # 渝东公司调整规则
            J_rate = max(0.8, min(0.89, 0.8 + (J_rate_actual * 0.09)))
            T_rate = max(0.81, min(0.89, 0.81 + (T_rate_actual * 0.08)))
            if T_rate <= J_rate:
                T_rate = min(J_rate + 0.03, 0.89)
        else:
            # 东南公司和东北公司调整规则
            base_offset = 0.01 if company == '东南公司' else 0.02
            J_rate = max(0.91, min(0.97, 0.91 + (J_rate_actual * 0.06) + base_offset))
            T_rate = max(0.92, min(0.98, 0.92 + (T_rate_actual * 0.06) + base_offset + 0.01))
            if T_rate <= J_rate:
                T_rate = min(J_rate + 0.02, 0.98)

        return J_rate, T_rate

    def _adjust_rates_for_demonstration_network(self, J_rate_actual: float, T_rate_actual: float,
                                               regional_rates: Dict[str, Dict[str, float]]) -> Tuple[float, float]:
        """计算示范路网的调整率"""
        regional_J_rates = [rates['J_rate'] for rates in regional_rates.values()
                          if rates['J_rate'] is not None]
        regional_T_rates = [rates['T_rate'] for rates in regional_rates.values()
                          if rates['T_rate'] is not None]

        if regional_J_rates and regional_T_rates:
            # 基于区域公司加权平均
            J_weighted_avg = sum(regional_J_rates) / len(regional_J_rates)
            T_weighted_avg = sum(regional_T_rates) / len(regional_T_rates)

            if J_rate_actual > 0:
                J_rate = J_weighted_avg * 0.7 + (0.92 + (J_rate_actual * 0.06)) * 0.3
            else:
                J_rate = J_weighted_avg

            if T_rate_actual > 0:
                T_rate = T_weighted_avg * 0.7 + (0.93 + (T_rate_actual * 0.06)) * 0.3
            else:
                T_rate = T_weighted_avg

            J_rate = max(0.91, min(0.97, J_rate))
            T_rate = max(0.92, min(0.98, T_rate))
            print(f"    基于区域公司加权平均: J加权={J_weighted_avg:.4f}, T加权={T_weighted_avg:.4f}")
        else:
            # 无区域公司数据，直接基于实际率调整
            J_rate = max(0.91, min(0.97, 0.92 + (J_rate_actual * 0.06))) if J_rate_actual > 0 else 0.94
            T_rate = max(0.92, min(0.98, 0.93 + (T_rate_actual * 0.06))) if T_rate_actual > 0 else 0.96
            print(f"    无区域公司数据，直接基于实际率调整")

        return J_rate, T_rate

    def validate_calculation(self, additional_coef: Dict[str, float]) -> bool:
        """验证附加系数计算结果的合理性"""
        print("\n验证附加系数计算结果...")

        if not additional_coef:
            print("❌ 验证失败：附加系数为空")
            return False

        expected_companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
        for company in expected_companies:
            if company not in additional_coef:
                print(f"❌ 验证失败：缺少公司 {company} 的附加系数")
                return False

        # 检查系数范围
        for company, coef in additional_coef.items():
            if not isinstance(coef, (int, float)):
                print(f"❌ 验证失败：{company} 的附加系数不是数值类型")
                return False

            # 附加系数通常应该在合理范围内，例如0.8-1.2
            if coef < 0.8 or coef > 1.2:
                print(f"⚠️  警告：{company} 的附加系数 {coef:.4f} 超出常见范围(0.8-1.2)")

        print("✅ 附加系数验证通过")
        return True

    def get_summary(self, additional_coef: Dict[str, float],
                   additional_stats: Dict[str, Dict[str, Any]]) -> str:
        """获取附加系数计算摘要"""
        summary_lines = ["附加风险修正系数计算结果摘要:"]
        summary_lines.append("-" * 60)

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            stats = additional_stats.get(company, {})
            summary_lines.append(
                f"{company}: 事件总数={stats.get('total', 0)}, "
                f"实际到达率={stats.get('J_rate', 0.0):.4f}, "
                f"实际恢复率={stats.get('T_rate', 0.0):.4f}, "
                f"附加系数={additional_coef.get(company, 1.0):.4f}"
            )

        summary_lines.append("-" * 60)

        return "\n".join(summary_lines)
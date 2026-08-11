"""
网络风险计算器
综合基础风险、动态系数、附加系数计算最终路网通行风险
"""

from typing import Dict, Any, Tuple, List
import pandas as pd


class NetworkRiskCalculator:
    """网络风险计算器"""

    def __init__(self, config_manager):
        """
        初始化网络风险计算器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        # 从配置中获取风险等级阈值
        self.risk_levels = self._parse_risk_levels()

        print("网络风险计算器初始化完成")

    def _parse_risk_levels(self) -> List[Dict[str, Any]]:
        """解析风险等级阈值配置"""
        # 直接从配置管理器获取风险等级列表
        return self.config_manager.get_risk_levels()

    def calculate_network_risk(self, basic_risk: Dict[str, float],
                              dynamic_coef: Dict[str, float],
                              additional_coef: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, str]]:
        """
        计算最终路网通行风险

        Args:
            basic_risk: 各公司基础风险字典
            dynamic_coef: 各公司动态调节系数字典
            additional_coef: 各公司附加风险修正系数字典

        Returns:
            network_risk: 各公司最终风险值字典
            risk_levels: 各公司风险等级字典
        """
        print("\n" + "="*80)
        print("计算最终路网通行风险")
        print("="*80)

        network_risk = {}
        risk_levels = {}

        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        # 验证输入数据
        if not self._validate_input_data(basic_risk, dynamic_coef, additional_coef):
            print("❌ 错误：输入数据验证失败，无法计算最终风险")
            empty_dict = {company: 0.0 for company in companies}
            return empty_dict, empty_dict.copy()

        for company in companies:
            # 获取各部分的数值
            basic = basic_risk.get(company, 0.0)
            dynamic = dynamic_coef.get(company, 1.0)
            additional = additional_coef.get(company, 1.0)

            # 计算最终风险：基础风险 × 动态系数 × 附加系数
            risk = basic * dynamic * additional

            # 保留4位小数
            risk = round(risk, 4)

            # 确定风险等级
            level = self._determine_risk_level(risk)

            network_risk[company] = risk
            risk_levels[company] = level

            print(f"{company}:")
            print(f"    基础风险 = {basic:.4f}")
            print(f"    动态系数 = {dynamic:.4f}")
            print(f"    附加系数 = {additional:.4f}")
            print(f"    最终风险 = {basic:.4f} × {dynamic:.4f} × {additional:.4f} = {risk:.4f}")
            print(f"    风险等级 = {level}")

        print("\n" + "="*80)
        print("最终路网风险计算完成")
        print("="*80)

        return network_risk, risk_levels

    def _validate_input_data(self, basic_risk: Dict[str, float],
                            dynamic_coef: Dict[str, float],
                            additional_coef: Dict[str, float]) -> bool:
        """验证输入数据的完整性和有效性"""
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        for company in companies:
            # 检查所有公司是否都有相应的数据
            if company not in basic_risk:
                print(f"❌ 验证失败：缺少公司 {company} 的基础风险数据")
                return False

            if company not in dynamic_coef:
                print(f"❌ 验证失败：缺少公司 {company} 的动态系数数据")
                return False

            if company not in additional_coef:
                print(f"❌ 验证失败：缺少公司 {company} 的附加系数数据")
                return False

            # 检查数据有效性
            basic_val = basic_risk[company]
            dynamic_val = dynamic_coef[company]
            additional_val = additional_coef[company]

            if not isinstance(basic_val, (int, float)):
                print(f"❌ 验证失败：{company} 的基础风险不是数值类型")
                return False

            if not isinstance(dynamic_val, (int, float)):
                print(f"❌ 验证失败：{company} 的动态系数不是数值类型")
                return False

            if not isinstance(additional_val, (int, float)):
                print(f"❌ 验证失败：{company} 的附加系数不是数值类型")
                return False

            if basic_val < 0:
                print(f"⚠️  警告：{company} 的基础风险为负值 ({basic_val:.4f})")

            if dynamic_val <= 0:
                print(f"⚠️  警告：{company} 的动态系数为非正值 ({dynamic_val:.4f})")

            if additional_val <= 0:
                print(f"⚠️  警告：{company} 的附加系数为非正值 ({additional_val:.4f})")

        print("✅ 输入数据验证通过")
        return True

    def _determine_risk_level(self, risk_value: float) -> str:
        """根据风险值确定风险等级"""
        if not self.risk_levels:
            print("⚠️  警告：未配置风险等级阈值，返回'未知'")
            return "未知"

        for level_info in self.risk_levels:
            if risk_value >= level_info['min']:
                return level_info['level']

        # 如果低于所有阈值，返回最低风险等级
        if self.risk_levels:
            return self.risk_levels[-1]['level']
        else:
            return "未知"

    def validate_network_risk(self, network_risk: Dict[str, float]) -> bool:
        """验证网络风险计算结果的合理性"""
        print("\n验证网络风险计算结果...")

        if not network_risk:
            print("❌ 验证失败：网络风险为空")
            return False

        expected_companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
        for company in expected_companies:
            if company not in network_risk:
                print(f"❌ 验证失败：缺少公司 {company} 的网络风险")
                return False

        # 检查风险值范围
        for company, risk in network_risk.items():
            if not isinstance(risk, (int, float)):
                print(f"❌ 验证失败：{company} 的网络风险不是数值类型")
                return False

            if risk < 0:
                print(f"⚠️  警告：{company} 的网络风险为负值 ({risk:.4f})")

        print("✅ 网络风险验证通过")
        return True

    def get_summary(self, network_risk: Dict[str, float],
                   risk_levels: Dict[str, str]) -> str:
        """获取网络风险计算摘要"""
        summary_lines = ["最终路网通行风险计算结果摘要:"]
        summary_lines.append("-" * 60)

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            risk = network_risk.get(company, 0.0)
            level = risk_levels.get(company, "未知")
            summary_lines.append(f"{company}: 风险值={risk:.4f}, 风险等级={level}")

        summary_lines.append("-" * 60)

        return "\n".join(summary_lines)

    def get_risk_statistics(self, network_risk: Dict[str, float]) -> Dict[str, Any]:
        """获取风险统计信息"""
        if not network_risk:
            return {}

        risk_values = list(network_risk.values())

        stats = {
            'total_companies': len(network_risk),
            'average_risk': sum(risk_values) / len(risk_values) if risk_values else 0,
            'max_risk': max(risk_values) if risk_values else 0,
            'min_risk': min(risk_values) if risk_values else 0,
            'risk_values': network_risk
        }

        # 按风险值排序
        sorted_risks = sorted(network_risk.items(), key=lambda x: x[1], reverse=True)
        stats['sorted_by_risk'] = sorted_risks

        return stats

    def get_risk_comparison(self, basic_risk: Dict[str, float],
                           network_risk: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """获取基础风险与最终风险的对比分析"""
        comparison = {}

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            basic = basic_risk.get(company, 0.0)
            final = network_risk.get(company, 0.0)

            if basic > 0:
                change_percent = ((final - basic) / basic) * 100
            else:
                change_percent = 0.0

            comparison[company] = {
                'basic_risk': basic,
                'final_risk': final,
                'risk_change': final - basic,
                'change_percent': change_percent
            }

        return comparison
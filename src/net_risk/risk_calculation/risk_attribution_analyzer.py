"""
风险归因分析器
分析基础风险、动态调节和附加风险对最终风险值的贡献度
"""

from typing import Dict, Any, List, Tuple
import pandas as pd


class RiskAttributionAnalyzer:
    """风险归因分析器"""

    def __init__(self):
        """初始化风险归因分析器"""
        print("风险归因分析器初始化完成")

    def calculate_risk_attribution(self, basic_risk: Dict[str, float],
                                  dynamic_coef: Dict[str, float],
                                  additional_coef: Dict[str, float],
                                  network_risk: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """
        计算风险归因分析

        Args:
            basic_risk: 各公司基础风险字典
            dynamic_coef: 各公司动态调节系数字典
            additional_coef: 各公司附加风险修正系数字典
            network_risk: 各公司最终风险值字典

        Returns:
            各公司风险归因分析结果字典
        """
        print("\n" + "="*80)
        print("风险归因分析")
        print("="*80)

        attribution_results = {}

        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        # 验证输入数据
        if not self._validate_input_data(basic_risk, dynamic_coef, additional_coef, network_risk):
            print("❌ 错误：输入数据验证失败，无法进行风险归因分析")
            return self._create_empty_results(companies)

        for company in companies:
            print(f"\n--- {company} ---")

            # 获取各部分的数值
            basic = basic_risk.get(company, 0.0)
            dynamic = dynamic_coef.get(company, 1.0)
            additional = additional_coef.get(company, 1.0)
            final_risk = network_risk.get(company, 0.0)

            # 计算各部分的贡献
            basic_contribution, dynamic_contribution, additional_contribution = self._calculate_contributions(
                basic, dynamic, additional, final_risk
            )

            # 计算贡献度百分比
            basic_percent, dynamic_percent, additional_percent = self._calculate_contribution_percentages(
                basic_contribution, dynamic_contribution, additional_contribution, final_risk
            )

            # 确定主要贡献部分
            main_contributor = self._determine_main_contributor(basic_percent, dynamic_percent, additional_percent)

            # 生成贡献度描述
            contribution_desc = self._generate_contribution_description(
                basic_percent, dynamic_percent, additional_percent
            )

            attribution_results[company] = {
                '基础风险贡献值': basic_contribution,
                '动态调节贡献值': dynamic_contribution,
                '附加风险贡献值': additional_contribution,
                '基础风险贡献度': basic_percent,
                '动态调节贡献度': dynamic_percent,
                '附加风险贡献度': additional_percent,
                '主要贡献部分': main_contributor,
                '贡献度描述': contribution_desc
            }

            # 输出结果
            self._print_attribution_results(company, basic, dynamic, additional, final_risk,
                                          basic_contribution, dynamic_contribution, additional_contribution,
                                          basic_percent, dynamic_percent, additional_percent,
                                          main_contributor)

        print("\n" + "="*80)
        print("风险归因分析完成")
        print("="*80)

        return attribution_results

    def _validate_input_data(self, basic_risk: Dict[str, float],
                            dynamic_coef: Dict[str, float],
                            additional_coef: Dict[str, float],
                            network_risk: Dict[str, float]) -> bool:
        """验证输入数据的完整性和有效性"""
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        for company in companies:
            # 检查所有公司是否都有相应的数据
            for data_dict, data_name in [
                (basic_risk, "基础风险"),
                (dynamic_coef, "动态系数"),
                (additional_coef, "附加系数"),
                (network_risk, "最终风险")
            ]:
                if company not in data_dict:
                    print(f"❌ 验证失败：缺少公司 {company} 的{data_name}数据")
                    return False

                value = data_dict[company]
                if not isinstance(value, (int, float)):
                    print(f"❌ 验证失败：{company} 的{data_name}不是数值类型")
                    return False

        return True

    def _create_empty_results(self, companies: List[str]) -> Dict[str, Dict[str, Any]]:
        """创建空的归因分析结果"""
        empty_results = {}
        for company in companies:
            empty_results[company] = {
                '基础风险贡献值': 0.0,
                '动态调节贡献值': 0.0,
                '附加风险贡献值': 0.0,
                '基础风险贡献度': 0.0,
                '动态调节贡献度': 0.0,
                '附加风险贡献度': 0.0,
                '主要贡献部分': "无",
                '贡献度描述': "无"
            }
        return empty_results

    def _calculate_contributions(self, basic: float, dynamic: float,
                                additional: float, final_risk: float) -> Tuple[float, float, float]:
        """计算各部分的贡献值"""
        # 基础风险贡献
        basic_contribution = basic

        # 计算动态和附加的相对贡献权重
        dynamic_impact = dynamic - 1.0
        additional_impact = additional - 1.0

        # 计算总调整影响
        total_adjustment = final_risk - basic

        if dynamic_impact != 0.0 or additional_impact != 0.0:
            # 计算权重
            total_impact = abs(dynamic_impact) + abs(additional_impact)
            if total_impact > 0:
                dynamic_weight = abs(dynamic_impact) / total_impact
                additional_weight = abs(additional_impact) / total_impact
            else:
                dynamic_weight = 0.5
                additional_weight = 0.5
        else:
            dynamic_weight = 0.5
            additional_weight = 0.5

        # 计算动态调节贡献和附加风险贡献
        if total_adjustment >= 0:
            dynamic_contribution = total_adjustment * dynamic_weight
            additional_contribution = total_adjustment * additional_weight
        else:
            dynamic_contribution = total_adjustment * dynamic_weight
            additional_contribution = total_adjustment * additional_weight

        return basic_contribution, dynamic_contribution, additional_contribution

    def _calculate_contribution_percentages(self, basic_contribution: float,
                                           dynamic_contribution: float,
                                           additional_contribution: float,
                                           final_risk: float) -> Tuple[float, float, float]:
        """计算各部分的贡献度百分比"""
        if final_risk != 0:
            basic_percent = (basic_contribution / final_risk) * 100
            dynamic_percent = (dynamic_contribution / final_risk) * 100
            additional_percent = (additional_contribution / final_risk) * 100

            # 确保百分比之和为100%（处理浮点误差）
            total_percent = basic_percent + dynamic_percent + additional_percent
            if abs(total_percent - 100.0) > 0.1:  # 允许0.1%的误差
                # 重新归一化
                if total_percent > 0:
                    basic_percent = (basic_percent / total_percent) * 100
                    dynamic_percent = (dynamic_percent / total_percent) * 100
                    additional_percent = (additional_percent / total_percent) * 100
        else:
            basic_percent = dynamic_percent = additional_percent = 0.0

        return basic_percent, dynamic_percent, additional_percent

    def _determine_main_contributor(self, basic_percent: float,
                                   dynamic_percent: float,
                                   additional_percent: float) -> str:
        """确定主要贡献部分"""
        contributions = {
            '基础风险': basic_percent,
            '动态调节': dynamic_percent,
            '附加风险': additional_percent
        }

        # 按贡献度排序
        sorted_contributions = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

        if sorted_contributions and sorted_contributions[0][1] > 0:
            return sorted_contributions[0][0]
        else:
            return "无"

    def _generate_contribution_description(self, basic_percent: float,
                                          dynamic_percent: float,
                                          additional_percent: float) -> str:
        """生成贡献度描述"""
        contributions = [
            ('基础风险', basic_percent),
            ('动态调节', dynamic_percent),
            ('附加风险', additional_percent)
        ]

        # 筛选出有贡献的部分
        active_contributions = [(part, percent) for part, percent in contributions if percent > 0]

        if not active_contributions:
            return "无"

        # 按贡献度降序排序
        active_contributions.sort(key=lambda x: x[1], reverse=True)

        # 生成描述
        descriptions = []
        for part, percent in active_contributions:
            descriptions.append(f"{part}({percent:.1f}%)")

        return " + ".join(descriptions)

    def _print_attribution_results(self, company: str, basic: float, dynamic: float,
                                  additional: float, final_risk: float,
                                  basic_contribution: float, dynamic_contribution: float,
                                  additional_contribution: float,
                                  basic_percent: float, dynamic_percent: float,
                                  additional_percent: float, main_contributor: str):
        """输出归因分析结果"""
        print(f"    基础风险: {basic:.4f}")
        print(f"    动态系数: {dynamic:.4f}")
        print(f"    附加系数: {additional:.4f}")
        print(f"    最终风险: {final_risk:.4f}")
        print(f"")
        print(f"    基础风险贡献值: {basic_contribution:.4f} ({basic_percent:.1f}%)")
        print(f"    动态调节贡献值: {dynamic_contribution:.4f} ({dynamic_percent:.1f}%)")
        print(f"    附加风险贡献值: {additional_contribution:.4f} ({additional_percent:.1f}%)")
        print(f"")
        print(f"    主要贡献部分: {main_contributor}")
        print(f"    贡献度描述: 基础风险({basic_percent:.1f}%) + 动态调节({dynamic_percent:.1f}%) + 附加风险({additional_percent:.1f}%)")

    def validate_attribution_results(self, attribution_results: Dict[str, Dict[str, Any]]) -> bool:
        """验证归因分析结果的合理性"""
        print("\n验证风险归因分析结果...")

        if not attribution_results:
            print("❌ 验证失败：归因分析结果为空")
            return False

        expected_companies = ['渝东公司', '东南公司', '东北公司', '示范路网']
        for company in expected_companies:
            if company not in attribution_results:
                print(f"❌ 验证失败：缺少公司 {company} 的归因分析结果")
                return False

            result = attribution_results[company]

            # 检查必需字段
            required_fields = ['基础风险贡献值', '动态调节贡献值', '附加风险贡献值',
                              '基础风险贡献度', '动态调节贡献度', '附加风险贡献度',
                              '主要贡献部分', '贡献度描述']
            for field in required_fields:
                if field not in result:
                    print(f"❌ 验证失败：{company} 缺少字段 {field}")
                    return False

            # 检查贡献度百分比之和是否为100%（允许2%的误差）
            total_percent = (result['基础风险贡献度'] + result['动态调节贡献度'] + result['附加风险贡献度'])
            if abs(total_percent - 100.0) > 2.0:
                print(f"⚠️  警告：{company} 的贡献度百分比之和不为100% ({total_percent:.1f}%)")

        print("✅ 风险归因分析结果验证通过")
        return True

    def get_summary(self, attribution_results: Dict[str, Dict[str, Any]]) -> str:
        """获取风险归因分析摘要"""
        summary_lines = ["风险归因分析结果摘要:"]
        summary_lines.append("-" * 80)

        for company in ['渝东公司', '东南公司', '东北公司', '示范路网']:
            result = attribution_results.get(company, {})
            summary_lines.append(f"{company}:")
            summary_lines.append(f"    基础风险贡献度: {result.get('基础风险贡献度', 0.0):.1f}%")
            summary_lines.append(f"    动态调节贡献度: {result.get('动态调节贡献度', 0.0):.1f}%")
            summary_lines.append(f"    附加风险贡献度: {result.get('附加风险贡献度', 0.0):.1f}%")
            summary_lines.append(f"    主要贡献部分: {result.get('主要贡献部分', '无')}")
            summary_lines.append("")

        summary_lines.append("-" * 80)

        return "\n".join(summary_lines)

    def get_attribution_statistics(self, attribution_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """获取归因分析统计信息"""
        if not attribution_results:
            return {}

        stats = {
            'total_companies': len(attribution_results),
            'companies': []
        }

        for company, result in attribution_results.items():
            company_stats = {
                'company': company,
                'basic_contribution_percent': result['基础风险贡献度'],
                'dynamic_contribution_percent': result['动态调节贡献度'],
                'additional_contribution_percent': result['附加风险贡献度'],
                'main_contributor': result['主要贡献部分']
            }
            stats['companies'].append(company_stats)

        return stats
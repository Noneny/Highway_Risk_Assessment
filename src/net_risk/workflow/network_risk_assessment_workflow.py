"""
网络风险评估工作流
协调所有数据处理和风险计算模块，按照顺序执行完整评估流程
"""

import pandas as pd
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from src.db_config import get_belong_date

# 导入数据处理器
from ..data_processing.traffic_flow_processor import TrafficFlowProcessor
from ..data_processing.road_risk_processor import RoadRiskProcessor
from ..data_processing.event_data_processor import EventDataProcessor
from ..data_processing.data_merger import DataMerger

# 导入风险计算器
from ..risk_calculation.basic_risk_calculator import BasicRiskCalculator
from ..risk_calculation.dynamic_coefficient_calculator import DynamicCoefficientCalculator
from ..risk_calculation.additional_coefficient_calculator import AdditionalCoefficientCalculator
from ..risk_calculation.network_risk_calculator import NetworkRiskCalculator
from ..risk_calculation.risk_attribution_analyzer import RiskAttributionAnalyzer

# 导入数据库模块
from ..database.database_manager import DatabaseManager

# 导入输出模块
from ..output.excel_writer import ExcelWriter

# 导入配置管理器
from ..config.config_manager import ConfigManager


class NetworkRiskAssessmentWorkflow:
    """网络风险评估工作流类"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化工作流

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        print("\n" + "="*80)
        print("初始化网络风险评估工作流")
        print("="*80)

        # 初始化配置管理器
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_all_config()

        # 获取基础信息
        self.period = get_belong_date()
        self.road_base_info = self.config.get('road_base_info', {})

        # 初始化组件
        self.traffic_flow_processor = None
        self.road_risk_processor = None
        self.event_data_processor = None
        self.data_merger = None
        self.basic_risk_calculator = None
        self.dynamic_coefficient_calculator = None
        self.additional_coefficient_calculator = None
        self.network_risk_calculator = None
        self.risk_attribution_analyzer = None
        self.database_manager = None
        self.excel_writer = None  # 延迟初始化

        # 数据存储
        self.traffic_flow_data = None
        self.road_risk_data = None
        self.event_data = None
        self.merged_data = None
        self.basic_risk_results = None
        self.dynamic_coefficient_results = None
        self.additional_coefficient_results = None
        self.network_risk_results = None
        self.risk_attribution_results = None
        self.final_results = None

        print("工作流初始化完成")

    def run(self) -> bool:
        """
        执行完整风险评估流程

        Returns:
            bool: 流程执行是否成功
        """
        print("\n" + "="*80)
        print("开始执行网络风险评估流程")
        print("="*80)

        success = True

        try:
            # 步骤1: 加载和处理数据
            if not self._load_and_process_data():
                print("❌ 数据加载和处理失败")
                return False

            # 步骤2: 合并数据
            if not self._merge_data():
                print("❌ 数据合并失败")
                return False

            # 步骤3: 计算基础风险
            if not self._calculate_basic_risk():
                print("❌ 基础风险计算失败")
                return False

            # 步骤4: 计算动态系数
            if not self._calculate_dynamic_coefficient():
                print("❌ 动态系数计算失败")
                return False

            # 步骤5: 计算附加系数
            if not self._calculate_additional_coefficient():
                print("❌ 附加系数计算失败")
                return False

            # 步骤6: 计算网络风险
            if not self._calculate_network_risk():
                print("❌ 网络风险计算失败")
                return False

            # 步骤7: 风险归因分析
            if not self._perform_risk_attribution():
                print("❌ 风险归因分析失败")
                return False

            # 步骤8: 保存结果
            if not self._save_results():
                print("❌ 结果保存失败")
                success = False

            # 步骤9: 保存中间数据
            self._save_intermediate_data()

            print("\n" + "="*80)
            print("网络风险评估流程执行完成")
            print("="*80)

            return success

        except Exception as e:
            print(f"❌ 工作流执行异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _load_and_process_data(self) -> bool:
        """
        加载和处理所有输入数据

        Returns:
            bool: 数据加载是否成功
        """
        print("\n>> 步骤1: 加载和处理数据")

        try:
            # 获取文件路径
            paths_config = self.config.get('paths', {})
            traffic_flow_path = paths_config.get('traffic_flow_path', '')
            road_risk_path = paths_config.get('road_risk_path', '')
            event_data_path = paths_config.get('event_data_path', '')

            # 检查文件是否存在
            for path in [traffic_flow_path, road_risk_path, event_data_path]:
                if not os.path.exists(path):
                    print(f"❌ 文件不存在: {path}")
                    # 尝试在项目根目录下查找
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    full_path = os.path.join(project_root, path)
                    if not os.path.exists(full_path):
                        print(f"❌ 完整路径也不存在: {full_path}")
                        return False
                    else:
                        print(f"✅ 找到文件: {full_path}")

            # 1.1 处理门架流量数据
            print("\n  1.1 处理门架流量数据...")
            self.traffic_flow_processor = TrafficFlowProcessor(self.config_manager)
            self.traffic_flow_data = self.traffic_flow_processor.run_full_process(traffic_flow_path)

            if self.traffic_flow_data.empty:
                print("❌ 门架流量数据处理失败")
                return False

            print(f"    ✅ 处理完成，共 {len(self.traffic_flow_data)} 个路段")

            # 1.2 处理路段风险数据
            print("\n  1.2 处理路段风险数据...")
            self.road_risk_processor = RoadRiskProcessor(self.config_manager)
            self.road_risk_data = self.road_risk_processor.run_full_process(road_risk_path)

            if self.road_risk_data.empty:
                print("❌ 路段风险数据处理失败")
                return False

            print(f"    ✅ 处理完成，共 {len(self.road_risk_data)} 个路段")

            # 1.3 处理事件数据
            print("\n  1.3 处理事件数据...")
            self.event_data_processor = EventDataProcessor(self.config_manager)
            self.event_data = self.event_data_processor.run_full_process(event_data_path)

            if self.event_data.empty:
                print("⚠️  事件数据处理结果为空，可能影响附加系数计算")
                # 仍然继续，但使用空数据
                print("    将使用空事件数据进行后续计算")

            print(f"    ✅ 处理完成，共 {len(self.event_data)} 个事件")

            print("\n✅ 数据加载和处理完成")
            return True

        except Exception as e:
            print(f"❌ 数据加载和处理异常: {e}")
            return False

    def _merge_data(self) -> bool:
        """
        合并所有数据

        Returns:
            bool: 数据合并是否成功
        """
        print("\n>> 步骤2: 合并数据")

        try:
            self.data_merger = DataMerger(
                self.config_manager,
                self.traffic_flow_data,
                self.road_risk_data,
                self.event_data
            )

            self.merged_data = self.data_merger.merge_all_data()

            if self.merged_data.empty:
                print("❌ 数据合并失败，合并后数据为空")
                return False

            # 按路段通行风险评价总表的排序重新排列路段
            self.merged_data = self._sort_by_road_order(self.merged_data)

            print(f"✅ 数据合并完成，共 {len(self.merged_data)} 个路段")
            return True

        except Exception as e:
            print(f"❌ 数据合并异常: {e}")
            return False

    def _sort_by_road_order(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        按路段通行风险评价总表中的路段排序重新排列DataFrame

        Args:
            df: 待排序的DataFrame

        Returns:
            排序后的DataFrame
        """
        road_order = getattr(self.road_risk_processor, 'road_order', None) if self.road_risk_processor else None
        if not road_order or 'road_name' not in df.columns:
            return df

        # 使用Categorical确保pandas按指定顺序排序
        ordered = [r for r in road_order if r in df['road_name'].values]
        if ordered:
            df = df.copy()
            df['road_name'] = pd.Categorical(
                df['road_name'],
                categories=ordered,
                ordered=True
            )
            df = df.sort_values('road_name').reset_index(drop=True)
        return df

    def _calculate_basic_risk(self) -> bool:
        """
        计算基础风险

        Returns:
            bool: 基础风险计算是否成功
        """
        print("\n>> 步骤3: 计算基础风险")

        try:
            self.basic_risk_calculator = BasicRiskCalculator(self.config_manager)

            # 计算基础风险
            self.basic_risk_tuple = self.basic_risk_calculator.calculate_basic_risk(
                self.merged_data
            )

            if not self.basic_risk_tuple:
                print("❌ 基础风险计算结果为空")
                return False

            # 提取基础风险字典和风险组件字典
            self.basic_risk_results = self.basic_risk_tuple[0]  # 基础风险字典
            self.risk_components = self.basic_risk_tuple[1]     # 风险组件字典

            if not self.basic_risk_results:
                print("❌ 基础风险字典为空")
                return False

            print("✅ 基础风险计算完成")
            return True

        except Exception as e:
            print(f"❌ 基础风险计算异常: {e}")
            return False

    def _calculate_dynamic_coefficient(self) -> bool:
        """
        计算动态调节系数

        Returns:
            bool: 动态系数计算是否成功
        """
        print("\n>> 步骤4: 计算动态调节系数")

        try:
            self.dynamic_coefficient_calculator = DynamicCoefficientCalculator(self.config_manager)

            # 计算动态系数
            self.dynamic_coefficient_results = self.dynamic_coefficient_calculator.calculate_dynamic_coefficient(
                self.merged_data
            )

            if not self.dynamic_coefficient_results:
                print("❌ 动态调节系数计算结果为空")
                return False

            print("✅ 动态调节系数计算完成")
            return True

        except Exception as e:
            print(f"❌ 动态调节系数计算异常: {e}")
            return False

    def _calculate_additional_coefficient(self) -> bool:
        """
        计算附加风险修正系数

        Returns:
            bool: 附加系数计算是否成功
        """
        print("\n>> 步骤5: 计算附加风险修正系数")

        try:
            self.additional_coefficient_calculator = AdditionalCoefficientCalculator(
                self.config_manager,
                self.road_base_info
            )

            # 计算附加系数
            self.additional_coefficient_results = self.additional_coefficient_calculator.calculate_additional_coefficient(
                self.event_data
            )

            if not self.additional_coefficient_results:
                print("❌ 附加风险修正系数计算结果为空")
                return False

            print("✅ 附加风险修正系数计算完成")
            return True

        except Exception as e:
            print(f"❌ 附加风险修正系数计算异常: {e}")
            return False

    def _calculate_network_risk(self) -> bool:
        """
        计算网络风险

        Returns:
            bool: 网络风险计算是否成功
        """
        print("\n>> 步骤6: 计算网络风险")

        try:
            self.network_risk_calculator = NetworkRiskCalculator(self.config_manager)

            # 计算网络风险
            network_risk_dict, risk_levels_dict = self.network_risk_calculator.calculate_network_risk(
                self.basic_risk_results,
                self.dynamic_coefficient_results[0] if self.dynamic_coefficient_results else {},
                self.additional_coefficient_results[0] if self.additional_coefficient_results else {}
            )

            if not network_risk_dict or not risk_levels_dict:
                print("❌ 网络风险计算结果为空")
                return False

            # 将字典转换为DataFrame以便后续处理
            network_risk_df = pd.DataFrame([
                {
                    '路网划分': company,
                    '路网通行风险值': risk,
                    '风险等级': risk_levels_dict.get(company, '未知')
                }
                for company, risk in network_risk_dict.items()
            ])

            # 存储原始字典和DataFrame
            self.network_risk_dict = network_risk_dict
            self.risk_levels_dict = risk_levels_dict
            self.network_risk_results = network_risk_df

            print("✅ 网络风险计算完成")
            return True

        except Exception as e:
            print(f"❌ 网络风险计算异常: {e}")
            return False

    def _perform_risk_attribution(self) -> bool:
        """
        执行风险归因分析

        Returns:
            bool: 风险归因分析是否成功
        """
        print("\n>> 步骤7: 风险归因分析")

        try:
            self.risk_attribution_analyzer = RiskAttributionAnalyzer()

            # 执行风险归因分析
            self.risk_attribution_results = self.risk_attribution_analyzer.calculate_risk_attribution(
                self.basic_risk_results,
                self.dynamic_coefficient_results[0] if self.dynamic_coefficient_results else {},
                self.additional_coefficient_results[0] if self.additional_coefficient_results else {},
                self.network_risk_dict
            )

            if not self.risk_attribution_results:
                print("❌ 风险归因分析结果为空")
                return False

            print("✅ 风险归因分析完成")
            return True

        except Exception as e:
            print(f"❌ 风险归因分析异常: {e}")
            return False

    def _save_results(self) -> bool:
        """
        保存评估结果到Excel和数据库

        Returns:
            bool: 结果保存是否成功
        """
        print("\n>> 步骤8: 保存评估结果")

        success = True

        # 8.1 创建最终结果DataFrame
        try:
            self.final_results = self._create_final_results()
            if self.final_results.empty:
                print("❌ 最终结果为空")
                return False

            print(f"  创建最终结果：共 {len(self.final_results)} 条记录")

        except Exception as e:
            print(f"❌ 创建最终结果失败: {e}")
            success = False

        # 8.2 保存到Excel
        try:
            excel_saved = self._save_to_excel()
            if not excel_saved:
                print("⚠️  Excel保存失败")
                success = False
            else:
                print("✅ Excel保存成功")

        except Exception as e:
            print(f"❌ Excel保存异常: {e}")
            success = False

        # 8.3 保存到数据库
        try:
            db_saved = self._save_to_database()
            if not db_saved:
                print("⚠️  数据库保存失败或未启用")
                # 数据库保存失败不影响整体流程，但标记为部分成功
            else:
                print("✅ 数据库保存成功")

        except Exception as e:
            print(f"❌ 数据库保存异常: {e}")
            # 数据库异常不影响整体流程，但标记为部分成功

        return success

    def _create_final_results(self) -> pd.DataFrame:
        """
        创建最终结果DataFrame

        Returns:
            pd.DataFrame: 最终结果
        """
        print("  >> 创建最终结果DataFrame...")

        # 初始化最终结果DataFrame
        final_data = []
        companies = ['渝东公司', '东南公司', '东北公司', '示范路网']

        for company in companies:
            # 基础风险
            basic_risk = self.basic_risk_results.get(company, 0.0) if self.basic_risk_results else 0.0

            # 风险组件
            risk_components = self.risk_components.get(company) if hasattr(self, 'risk_components') and self.risk_components else None

            # 动态系数
            dynamic_coef = 1.0
            avg_saturation = 0.0
            equilibrium_coef = 0.0
            if self.dynamic_coefficient_results and len(self.dynamic_coefficient_results) >= 3:
                dynamic_coef = self.dynamic_coefficient_results[0].get(company, 1.0)
                avg_saturation = self.dynamic_coefficient_results[1].get(company, 0.0)
                equilibrium_coef = self.dynamic_coefficient_results[2].get(company, 0.0)

            # 附加系数
            additional_coef = 1.0
            arrival_rate = 0.0
            recovery_rate = 0.0
            if self.additional_coefficient_results and len(self.additional_coefficient_results) >= 2:
                additional_coef = self.additional_coefficient_results[0].get(company, 1.0)
                additional_stats = self.additional_coefficient_results[1].get(company, {})
                arrival_rate = additional_stats.get('J_rate', 0.0)
                recovery_rate = additional_stats.get('T_rate', 0.0)

            # 最终风险
            final_risk = 0.0
            risk_level = "未知"
            if hasattr(self, 'network_risk_dict'):
                final_risk = self.network_risk_dict.get(company, 0.0)
                risk_level = self.risk_levels_dict.get(company, "未知")

            # 添加一行数据
            row_data = {
                '路网划分': company,
                '路段通行风险综合值': round(risk_components.R, 2) if risk_components else 0.0,
                '路网密度通行风险值': round(risk_components.B, 2) if risk_components else 0.0,
                '路网连通度通行风险值': round(risk_components.C, 2) if risk_components else 0.0,
                '路网基础风险值': round(basic_risk, 2),
                '平均饱和度': round(avg_saturation, 2),
                '交通流均衡性系数': round(equilibrium_coef, 2),
                '动态调节系数': round(dynamic_coef, 4),
                '30分钟到达率': round(arrival_rate, 4),
                '1小时恢复通行率': round(recovery_rate, 4),
                '附加风险修正系数': round(additional_coef, 4),
                '路网通行风险值': round(final_risk, 2),
                '风险等级': risk_level
            }

            # 添加风险归因信息
            if self.risk_attribution_results:
                attribution = self.risk_attribution_results.get(company, {})
                row_data.update({
                    '基础风险贡献度(%)': round(attribution.get('基础风险贡献度', 0.0), 1),
                    '动态调节贡献度(%)': round(attribution.get('动态调节贡献度', 0.0), 1),
                    '附加风险贡献度(%)': round(attribution.get('附加风险贡献度', 0.0), 1),
                    '主要贡献部分': attribution.get('主要贡献部分', '未知')
                })

            final_data.append(row_data)

        # 创建DataFrame
        final_df = pd.DataFrame(final_data)

        # 按风险值降序排序
        if '路网通行风险值' in final_df.columns:
            final_df = final_df.sort_values('路网通行风险值', ascending=False)

        print(f"    创建完成，共 {len(final_df)} 条记录")
        return final_df

    def _save_to_excel(self) -> bool:
        """
        保存结果到Excel文件

        Returns:
            bool: 保存是否成功
        """
        try:
            # 初始化ExcelWriter
            if self.excel_writer is None:
                self.excel_writer = ExcelWriter(self.config_manager)

            # 构造基础风险中间数据
            basic_risk_data = {}
            if self.basic_risk_calculator:
                basic_risk_df = self.basic_risk_calculator.get_company_risk_summary()
                if not basic_risk_df.empty:
                    basic_risk_data['basic_risk_df'] = basic_risk_df

            # 使用ExcelWriter保存完整评估结果
            excel_path = self.excel_writer.save_assessment_results(
                final_results_df=self.final_results,
                basic_risk_results=basic_risk_data,
                dynamic_coefficient_results=self.dynamic_coefficient_results,
                additional_coefficient_results=self.additional_coefficient_results,
                network_risk_results=self.network_risk_results,
                risk_attribution_results=self.risk_attribution_results
            )

            print(f"  结果已保存到: {excel_path}")
            return True

        except Exception as e:
            print(f"❌ 保存到Excel失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_to_database(self) -> bool:
        """
        保存结果到数据库

        Returns:
            bool: 保存是否成功
        """
        try:
            # 初始化数据库管理器
            self.database_manager = DatabaseManager(self.config_manager, self.period)

            # 初始化数据库连接
            if not self.database_manager.initialize_database():
                print("⚠️  数据库初始化失败")
                return False

            # 保存结果
            if self.database_manager.save_assessment_results(self.final_results):
                print("✅ 数据库保存成功")
                return True
            else:
                print("⚠️  数据库保存失败")
                return False

        except Exception as e:
            print(f"❌ 数据库保存异常: {e}")
            return False

    def _save_intermediate_data(self):
        """
        保存中间计算数据
        """
        try:
            # 获取配置
            paths_config = self.config.get('paths', {})
            save_intermediate = paths_config.get('save_intermediate_data', 'False').lower() == 'true'
            output_dir = paths_config.get('output_dir', 'data/output')
            intermediate_filename = paths_config.get('intermediate_filename', '中间计算数据')

            if not save_intermediate:
                print("\n>> 跳过中间数据保存（配置中已禁用）")
                return

            print("\n>> 步骤9: 保存中间计算数据")

            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 保存合并数据
            if self.merged_data is not None and not self.merged_data.empty:
                merged_path = os.path.join(output_dir, f"{intermediate_filename}_合并数据_{timestamp}.xlsx")
                merged_df = self.excel_writer._rename_columns_to_chinese(self.merged_data.copy()) if self.excel_writer else self.merged_data
                merged_df.to_excel(merged_path, index=False)
                print(f"  合并数据已保存到: {merged_path}")

            # 保存各阶段结果（可选）
            # ...

            print("✅ 中间数据保存完成")

        except Exception as e:
            print(f"⚠️  中间数据保存失败: {e}")

    def get_results(self) -> Dict[str, Any]:
        """
        获取所有计算结果

        Returns:
            Dict[str, Any]: 包含所有结果的字典
        """
        return {
            'traffic_flow_data': self.traffic_flow_data,
            'road_risk_data': self.road_risk_data,
            'event_data': self.event_data,
            'merged_data': self.merged_data,
            'basic_risk_results': self.basic_risk_results,
            'dynamic_coefficient_results': self.dynamic_coefficient_results,
            'additional_coefficient_results': self.additional_coefficient_results,
            'network_risk_results': self.network_risk_results,
            'risk_attribution_results': self.risk_attribution_results,
            'final_results': self.final_results
        }

    def print_summary(self):
        """打印执行摘要"""
        print("\n" + "="*80)
        print("执行摘要")
        print("="*80)

        if self.traffic_flow_data is not None:
            print(f"• 门架流量数据: {len(self.traffic_flow_data)} 个路段")

        if self.road_risk_data is not None:
            print(f"• 路段风险数据: {len(self.road_risk_data)} 个路段")

        if self.event_data is not None:
            print(f"• 事件数据: {len(self.event_data)} 个事件")

        if self.merged_data is not None:
            print(f"• 合并数据: {len(self.merged_data)} 个路段")

        if self.final_results is not None:
            print(f"• 最终结果: {len(self.final_results)} 个路网评估结果")

        # 打印风险统计
        if self.network_risk_results is not None and not self.network_risk_results.empty:
            print("\n• 风险评估统计:")
            if '风险等级' in self.network_risk_results.columns:
                risk_counts = self.network_risk_results['风险等级'].value_counts()
                for level, count in risk_counts.items():
                    print(f"  - {level}: {count} 个路网")

        print("="*80)


def main():
    """主函数"""
    print("\n" + "="*80)
    print("高速公路路网通行风险评估系统")
    print("版本: 1.0.0 (重构版)")
    print("="*80)

    # 使用默认配置文件
    workflow = NetworkRiskAssessmentWorkflow()

    # 执行完整流程
    success = workflow.run()

    if success:
        print("\n✅ 评估流程执行成功")
        workflow.print_summary()
    else:
        print("\n❌ 评估流程执行失败")

    return success


if __name__ == "__main__":
    main()
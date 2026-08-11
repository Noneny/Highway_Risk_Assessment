"""
风险评估工作流
协调所有数据处理和风险计算模块，实现完整的风险评估流程
对应原项目中的 [0]start.py 脚本
"""

import time
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from ..config.config_manager import get_config_manager
from ..database.database_connector import create_database_connector_from_config
from ..data_processing.structure_processor import StructureDataProcessor
from ..data_processing.weather_processor import WeatherDataProcessor
from ..data_processing.traffic_processor import TrafficDataProcessor
from ..data_processing.roadname_processor import RoadNameProcessor
from ..risk_calculation.risk_calculator import RiskCalculator


class RiskAssessmentWorkflow:
    """风险评估工作流类"""

    def __init__(self, config_path: str = None):
        """
        初始化工作流

        Args:
            config_path: 配置文件路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()
        self.db_connector = create_database_connector_from_config(self.config_manager)

        # 初始化处理器
        self.structure_processor = StructureDataProcessor()
        self.weather_processor = WeatherDataProcessor()
        self.traffic_processor = TrafficDataProcessor()
        self.roadname_processor = RoadNameProcessor()
        self.risk_calculator = RiskCalculator()

        # 状态跟踪
        self.execution_status = {
            'structure_processing': False,
            'weather_processing': False,
            'traffic_processing': False,
            'roadname_processing': False,
            'risk_calculation': False,
            'database_save': False
        }

    def log_step(self, step_name: str, message: str):
        """
        记录步骤日志

        Args:
            step_name: 步骤名称
            message: 日志消息
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"\n{'='*80}")
        print(f"[{timestamp}] 步骤: {step_name}")
        print(f"{message}")
        print(f"{'='*80}")

    def execute_structure_processing(self) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        执行结构点数据处理

        Returns:
            (是否成功, 处理结果DataFrame)
        """
        self.log_step("结构点数据处理", "开始处理结构物监测基础信息...")

        try:
            result_df = self.structure_processor.process_pipeline()
            self.execution_status['structure_processing'] = True
            return True, result_df
        except Exception as e:
            print(f"❌ 结构点数据处理失败: {e}")
            return False, None

    def execute_weather_processing(self) -> Tuple[bool, Optional[Tuple[pd.DataFrame, pd.DataFrame]]]:
        """
        执行气象预警数据处理

        Returns:
            (是否成功, (预警统计DataFrame, 更新后的风险DataFrame))
        """
        self.log_step("气象预警数据处理", "开始处理气象预警数据...")

        try:
            warning_stats, updated_risk = self.weather_processor.process_pipeline()
            self.execution_status['weather_processing'] = True
            return True, (warning_stats, updated_risk)
        except Exception as e:
            print(f"❌ 气象预警数据处理失败: {e}")
            return False, None

    def execute_traffic_processing(self) -> Tuple[bool, Optional[Tuple[pd.DataFrame, pd.DataFrame]]]:
        """
        执行流量数据处理

        Returns:
            (是否成功, (门架风险评估DataFrame, 更新后的结构点风险DataFrame))
        """
        self.log_step("流量数据处理", "开始处理门架流量数据...")

        try:
            traffic_risk, updated_structure_risk = self.traffic_processor.process_pipeline()
            self.execution_status['traffic_processing'] = True
            return True, (traffic_risk, updated_structure_risk)
        except Exception as e:
            print(f"❌ 流量数据处理失败: {e}")
            return False, None

    def execute_roadname_processing(self) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        执行道路名称处理

        Returns:
            (是否成功, 处理结果DataFrame)
        """
        self.log_step("道路名称处理", "开始补充门架信息...")

        try:
            success, result_df = self.roadname_processor.process_pipeline()
            self.execution_status['roadname_processing'] = success
            return success, result_df
        except Exception as e:
            print(f"❌ 道路名称处理失败: {e}")
            return False, None

    def execute_risk_calculation(self) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        执行风险计算

        Returns:
            (是否成功, 最终风险评价DataFrame)
        """
        self.log_step("风险等级计算", "开始计算风险等级...")

        try:
            final_result = self.risk_calculator.process_pipeline()
            self.execution_status['risk_calculation'] = True
            return True, final_result
        except Exception as e:
            print(f"❌ 风险等级计算失败: {e}")
            return False, None

    def execute_full_workflow(self) -> bool:
        """
        执行完整的工作流

        Returns:
            工作流是否成功执行
        """
        print("\n" + "="*100)
        print("开始执行高速公路风险结构点风险评估工作流")
        print("="*100)

        start_time = time.time()

        try:
            # 步骤1: 结构点数据处理
            success1, _ = self.execute_structure_processing()
            if not success1:
                print("❌ 工作流在结构点数据处理步骤中断")
                return False

            time.sleep(1)  # 短暂延迟

            # 步骤2: 气象预警数据处理
            success2, _ = self.execute_weather_processing()
            if not success2:
                print("❌ 工作流在气象预警数据处理步骤中断")
                return False

            time.sleep(1)

            # 步骤3: 流量数据处理
            success3, _ = self.execute_traffic_processing()
            if not success3:
                print("❌ 工作流在流量数据处理步骤中断")
                return False

            time.sleep(1)

            # 步骤4: 道路名称处理
            success4, _ = self.execute_roadname_processing()
            if not success4:
                print("❌ 工作流在道路名称处理步骤中断")
                return False

            time.sleep(1)

            # 步骤5: 风险计算
            success5, final_result = self.execute_risk_calculation()
            if not success5:
                print("❌ 工作流在风险计算步骤中断")
                return False

            # 更新数据库保存状态
            if self.db_connector and self.db_connector.connection:
                self.execution_status['database_save'] = True

            # 计算执行时间
            end_time = time.time()
            execution_time = end_time - start_time

            # 输出执行摘要
            self._print_execution_summary(final_result, execution_time)

            return True

        except KeyboardInterrupt:
            print("\n⚠️  用户中断了工作流执行")
            return False
        except Exception as e:
            print(f"\n❌ 工作流执行过程中发生未知错误: {e}")
            return False

    def _print_execution_summary(self, final_result: pd.DataFrame, execution_time: float):
        """打印执行摘要"""
        print("\n" + "="*100)
        print("工作流执行摘要")
        print("="*100)

        # 执行状态
        print("\n执行状态:")
        for step, status in self.execution_status.items():
            status_symbol = "✅" if status else "❌"
            step_name = {
                'structure_processing': '结构点数据处理',
                'weather_processing': '气象预警数据处理',
                'traffic_processing': '流量数据处理',
                'roadname_processing': '道路名称处理',
                'risk_calculation': '风险等级计算',
                'database_save': '数据库保存'
            }.get(step, step)
            print(f"  {status_symbol} {step_name}")

        # 结果统计
        if final_result is not None and not final_result.empty:
            print(f"\n结果统计:")
            print(f"  处理的结构点总数: {len(final_result)}")

            if '风险等级' in final_result.columns:
                risk_distribution = final_result['风险等级'].value_counts()
                print(f"\n  风险等级分布:")
                for level, count in risk_distribution.items():
                    percentage = count / len(final_result) * 100
                    print(f"    {level}: {count}个点 ({percentage:.1f}%)")

            # 高风险点统计
            high_risk_points = final_result[
                final_result['风险等级'].isin(['较高风险', '高风险'])
                ] if '风险等级' in final_result.columns else pd.DataFrame()

            if not high_risk_points.empty:
                print(f"\n  高风险点统计:")
                print(f"    较高风险/高风险点总数: {len(high_risk_points)}")

                if '所属路段' in high_risk_points.columns:
                    road_distribution = high_risk_points['所属路段'].value_counts().head(5)
                    print(f"    高风险点最多的前5个路段:")
                    for road, count in road_distribution.items():
                        print(f"      {road}: {count}个点")

        # 执行时间
        print(f"\n执行时间: {execution_time:.2f}秒 ({execution_time/60:.2f}分钟)")

        # 配置信息
        print(f"\n配置信息:")
        print(f"  数据库: {'已启用' if self.config['database']['enable'] else '未启用'}")
        if self.config['database']['enable']:
            print(f"  数据库连接: {self.config['database']['host']}:{self.config['database']['port']}/{self.config['database']['database']}")

        print("\n" + "="*100)
        print("工作流执行完成!")
        print("="*100)

    def execute_step(self, step_name: str) -> bool:
        """
        执行单个步骤

        Args:
            step_name: 步骤名称 ('structure', 'weather', 'traffic', 'roadname', 'risk')

        Returns:
            是否执行成功
        """
        if step_name == 'structure':
            success, _ = self.execute_structure_processing()
            return success
        elif step_name == 'weather':
            success, _ = self.execute_weather_processing()
            return success
        elif step_name == 'traffic':
            success, _ = self.execute_traffic_processing()
            return success
        elif step_name == 'roadname':
            success, _ = self.execute_roadname_processing()
            return success
        elif step_name == 'risk':
            success, _ = self.execute_risk_calculation()
            return success
        else:
            print(f"❌ 未知的步骤名称: {step_name}")
            print("可用步骤: 'structure', 'weather', 'traffic', 'roadname', 'risk'")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取工作流状态

        Returns:
            状态字典
        """
        return {
            'execution_status': self.execution_status,
            'config': {
                'database_enabled': self.config['database']['enable'],
                'paths': list(self.config['paths'].keys())[:5]  # 只显示前5个路径
            }
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='高速公路风险结构点风险评估系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python main.py                     # 执行完整工作流
  python main.py --step structure    # 仅执行结构点数据处理
  python main.py --step weather      # 仅执行气象预警数据处理
  python main.py --step traffic      # 仅执行流量数据处理
  python main.py --step roadname     # 仅执行道路名称处理
  python main.py --step risk         # 仅执行风险计算
  python main.py --config custom.ini # 使用自定义配置文件
        '''
    )

    parser.add_argument('--config', type=str, default=None,
                       help='配置文件路径 (默认: config/config.ini)')
    parser.add_argument('--step', type=str, choices=['structure', 'weather', 'traffic', 'roadname', 'risk'],
                       help='执行单个步骤')

    args = parser.parse_args()

    # 创建工作流实例
    workflow = RiskAssessmentWorkflow(args.config)

    if args.step:
        # 执行单个步骤
        print(f"\n执行单个步骤: {args.step}")
        success = workflow.execute_step(args.step)
        if success:
            print(f"\n✅ 步骤 '{args.step}' 执行成功")
        else:
            print(f"\n❌ 步骤 '{args.step}' 执行失败")
    else:
        # 执行完整工作流
        success = workflow.execute_full_workflow()
        if success:
            print("\n🎉 完整工作流执行成功!")
        else:
            print("\n⚠️  工作流执行失败，请检查错误信息")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
高速公路路段风险评估系统 - 主程序入口
重构版本：面向对象设计，模块化架构
"""

import argparse
import sys
import os
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
from src.line_risk.workflow.line_risk_workflow import LineRiskWorkflow
from src.line_risk.data_processing.base_risk_processor import BaseRiskProcessor
from src.line_risk.data_processing.dynamic_risk_processor import DynamicRiskProcessor
from src.line_risk.data_processing.extra_risk_processor import ExtraRiskProcessor
from src.line_risk.risk_calculation.risk_calculator import RiskCalculator
from src.line_risk.database.database_connector import DatabaseConnector
from src.line_risk.config.config_manager import get_config_manager, DEFAULT_CONFIG_PATH

warnings.filterwarnings('ignore')


def print_banner():
    """打印程序横幅"""
    banner = """
==========================================
      山区高速公路通行风险评价系统
==========================================
    """
    print(banner)


def run_full_workflow(config_path: str) -> bool:
    """
    运行完整的工作流程

    Args:
        config_path: 配置文件路径

    Returns:
        是否成功运行
    """
    print(">>> 开始完整工作流程...")

    try:
        workflow = LineRiskWorkflow(config_path)
        success = workflow.run()
        return success

    except Exception as e:
        print(f"❌ 完整工作流程执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_single_module(module_name: str, config_path: str, **kwargs) -> bool:
    """
    运行单个模块

    Args:
        module_name: 模块名称
        config_path: 配置文件路径
        **kwargs: 模块特定参数

    Returns:
        是否成功运行
    """
    print(f">>> 开始运行 {module_name} 模块...")

    # 导入pandas
    import pandas as pd

    try:
        if module_name == 'base_risk':
            # 基础风险计算
            points_file = kwargs.get('points_file')
            template_file = kwargs.get('template_file')
            current_month = kwargs.get('current_month')

            if not all([points_file, template_file, current_month]):
                print("❌ 缺少必要参数: points_file, template_file, current_month")
                return False

            processor = BaseRiskProcessor(config_path)

            # 加载数据
            df_points = pd.read_excel(points_file)
            df_template = pd.read_excel(template_file)

            # 运行计算
            result = processor.run(df_points, df_template, current_month)

            if result is not None:
                output_file = kwargs.get('output_file', 'base_risk_result.xlsx')
                result.to_excel(output_file, index=False)
                print(f"✅ 基础风险计算完成，结果保存到: {output_file}")
                return True
            else:
                print("❌ 基础风险计算失败")
                return False

        elif module_name == 'dynamic_risk':
            # 动态风险计算
            etc_dir = kwargs.get('etc_dir')
            gantry_file = kwargs.get('gantry_file')
            template_file = kwargs.get('template_file')
            weather_file = kwargs.get('weather_file')
            start_date = kwargs.get('start_date')
            end_date = kwargs.get('end_date')

            if not all([etc_dir, gantry_file, template_file, weather_file, start_date, end_date]):
                print("❌ 缺少必要参数: etc_dir, gantry_file, template_file, weather_file, start_date, end_date")
                return False

            processor = DynamicRiskProcessor(config_path)

            # 运行计算
            result = processor.run(etc_dir, gantry_file, template_file, weather_file, start_date, end_date)

            if result is not None:
                output_file = kwargs.get('output_file', 'dynamic_risk_result.xlsx')
                result.to_excel(output_file, index=False)
                print(f"✅ 动态风险计算完成，结果保存到: {output_file}")
                return True
            else:
                print("❌ 动态风险计算失败")
                return False

        elif module_name == 'extra_risk':
            # 附加风险计算
            accident_file = kwargs.get('accident_file')
            template_file = kwargs.get('template_file')

            if not all([accident_file, template_file]):
                print("❌ 缺少必要参数: accident_file, template_file")
                return False

            processor = ExtraRiskProcessor(config_path)

            # 运行计算
            result = processor.run(accident_file, template_file)

            if result is not None:
                output_file = kwargs.get('output_file', 'extra_risk_result.xlsx')
                result.to_excel(output_file, index=False)
                print(f"✅ 附加风险计算完成，结果保存到: {output_file}")
                return True
            else:
                print("❌ 附加风险计算失败")
                return False

        elif module_name == 'risk_assessment':
            # 最终风险评估
            base_file = kwargs.get('base_file')
            dynamic_file = kwargs.get('dynamic_file')
            extra_file = kwargs.get('extra_file')

            if not all([base_file, dynamic_file, extra_file]):
                print("❌ 缺少必要参数: base_file, dynamic_file, extra_file")
                return False

            calculator = RiskCalculator(config_path)

            # 加载数据
            import pandas as pd
            df_base = pd.read_excel(base_file)
            df_dyn = pd.read_excel(dynamic_file)
            df_extra = pd.read_excel(extra_file)

            # 运行计算
            result = calculator.calculate_final_risk(df_base, df_dyn, df_extra)

            if result is not None:
                output_file = kwargs.get('output_file', 'final_assessment.xlsx')
                result = calculator.format_output_columns(result)
                result.to_excel(output_file, index=False)
                calculator.generate_statistics(result)
                print(f"✅ 最终风险评估完成，结果保存到: {output_file}")
                return True
            else:
                print("❌ 最终风险评估失败")
                return False

        elif module_name == 'database':
            # 数据库操作
            result_file = kwargs.get('result_file')
            belong_date = kwargs.get('belong_date', datetime.now().strftime('%Y-%m-%d'))

            if not result_file:
                print("❌ 缺少必要参数: result_file")
                return False

            connector = DatabaseConnector(config_path)

            if connector.is_enabled():
                # 连接到数据库
                connected = connector.connect()
                if connected:
                    # 创建表
                    table_created = connector.create_table_if_not_exists(belong_date)

                    if table_created:
                        # 加载结果数据
                        import pandas as pd
                        df_result = pd.read_excel(result_file)

                        # 保存到数据库
                        success = connector.save_results(df_result, belong_date)
                        connector.disconnect()

                        if success:
                            print(f"✅ 数据库操作完成")
                            return True
                        else:
                            print("❌ 数据库保存失败")
                            return False
                    else:
                        print("❌ 表创建失败")
                        connector.disconnect()
                        return False
                else:
                    print("❌ 数据库连接失败")
                    return False
            else:
                print("⚠️  数据库功能未启用")
                return False

        else:
            print(f"❌ 未知模块: {module_name}")
            return False

    except Exception as e:
        print(f"❌ {module_name} 模块执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_config_info(config_path: str):
    """显示配置信息"""
    try:
        config_manager = get_config_manager(config_path)
        all_config = config_manager.get_all_config()

        print("\n当前配置信息:")
        print("=" * 50)

        for section, config_dict in all_config.items():
            print(f"\n[{section.upper()}]")
            for key, value in config_dict.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for subkey, subvalue in value.items():
                        print(f"    {subkey}: {subvalue}")
                elif isinstance(value, list):
                    print(f"  {key}: {', '.join(map(str, value))}")
                else:
                    print(f"  {key}: {value}")

        print("\n" + "=" * 50)

    except Exception as e:
        print(f"❌ 读取配置信息失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='山区高速公路通行风险评价系统 - 重构版本',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 基本参数
    parser.add_argument(
        '--config', '-c',
        default=DEFAULT_CONFIG_PATH,
        help=f'配置文件路径 (默认: {DEFAULT_CONFIG_PATH})'
    )

    # 运行模式
    parser.add_argument(
        '--mode', '-m',
        choices=['full', 'module', 'config'],
        default='full',
        help='运行模式: full(完整流程), module(单个模块), config(查看配置)'
    )

    # 模块参数 (当 mode=module 时使用)
    parser.add_argument(
        '--module', '-M',
        choices=['base_risk', 'dynamic_risk', 'extra_risk', 'risk_assessment', 'database'],
        help='要运行的模块名称'
    )

    # 模块特定参数
    parser.add_argument(
        '--points-file',
        help='结构点数据文件 (base_risk 模块使用)'
    )
    parser.add_argument(
        '--template-file',
        help='模板数据文件 (多个模块使用)'
    )
    parser.add_argument(
        '--gantry-file',
        help='门架数据文件 (dynamic_risk 模块使用)'
    )
    parser.add_argument(
        '--weather-file',
        help='气象预警文件 (dynamic_risk 模块使用)'
    )
    parser.add_argument(
        '--accident-file',
        help='事故数据文件 (extra_risk 模块使用)'
    )
    parser.add_argument(
        '--etc-dir',
        help='ETC数据目录 (dynamic_risk 模块使用)'
    )
    parser.add_argument(
        '--base-file',
        help='基础风险结果文件 (risk_assessment 模块使用)'
    )
    parser.add_argument(
        '--dynamic-file',
        help='动态风险结果文件 (risk_assessment 模块使用)'
    )
    parser.add_argument(
        '--extra-file',
        help='附加风险结果文件 (risk_assessment 模块使用)'
    )
    parser.add_argument(
        '--result-file',
        help='最终结果文件 (database 模块使用)'
    )
    parser.add_argument(
        '--start-date',
        default='2025-12-01',
        help='评估开始日期 (默认: 2025-12-01)'
    )
    parser.add_argument(
        '--end-date',
        default='2026-01-31',
        help='评估结束日期 (默认: 2026-01-31)'
    )
    parser.add_argument(
        '--current-month',
        type=int,
        help='当前月份 (1-12)，如未指定则根据 end_date 自动计算'
    )
    parser.add_argument(
        '--belong-date',
        help='数据归属日期，用于数据库存储'
    )
    parser.add_argument(
        '--output-file', '-o',
        help='输出文件路径'
    )

    # 其他选项
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细输出'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='运行测试模式'
    )

    args = parser.parse_args()

    # 打印横幅
    print_banner()

    # 检查配置文件是否存在
    if not os.path.exists(args.config):
        print(f"⚠️  配置文件不存在: {args.config}")
        print("正在创建默认配置文件...")
        config_manager = get_config_manager(args.config)
        print(f"✅ 默认配置文件已创建: {args.config}")

    # 测试模式
    if args.test:
        print(">>> 运行测试模式...")
        # 这里可以添加测试代码
        return

    # 根据模式执行
    if args.mode == 'config':
        # 显示配置信息
        show_config_info(args.config)
        return

    elif args.mode == 'module':
        # 运行单个模块
        if not args.module:
            print("❌ 请使用 --module 参数指定要运行的模块")
            parser.print_help()
            return

        # 准备模块参数
        module_kwargs = {}

        # 收集模块特定参数
        if args.points_file:
            module_kwargs['points_file'] = args.points_file
        if args.template_file:
            module_kwargs['template_file'] = args.template_file
        if args.gantry_file:
            module_kwargs['gantry_file'] = args.gantry_file
        if args.weather_file:
            module_kwargs['weather_file'] = args.weather_file
        if args.accident_file:
            module_kwargs['accident_file'] = args.accident_file
        if args.etc_dir:
            module_kwargs['etc_dir'] = args.etc_dir
        if args.base_file:
            module_kwargs['base_file'] = args.base_file
        if args.dynamic_file:
            module_kwargs['dynamic_file'] = args.dynamic_file
        if args.extra_file:
            module_kwargs['extra_file'] = args.extra_file
        if args.result_file:
            module_kwargs['result_file'] = args.result_file
        if args.start_date:
            module_kwargs['start_date'] = args.start_date
        if args.end_date:
            module_kwargs['end_date'] = args.end_date
        if args.current_month:
            module_kwargs['current_month'] = args.current_month
        elif args.end_date:
            # 自动计算月份
            try:
                import pandas as pd
                end_date = pd.to_datetime(args.end_date)
                module_kwargs['current_month'] = end_date.month
                print(f"自动计算月份: {module_kwargs['current_month']}月")
            except:
                print("⚠️  无法自动计算月份，请使用 --current-month 参数指定")
        if args.belong_date:
            module_kwargs['belong_date'] = args.belong_date
        if args.output_file:
            module_kwargs['output_file'] = args.output_file

        # 导入pandas用于单个模块
        import pandas as pd

        # 运行模块
        success = run_single_module(args.module, args.config, **module_kwargs)

        if success:
            print(f"\n✅ {args.module} 模块执行成功!")
        else:
            print(f"\n❌ {args.module} 模块执行失败!")
            sys.exit(1)

    else:
        # 运行完整工作流程
        success = run_full_workflow(args.config)

        if success:
            print("\n✅ 完整工作流程执行成功!")
        else:
            print("\n❌ 完整工作流程执行失败!")
            sys.exit(1)


if __name__ == "__main__":
    main()
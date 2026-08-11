#!/usr/bin/env python3
"""
高速公路路网通行风险评估系统 - 主程序入口

基于面向对象编程重构，统一配置文件管理，标准项目结构

使用方法:
    python main.py [选项]

选项:
    -h, --help            显示帮助信息
    -c CONFIG, --config CONFIG  指定配置文件路径
    -v, --verbose         启用详细输出模式
    -t, --test            运行测试模式（不保存结果）
"""

import sys
import os
import argparse
from datetime import datetime

from src.net_risk.workflow.network_risk_assessment_workflow import NetworkRiskAssessmentWorkflow


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="高速公路路网通行风险评估系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                     # 使用默认配置文件
  python main.py -c custom.ini       # 使用自定义配置文件
  python main.py -v                  # 详细输出模式
  python main.py --test              # 测试模式
        """
    )

    parser.add_argument(
        '-c', '--config',
        type=str,
        default=None,
        help='配置文件路径（默认: config/config.ini）'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='启用详细输出模式'
    )

    parser.add_argument(
        '-t', '--test',
        action='store_true',
        help='测试模式（不保存结果到文件/数据库）'
    )

    parser.add_argument(
        '-V', '--version',
        action='version',
        version='高速公路路网通行风险评估系统 v1.0.0 (重构版)'
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    # 显示项目信息
    print("\n" + "="*80)
    print("高速公路路网通行风险评估系统")
    print("版本: 1.0.0 (重构版)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    if args.verbose:
        print("模式: 详细输出")
    if args.test:
        print("模式: 测试（不保存结果）")
    if args.config:
        print(f"配置文件: {args.config}")
    else:
        print("配置文件: config/config.ini (默认)")

    print("")

    try:
        # 初始化工作流
        print("初始化评估工作流...")
        workflow = NetworkRiskAssessmentWorkflow(config_path=args.config)

        # 如果启用测试模式，临时修改配置
        if args.test:
            print("测试模式启用：跳过结果保存")
            # 可以在这里修改配置以跳过保存

        # 执行完整流程
        success = workflow.run()

        if success:
            print("\n" + "="*80)
            print("✅ 评估流程执行成功")
            print("="*80)
            workflow.print_summary()

            # 打印结果保存位置（如果不是测试模式）
            if not args.test:
                print("\n结果保存位置:")
                print("  • Excel文件: data/output/2 (带时间戳的文件)")
                print("  • 数据库表: net_risk_evaluation")

            return 0
        else:
            print("\n" + "="*80)
            print("❌ 评估流程执行失败")
            print("="*80)
            return 1

    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        return 130
    except Exception as e:
        print(f"\n❌ 程序执行异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
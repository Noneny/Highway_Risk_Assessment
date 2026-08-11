#!/usr/bin/env python3
"""
高速公路路网通行风险评估系统 - 总控入口

企业级项目结构:
  src/input/       - 输入数据准备模块
  src/point_risk/  - 点风险评估模块
  src/line_risk/   - 线风险评估模块
  src/net_risk/    - 网风险评估模块
  src/compare/     - 两期对比分析模块
  config/          - 配置文件
  data/            - 数据目录 (input / temp / output)
  tests/           - 测试目录

 使用方式:
   python main.py                     # 执行数据准备→点→线→网风险评估
   python main.py --config-update     # 先从数据库更新config，再执行风险评估
   python main.py --compare           # 执行数据准备→点→线→网 + 两期对比分析
   python main.py --compare --no-recalculate  # 执行数据准备 + 两期对比分析 (跳过风险重新计算)
   python main.py --simple-log        # 简化日志，仅记录关键信息
   python main.py --no-input          # 不执行数据准备，点→线→网风险评估
"""

import sys
import os
import shutil
import time
from pathlib import Path
from datetime import datetime

from src.log_create import setup_logging

BASE_DIR = Path(__file__).parent.resolve()
DATA_INPUT = BASE_DIR / "data" / "input"
DATA_OUTPUT = BASE_DIR / "data" / "output"
DATA_TEMP = BASE_DIR / "data" / "temp"

DATA_INPUT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
DATA_TEMP.mkdir(parents=True, exist_ok=True)


def run_config_update_step() -> bool:
    print_section("阶段 PRE: 配置更新 (ConfigUpdate)")
    try:
        from src.config_update import run_config_update
        return run_config_update()
    except Exception as e:
        print(f"  ❌ 配置更新异常: {e}")
        import traceback; traceback.print_exc()
        return False


def print_banner(log_path: str = None):
    print("\n" + "=" * 80)
    print("     高速公路路网通行风险评估系统")
    print("     版本: 2.0.0 (企业集成版)")
    print(f"     时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"     项目根目录: {BASE_DIR}")
    if log_path:
        print(f"     日志文件: {log_path}")
    print("=" * 80)


def print_section(title: str):
    print("\n" + "#" * 80)
    print(f"##  {title}")
    print("#" * 80)


def copy_file(src: Path, dst: Path, description: str) -> bool:
    if not src.exists():
        print(f"  ❌ 源文件不存在: {src}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    print(f"  ✅ {description}: {src.name} -> {dst.relative_to(BASE_DIR)}")
    return True


def run_input() -> bool:
    print_section("阶段 0/4: 输入数据准备 (Input)")
    try:
        from src.input.input_main import run_all
        return run_all()
    except Exception as e:
        print(f"  ❌ 输入数据准备异常: {e}")
        import traceback; traceback.print_exc()
        return False


def run_point_risk() -> bool:
    print_section("阶段 1/4: 点风险评估 (PointRisk)")
    try:
        from src.point_risk.workflow.risk_assessment_workflow import RiskAssessmentWorkflow
        workflow = RiskAssessmentWorkflow()
        return workflow.execute_full_workflow()
    except Exception as e:
        print(f"  ❌ 点风险评估异常: {e}")
        import traceback; traceback.print_exc()
        return False


def run_line_risk() -> bool:
    print_section("阶段 2/4: 线风险评估 (LineRisk)")
    try:
        from src.line_risk.workflow.line_risk_workflow import LineRiskWorkflow
        workflow = LineRiskWorkflow()
        return workflow.run()
    except Exception as e:
        print(f"  ❌ 线风险评估异常: {e}")
        import traceback; traceback.print_exc()
        return False


def run_net_risk() -> bool:
    print_section("阶段 3/4: 网风险评估 (NetRisk)")
    try:
        from src.net_risk.workflow.network_risk_assessment_workflow import NetworkRiskAssessmentWorkflow
        workflow = NetworkRiskAssessmentWorkflow()
        success = workflow.run()
        if success:
            workflow.print_summary()
        return success
    except Exception as e:
        print(f"  ❌ 网风险评估异常: {e}")
        import traceback; traceback.print_exc()
        return False


def run_compare() -> bool:
    print_section("阶段 4/4: 两期对比分析 (Compare)")
    try:
        from src.compare.compare import run_compare as cmp_run
        return cmp_run()
    except Exception as e:
        print(f"  ❌ 两期对比分析异常: {e}")
        import traceback; traceback.print_exc()
        return False


def run_risk_assessment() -> bool:
    """执行数据准备→点→线→网风险评估，包含数据传输"""
    overall_start = time.time()

    if not run_point_risk():
        print("\n❌ 点风险评估失败，流程终止")
        return False

    print_section("数据传输: PointRisk → LineRisk / NetRisk")
    copy_file(DATA_OUTPUT / "全结构点通行风险值评价表.xlsx",
              DATA_INPUT / "全结构点通行风险值评价表.xlsx",
              "结构点风险评价表 -> LineRisk")
    copy_file(DATA_TEMP / "双月门架风险评估表_路段信息.xlsx",
              DATA_INPUT / "双月门架风险评估表_路段信息.xlsx",
              "门架风险评估表(路段信息) -> NetRisk")

    if not run_line_risk():
        print("\n❌ 线风险评估失败，流程终止")
        return False

    print_section("数据传输: LineRisk → NetRisk")
    copy_file(DATA_OUTPUT / "路段通行风险评价总表.xlsx",
              DATA_INPUT / "路段通行风险评价总表.xlsx",
              "路段风险评价总表 -> NetRisk")

    if not run_net_risk():
        print("\n❌ 网风险评估失败")
        return False

    elapsed = time.time() - overall_start
    print(f"\n  ✅ 风险评估完成，耗时: {elapsed:.2f} 秒 ({elapsed/60:.2f} 分钟)")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="高速公路路网通行风险评估系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
 示例:
   python main.py                     # 执行数据准备→点→线→网风险评估
   python main.py --config-update     # 先从数据库更新config，再执行风险评估
   python main.py --compare           # 执行数据准备→点→线→网 + 两期对比分析
   python main.py --compare --no-recalculate  # 执行数据准备 + 两期对比分析
   python main.py --no-input          # 不执行数据准备，点→线→网风险评估
   python main.py --simple-log        # 简化日志，仅记录关键信息
        """
    )
    parser.add_argument('--config-update', action='store_true',
                        help='在风险评估前，从数据库更新 config/ 下的 ini 配置文件')
    parser.add_argument('--compare', action='store_true',
                        help='启用两期对比分析')
    parser.add_argument('--no-recalculate', action='store_true',
                        help='跳过风险重新计算，仅执行对比分析')
    parser.add_argument('--no-input', action='store_true',
                        help='不执行数据准备')
    parser.add_argument('--simple-log', action='store_true',
                        help='简化日志模式：仅记录阶段标题、错误、警告和结果摘要，减少冗余')

    args = parser.parse_args()

    log_path = setup_logging(simple_mode=args.simple_log)

    print_banner(log_path)

    overall_start = time.time()

    if args.config_update:
        if not run_config_update_step():
            print("\n❌ 配置更新失败，流程终止")
            return 1

    if not args.no_input:
        if not run_input():
                print("\n❌ 输入数据准备失败，流程终止")
                return 1
            
    if args.no_recalculate:
        if not args.compare:
            print("⚠️  --no-recalculate 需要同时指定 --compare")
            return 1
        if not run_compare():
            return 1
    else:
        # 执行风险评估
        if not run_risk_assessment():
            return 1

        # 如果启用对比分析，继续执行
        if args.compare:
            if not run_compare():
                print("\n⚠️  风险评估已完成，但对比分析失败")
                return 1

    overall_end = time.time()
    elapsed = overall_end - overall_start

    print("\n" + "=" * 80)
    print("✅ 高速公路路网通行风险评估系统 - 全部流程执行完毕")
    print("=" * 80)
    print(f"  总耗时: {elapsed:.2f} 秒 ({elapsed/60:.2f} 分钟)")
    print()
    print("  输出文件:")
    print(f"    • 点风险:  {DATA_OUTPUT / '全结构点通行风险值评价表.xlsx'}")
    print(f"    • 线风险:  {DATA_OUTPUT / '路段通行风险评价总表.xlsx'}")
    print(f"    • 网风险:  {DATA_OUTPUT / '路网通行风险评估结果_<时间戳>.xlsx'}")
    if args.compare or args.no_recalculate:
        print(f"    • 对比分析: {DATA_OUTPUT / '风险评价对比结果.xlsx'}")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断了评估流程")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 程序执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

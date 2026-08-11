"""
输入数据准备模块 - 总控入口

功能:
  1. 从ETC_Data读取双月交通流Excel文件，合并为单个CSV放入data/input/traffic_data/
  2. 从数据库导出气象预警、交通事故等数据到data/input/

使用方式:
  python -m src.input.input_main                 # 执行全部数据准备
  python -m src.input.input_main --etc-only      # 仅合并ETC交通流数据
  python -m src.input.input_main --db-only       # 仅从数据库导出
  python -m src.input.input_main --list-tables   # 列出数据库中可用表格
  python -m src.input.input_main --test-connection  # 测试数据库连接
  python -m src.input.input_main --set-date 2025-08-01  # 设置归属日期
"""

import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent.resolve()

from .config_manager import InputConfigManager
from .excel_tocsv import merge_excel_to_csv
from .database_exporter import DatabaseExporter


def print_banner():
    print("\n" + "=" * 60)
    print("     输入数据准备模块")
    print(f"     项目根目录: {BASE_DIR}")
    print("=" * 60)


def run_etc_traffic_merge(config_manager: InputConfigManager = None) -> bool:
    print("\n" + "#" * 60)
    print("##  阶段 1: ETC交通流数据合并")
    print("#" * 60)
    try:
        merge_excel_to_csv(config_manager)
        return True
    except Exception as e:
        print(f"ETC数据合并失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_db_export(config_manager: InputConfigManager = None, command: str = 'export-all') -> bool:
    print("\n" + "#" * 60)
    print("##  阶段 2: 数据库导出")
    print("#" * 60)
    try:
        exporter = DatabaseExporter(config_manager)

        if command == 'export-all':
            return exporter.export_all_tables()
        elif command == 'export-point':
            return exporter.export_point_alert_to_json()
        elif command == 'export-district':
            return exporter.export_district_alert_to_excel()
        elif command == 'export-accident':
            return exporter.export_accident_to_excel()
        elif command == 'list-tables':
            exporter.list_available_tables()
            return True
        elif command == 'test-connection':
            return exporter.test_connection()
        else:
            print(f"未知命令: {command}")
            return False

    except Exception as e:
        print(f"数据库导出失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all(config_manager: InputConfigManager = None) -> bool:
    overall_start = time.time()

    if not run_etc_traffic_merge(config_manager):
        print("\nETC交通流数据合并失败，流程终止")
        return False

    if not run_db_export(config_manager):
        print("\n数据库导出失败")
        return False

    elapsed = time.time() - overall_start
    print(f"\n输入数据准备完成，耗时: {elapsed:.2f} 秒 ({elapsed / 60:.2f} 分钟)")
    return True


def print_help():
    help_text = """
输入数据准备模块 - 帮助信息

用法:
  python -m src.input.input_main [选项]

选项:
  --etc-only           仅合并ETC交通流数据
  --db-only            仅从数据库导出数据
  --export-point       仅导出point_alert表格到JSON
  --export-district    仅导出district_alert表格到Excel
  --export-accident    仅导出accident表格到Excel
  --list-tables        列出数据库中可用的表格
  --test-connection    测试数据库连接
  --set-date <date>    设置归属日期，格式: YYYY-MM-DD
  --help, -h           显示帮助信息

示例:
  python -m src.input.input_main                    # 执行全部数据准备
  python -m src.input.input_main --etc-only         # 仅合并ETC交通流数据
  python -m src.input.input_main --db-only          # 仅从数据库导出
  python -m src.input.input_main --set-date 2025-08-01  # 设置归属日期
"""
    print(help_text)


def main():
    print_banner()

    config_manager = InputConfigManager()

    if '--help' in sys.argv or '-h' in sys.argv:
        print_help()
        return

    if '--set-date' in sys.argv:
        idx = sys.argv.index('--set-date')
        if idx + 1 < len(sys.argv):
            new_date = sys.argv[idx + 1]
            config_manager.update_belong_date(new_date)
        else:
            print("请提供日期参数")
        return

    if '--etc-only' in sys.argv:
        success = run_etc_traffic_merge(config_manager)
        if not success:
            sys.exit(1)
        return

    if '--db-only' in sys.argv:
        success = run_db_export(config_manager, 'export-all')
        if not success:
            sys.exit(1)
        return

    if '--export-point' in sys.argv:
        success = run_db_export(config_manager, 'export-point')
        if not success:
            sys.exit(1)
        return

    if '--export-district' in sys.argv:
        success = run_db_export(config_manager, 'export-district')
        if not success:
            sys.exit(1)
        return

    if '--export-accident' in sys.argv:
        success = run_db_export(config_manager, 'export-accident')
        if not success:
            sys.exit(1)
        return

    if '--list-tables' in sys.argv:
        run_db_export(config_manager, 'list-tables')
        return

    if '--test-connection' in sys.argv:
        success = run_db_export(config_manager, 'test-connection')
        if not success:
            sys.exit(1)
        return

    if not run_all(config_manager):
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断了输入数据准备流程")
        sys.exit(130)
    except Exception as e:
        print(f"\n程序执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

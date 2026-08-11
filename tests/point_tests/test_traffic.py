#!/usr/bin/env python3
"""
测试脚本：检查流量数据输出文件并验证数据库保存
"""

import pandas as pd
import os

def test_read_traffic_output():
    """测试读取流量评估输出文件"""
    print("="*80)
    print("测试读取流量评估输出文件")
    print("="*80)

    # 检查输出文件
    output_paths = [
        'data/temp/双月门架风险评估表.xlsx',
        'data/temp/双月门架风险评估表_路段信息.xlsx',
        'data/temp/2025年12月门架流量统计结果.xlsx'
    ]

    for path in output_paths:
        if os.path.exists(path):
            try:
                print(f"\n读取文件: {path}")
                df = pd.read_excel(path)
                print(f"文件存在，形状: {df.shape}")
                print(f"列名: {list(df.columns)}")
                if not df.empty:
                    print(f"前3行数据:")
                    print(df.head(3))

                    # 特别检查是否有'门架编码'或'门架编号'列
                    gantry_cols = ['门架编码', '门架编号', 'etc_id', 'ETC_ID', 'gantry_id']
                    found_cols = [col for col in gantry_cols if col in df.columns]
                    if found_cols:
                        print(f"找到门架列: {found_cols}")
                        print(f"门架列示例值: {df[found_cols[0]].head(5).tolist()}")
                    else:
                        print("警告: 未找到门架标识列")

                else:
                    print("警告: 文件为空")
            except Exception as e:
                print(f"读取文件失败: {e}")
        else:
            print(f"文件不存在: {path}")

    print("\n" + "="*80)
    print("检查数据库保存列名映射")
    print("="*80)

    # 模拟数据库保存逻辑
    from src.point_risk.database.database_connector import DatabaseConnector

    # 读取一个示例文件来测试
    test_file = 'data/temp/双月门架风险评估表.xlsx'
    if os.path.exists(test_file):
        try:
            test_df = pd.read_excel(test_file)
            print(f"测试DataFrame形状: {test_df.shape}")
            print(f"测试DataFrame列名: {list(test_df.columns)}")

            # 测试列名映射
            column_mapping = {
                '门架编码': 'etc_id',
                '门架编号': 'etc_id',  # 兼容两种列名
                '日均高峰小时流量': 'daily_busy_hour_traffic',
                '日均大型车占比': 'daily_largelrate',
                '日均高峰小时车速离散差': 'daily_busyhourdiscrete',
                '拥挤度': 'crowdedness',
                '拥挤度风险值': 'crowd_risk',
                '交通组成风险值': 'composition_risk',
                '离散差风险值': 'discrete_risk'
            }

            print("\n列名映射检查:")
            available_mapping = {}
            for excel_col, db_col in column_mapping.items():
                if excel_col in test_df.columns:
                    available_mapping[excel_col] = db_col
                    print(f"  ✅ '{excel_col}' -> '{db_col}'")
                else:
                    print(f"  ❌ '{excel_col}' 不存在")

            if not available_mapping:
                print("警告: 没有找到任何可映射的列!")
                # 检查DataFrame实际的列名
                print(f"实际列名: {list(test_df.columns)}")
                # 尝试匹配相似的列名
                for actual_col in test_df.columns:
                    for excel_col in column_mapping.keys():
                        if excel_col in actual_col or actual_col in excel_col:
                            print(f"  🔍 相似列名: '{actual_col}' 可能对应 '{excel_col}'")

        except Exception as e:
            print(f"测试失败: {e}")

if __name__ == "__main__":
    test_read_traffic_output()

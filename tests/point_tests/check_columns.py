#!/usr/bin/env python3
"""
检查Excel文件列名和数据库映射
"""

import pandas as pd
import sys
import os

def check_traffic_file():
    """检查流量评估文件"""
    file_path = '../../data/temp/双月门架风险评估表.xlsx'

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return

    try:
        # 读取Excel文件
        df = pd.read_excel(file_path)
        print(f"文件: {file_path}")
        print(f"形状: {df.shape}")
        print(f"列名: {list(df.columns)}")
        print(f"数据类型:\n{df.dtypes}")

        if not df.empty:
            print(f"\n前5行数据:")
            print(df.head())

            # 检查门架编码列
            gantry_cols = ['门架编码', '门架编号', 'etc_id', 'ETC_ID', 'gantry_id', '门架ID', '当前门架']
            found_gantry = None
            for col in gantry_cols:
                if col in df.columns:
                    found_gantry = col
                    print(f"找到门架列: '{col}'")
                    print(f"门架值示例: {df[col].head(10).tolist()}")
                    break

            if not found_gantry:
                print("警告: 未找到任何门架标识列!")
                # 显示所有列名
                print(f"实际列名: {list(df.columns)}")

            # 检查其他关键列
            key_columns = ['日均高峰小时流量', '日均高峰小时车速离散差', '日均大型车占比',
                          '拥挤度', '拥挤度风险值', '交通组成风险值', '离散差风险值']

            print(f"\n关键列检查:")
            for col in key_columns:
                if col in df.columns:
                    print(f"  ✅ '{col}' 存在")
                else:
                    print(f"  ❌ '{col}' 不存在")

            # 尝试数据库映射
            print(f"\n数据库映射测试:")
            column_mapping = {
                '门架编码': 'etc_id',
                '门架编号': 'etc_id',
                'etc_id': 'etc_id',
                'ETC_ID': 'etc_id',
                'gantry_id': 'etc_id',
                '门架ID': 'etc_id',
                '当前门架': 'etc_id',
                '日均高峰小时流量': 'daily_busy_hour_traffic',
                '高峰小时流量': 'daily_busy_hour_traffic',
                '日均流量': 'daily_busy_hour_traffic',
                '流量': 'daily_busy_hour_traffic',
                '日均大型车占比': 'daily_largelrate',
                '大型车占比': 'daily_largelrate',
                '大车比例': 'daily_largelrate',
                '货车比例': 'daily_largelrate',
                '日均高峰小时车速离散差': 'daily_busyhourdiscrete',
                '车速离散差': 'daily_busyhourdiscrete',
                '速度离散差': 'daily_busyhourdiscrete',
                '离散差': 'daily_busyhourdiscrete',
                '拥挤度': 'crowdedness',
                '拥堵度': 'crowdedness',
                '饱和度': 'crowdedness',
                '拥挤度风险值': 'crowd_risk',
                '拥堵风险值': 'crowd_risk',
                '交通组成风险值': 'composition_risk',
                '组成风险值': 'composition_risk',
                '离散差风险值': 'discrete_risk',
                '速度风险值': 'discrete_risk'
            }

            # 检查映射
            mapped_columns = {}
            for excel_col, db_col in column_mapping.items():
                if excel_col in df.columns:
                    mapped_columns[excel_col] = db_col
                    print(f"  ✅ '{excel_col}' -> '{db_col}'")

            if not mapped_columns:
                print("  警告: 没有找到任何精确匹配的列!")
                print("  尝试模糊匹配...")
                for actual_col in df.columns:
                    actual_col_lower = str(actual_col).lower()
                    for excel_col, db_col in column_mapping.items():
                        excel_col_lower = str(excel_col).lower()
                        if excel_col_lower in actual_col_lower or actual_col_lower in excel_col_lower:
                            mapped_columns[actual_col] = db_col
                            print(f"  🔍 '{actual_col}' -> '{db_col}' (原映射: '{excel_col}')")
                            break

            # 检查必需字段
            required_db_fields = ['etc_id']
            for field in required_db_fields:
                if field in mapped_columns.values():
                    print(f"  ✅ 必需字段 '{field}' 已映射")
                else:
                    print(f"  ❌ 必需字段 '{field}' 未映射")

                    # 尝试找到对应的列
                    possible_excel_cols = []
                    for excel_col, db_col in column_mapping.items():
                        if db_col == field:
                            possible_excel_cols.append(excel_col)

                    print(f"    可能对应的Excel列名: {possible_excel_cols}")
                    print(f"    实际Excel列名: {list(df.columns)}")

            # 检查是否有空值
            if found_gantry:
                null_count = df[found_gantry].isnull().sum()
                print(f"\n门架列空值检查:")
                print(f"  总行数: {len(df)}")
                print(f"  空值数量: {null_count}")
                if null_count > 0:
                    print(f"  有 {null_count} 个空值，这可能导致数据无法插入")

    except Exception as e:
        print(f"读取文件失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_traffic_file()
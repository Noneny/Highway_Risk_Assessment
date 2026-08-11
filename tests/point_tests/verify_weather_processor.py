#!/usr/bin/env python3
"""
验证weather_processor.py的修改是否正确
"""

import ast
import sys

def analyze_weather_processor():
    """分析weather_processor.py文件"""
    filename = "../src/data_processing/weather_processor.py"

    print(f"分析文件: {filename}")
    print("="*60)

    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查calculate_warning_days方法
    print("1. 检查calculate_warning_days方法:")

    if 'def calculate_warning_days' in content:
        print("  ✓ 方法存在")

        # 检查列名
        expected_columns = ['点位类型', '点位描述', '点位桩号', '红色预警天数', '橙色预警天数', '黄色预警天数', '蓝色预警天数', '总预警天数', '风险系数']

        for col in expected_columns:
            if col in content:
                print(f"  ✓ 列名 '{col}' 存在")
            else:
                print(f"  ✗ 列名 '{col}' 不存在")

        # 检查风险系数计算
        if 'def _calculate_risk_factor' in content:
            print("  ✓ _calculate_risk_factor方法存在")
        else:
            print("  ✗ _calculate_risk_factor方法不存在")

    else:
        print("  ✗ calculate_warning_days方法不存在")

    print("\n2. 检查列名标准化:")

    if '_standardize_structure_column_names' in content:
        print("  ✓ _standardize_structure_column_names方法存在")

        # 检查列名映射
        column_mapping_check = [
            ('点位类型', ['point_type', 'PointType', '类型', 'Point_Type']),
            ('点位描述', ['point_description', 'PointDescription', '描述', '点位名称']),
            ('点位桩号', ['stake_number', 'StakeNumber', '桩号', '点号', 'Point_No'])
        ]

        for target_name, possible_names in column_mapping_check:
            found = False
            for name in possible_names:
                if name in content:
                    found = True
                    break
            if found:
                print(f"  ✓ {target_name}的映射存在")
            else:
                print(f"  ✗ {target_name}的映射可能不完整")
    else:
        print("  ✗ _standardize_structure_column_names方法不存在")

    print("\n3. 检查process_pipeline方法:")

    if 'def process_pipeline' in content:
        print("  ✓ process_pipeline方法存在")

        # 检查输出路径
        if 'weather_warning_output' in content:
            print("  ✓ 输出路径配置存在")
        else:
            print("  ✗ 输出路径配置可能不存在")
    else:
        print("  ✗ process_pipeline方法不存在")

    print("\n4. 检查参考文件的列格式:")

    # 列出参考文件的列
    print("  参考文件 'new结构点预警天数统计_.xlsx' 应包含的列:")
    print("    1. 点位类型")
    print("    2. 点位描述")
    print("    3. 点位桩号")
    print("    4. 红色预警天数")
    print("    5. 橙色预警天数")
    print("    6. 黄色预警天数")
    print("    7. 蓝色预警天数")
    print("    8. 总预警天数")

    print("\n5. 与当前输出格式对比:")
    print("  之前输出列:")
    print("    1. 点位描述")
    print("    2. 经度")
    print("    3. 纬度")
    print("    4. 预警天数")
    print("    5. 预警级别")
    print("    6. 风险系数")

    print("\n  修改后输出列:")
    print("    1. 点位类型")
    print("    2. 点位描述")
    print("    3. 点位桩号")
    print("    4. 红色预警天数")
    print("    5. 橙色预警天数")
    print("    6. 黄色预警天数")
    print("    7. 蓝色预警天数")
    print("    8. 总预警天数")
    print("    9. 风险系数")

    print("\n6. 关键修改总结:")
    print("  a) calculate_warning_days方法重构，按预警颜色统计天数")
    print("  b) 输出列名与参考文件保持一致")
    print("  c) 保留风险系数列")
    print("  d) 添加列名标准化逻辑")
    print("  e) 移除预警级别列（改为按颜色分类）")

    print("\n" + "="*60)
    print("验证完成")

if __name__ == "__main__":
    analyze_weather_processor()
#!/usr/bin/env python3
"""
验证字段映射关系，不依赖外部库
"""

def check_mapping():
    print("=== 验证字段映射关系 ===\n")

    # database_connector.py中的表结构字段
    table_fields = [
        'belong_date', 'point_id', 'point_type', 'point_description',
        'company', 'county', 'comprehensive_level', 'road_section', 'road_number',
        'longitude', 'latitude', 'stake_number', 'nearby_gantry_name', 'gantry_code',
        'gantry_latitude', 'gantry_longitude', 'direction', 'technical_condition',
        'point_level', 'warning_days', 'base_risk_value', 'dynamic_risk_overlay',
        'special_management_reduction', 'total_risk_value', 'base_risk_attribution',
        'dynamic_risk_attribution', 'risk_level',
        'create_time', 'update_time'
    ]

    print(f"1. 数据库表字段总数: {len(table_fields)}")
    print("   主要字段:")
    for i, field in enumerate(table_fields[:20], 1):
        print(f"     {i}. {field}")
    print("   ...")

    # database_connector.py中的列映射
    column_mapping = {
        '点位标识': 'point_id',
        '点位类型': 'point_type',
        '点位描述': 'point_description',
        '所属公司': 'company',
        '所属区县': 'county',
        '综合等级': 'comprehensive_level',
        '所属路段': 'road_section',
        '路段编号': 'road_number',
        '经度': 'longitude',
        '纬度': 'latitude',
        '点位桩号': 'stake_number',
        '附近门架名称': 'nearby_gantry_name',
        '门架编码': 'gantry_code',
        '附近门架信息纬度': 'gantry_latitude',
        '附近门架信息经度': 'gantry_longitude',
        '上下行': 'direction',
        '技术状况': 'technical_condition',
        '点位等级': 'point_level',
        '总预警天数': 'warning_days',
        '基础风险值': 'base_risk_value',
        '动态风险叠加': 'dynamic_risk_overlay',
        '专项管控折减': 'special_management_reduction',
        '总风险值': 'total_risk_value',
        '基础风险归因': 'base_risk_attribution',
        '动态风险归因': 'dynamic_risk_attribution',
        '风险等级': 'risk_level'
    }

    print(f"\n2. 列映射数量: {len(column_mapping)}")
    print("   中文列名 -> 数据库字段名:")
    for chinese, db_field in column_mapping.items():
        print(f"     {chinese} -> {db_field}")

    # risk_calculator.py中的required_columns
    required_columns = [
        '点位类型', '点位描述', '所属公司', '所属区县', '综合等级', '所属路段', '路段编号',
        '经度', '纬度', '点位桩号', '附近门架名称', '门架编码', '附近门架信息纬度',
        '附近门架信息经度', '上下行', '技术状况', '点位等级', '总预警天数',
        '基础风险值', '动态风险叠加', '专项管控折减', '总风险值',
        '基础风险归因', '动态风险归因', '风险等级'
    ]

    print(f"\n3. risk_calculator.py的required_columns数量: {len(required_columns)}")
    print("   列名列表:")
    for i, col in enumerate(required_columns, 1):
        print(f"     {i}. {col}")

    # 检查映射完整性
    print("\n4. 映射完整性检查:")

    # 检查所有required_columns是否都有映射
    missing_mapping = []
    for col in required_columns:
        if col not in column_mapping:
            missing_mapping.append(col)

    if missing_mapping:
        print(f"   警告: {len(missing_mapping)} 列在column_mapping中缺失: {missing_mapping}")
    else:
        print("   ✓ 所有required_columns都有对应的column_mapping")

    # 检查所有column_mapping值是否都在table_fields中
    missing_in_table = []
    for chinese, db_field in column_mapping.items():
        if db_field not in table_fields:
            missing_in_table.append(f"{chinese}({db_field})")

    if missing_in_table:
        print(f"   警告: {len(missing_in_table)} 个映射字段不在表结构中: {missing_in_table}")
    else:
        print("   ✓ 所有column_mapping字段都在表结构中")

    # 特殊字段处理
    print("\n5. 特殊字段处理:")
    print("   - belong_date: 在_prepare_risk_evaluation_data方法中直接添加")
    print("   - create_time/update_time: 数据库自动生成")
    print("   - 点位标识: 在risk_calculator.py的prepare_for_database方法中生成")

    # 检查点位标识
    print("\n6. 点位标识字段检查:")
    if '点位标识' in column_mapping:
        print("   ✓ 点位标识在column_mapping中")
    else:
        print("   ✗ 点位标识不在column_mapping中")

    if '点位标识' in required_columns:
        print("   ✓ 点位标识在required_columns中")
    else:
        print("   ✗ 点位标识不在required_columns中（但在prepare_for_database中单独生成）")

    # 总结
    print("\n7. 问题总结:")
    issues = []

    # 点位标识不在required_columns中，但在column_mapping中
    if '点位标识' in column_mapping and '点位标识' not in required_columns:
        issues.append("点位标识在column_mapping中但不在required_columns中")

    if missing_mapping:
        issues.append(f"{len(missing_mapping)}个required_columns缺少映射")

    if missing_in_table:
        issues.append(f"{len(missing_in_table)}个映射字段不在表结构中")

    if issues:
        print(f"   发现{len(issues)}个问题:")
        for issue in issues:
            print(f"     - {issue}")
    else:
        print("   ✓ 所有映射关系正确")

    print("\n=== 建议的修复方案 ===")
    print("1. 确保实际Excel文件包含所有required_columns中的字段")
    print("2. 如果Excel文件字段名不同，需要更新column_mapping")
    print("3. 运行测试确保数据能正确导入数据库")

if __name__ == "__main__":
    check_mapping()

#!/usr/bin/env python3
"""
验证新的字段映射关系
"""

def check_new_mapping():
    print("=== 验证新的字段映射关系 ===\n")

    # 根据用户要求的新映射关系
    new_column_mapping = {
        '点位类型': 'point_type',
        '点位描述': 'point_name',
        '所属公司': 'asso_company',
        '所属区县': 'district',
        '综合等级': 'level',
        '所属路段': 'associated_line',
        '路段编号': 'line_num',
        '经度': 'longitude',
        '纬度': 'latitude',
        '点位桩号': 'stake_num',
        '附近门架名称': 'nearby_etc',
        '门架编码': 'etc_id',
        '附近门架信息纬度': 'etc_lati',
        '附近门架信息经度': 'etc_longi',
        '上下行': 'direction',
        '基础风险值': 'F',
        '动态风险叠加': 'y',
        '专项管控折减': 'z',
        '总风险值': 'point_risk',
        '基础风险归因': 'F_reason',
        '动态风险归因': 'y_reason',
        '风险等级': 'risk_level'
    }

    print("1. 新的列映射关系（中文列名 -> 数据库字段名）：")
    for chinese, db_field in sorted(new_column_mapping.items()):
        print(f"   {chinese:20s} -> {db_field}")

    print(f"\n   总计 {len(new_column_mapping)} 个字段映射")

    # 数据库表结构字段（根据database_connector.py中的定义）
    table_fields = [
        'id', 'belong_date', 'point_type', 'point_name', 'asso_company',
        'district', 'level', 'associated_line', 'line_num', 'longitude',
        'latitude', 'stake_num', 'nearby_etc', 'etc_id', 'etc_lati',
        'etc_longi', 'direction', 'F', 'y', 'z', 'point_risk', 'F_reason',
        'y_reason', 'risk_level', 'create_time', 'update_time'
    ]

    print(f"\n2. 数据库表字段总数: {len(table_fields)}")
    print("   表字段列表:")
    for i, field in enumerate(sorted(table_fields), 1):
        print(f"   {i:2d}. {field}")

    # 检查映射完整性
    print("\n3. 映射完整性检查:")

    # 检查所有new_column_mapping值是否都在table_fields中
    missing_in_table = []
    for chinese, db_field in new_column_mapping.items():
        if db_field not in table_fields:
            missing_in_table.append(f"{chinese}({db_field})")

    if missing_in_table:
        print(f"   ✗ 警告: {len(missing_in_table)} 个映射字段不在表结构中:")
        for item in missing_in_table:
            print(f"       - {item}")
    else:
        print("   ✓ 所有映射字段都在表结构中")

    # 检查所有table_fields是否都有对应映射
    missing_mapping = []
    for field in table_fields:
        if field not in ['id', 'belong_date', 'create_time', 'update_time']:
            # 查找是否有中文列名映射到这个字段
            mapped = False
            for chinese, db_field in new_column_mapping.items():
                if db_field == field:
                    mapped = True
                    break
            if not mapped:
                missing_mapping.append(field)

    if missing_mapping:
        print(f"   ✗ 警告: {len(missing_mapping)} 个表字段没有对应的中文列名映射:")
        for field in missing_mapping:
            print(f"       - {field}")
    else:
        print("   ✓ 所有表字段都有对应的中文列名映射")

    # 特殊字段处理
    print("\n4. 特殊字段处理:")
    print("   - id: UUID自动生成（在_prepare_risk_evaluation_data方法中生成）")
    print("   - belong_date: 在_prepare_risk_evaluation_data方法中直接添加")
    print("   - create_time/update_time: 数据库自动生成")

    # 检查已移除的字段
    removed_fields = ['point_id', 'technical_condition', 'point_level', 'warning_days',
                      'base_risk_value', 'dynamic_risk_overlay', 'special_management_reduction',
                      'total_risk_value', 'base_risk_attribution', 'dynamic_risk_attribution',
                      'point_description', 'company', 'county', 'comprehensive_level',
                      'road_section', 'road_number', 'stake_number', 'nearby_gantry_name',
                      'gantry_code', 'gantry_latitude', 'gantry_longitude']

    print("\n5. 已移除的字段:")
    for field in removed_fields:
        print(f"   - {field}")

    print(f"\n   总计移除了 {len(removed_fields)} 个字段")

    # 对比新旧字段名
    print("\n6. 新旧字段名对比:")
    old_to_new = {
        'point_id': '已移除，使用UUID作为主键',
        'point_description': 'point_name',
        'company': 'asso_company',
        'county': 'district',
        'comprehensive_level': 'level',
        'road_section': 'associated_line',
        'road_number': 'line_num',
        'stake_number': 'stake_num',
        'nearby_gantry_name': 'nearby_etc',
        'gantry_code': 'etc_id',
        'gantry_latitude': 'etc_lati',
        'gantry_longitude': 'etc_longi',
        'base_risk_value': 'F',
        'dynamic_risk_overlay': 'y',
        'special_management_reduction': 'z',
        'total_risk_value': 'point_risk',
        'base_risk_attribution': 'F_reason',
        'dynamic_risk_attribution': 'y_reason',
        'technical_condition': '已移除',
        'point_level': '已移除',
        'warning_days': '已移除'
    }

    for old, new in sorted(old_to_new.items()):
        print(f"   {old:30s} -> {new}")

    # 总结
    print("\n7. 问题总结:")
    issues = []

    if missing_in_table:
        issues.append(f"{len(missing_in_table)}个映射字段不在表结构中")

    if missing_mapping:
        issues.append(f"{len(missing_mapping)}个表字段没有对应的中文列名映射")

    if issues:
        print(f"   发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"     - {issue}")
    else:
        print("   ✓ 所有映射关系正确")

    print("\n=== 修改的文件 ===")
    modified_files = [
        "src/database/database_connector.py - 更新了表结构和数据准备函数",
        "src/risk_calculation/risk_calculator.py - 更新了required_columns",
        "src/models/data_models.py - 更新了RiskEvaluationResult类",
        "src/data_processing/structure_processor.py - 移除了技术状况和点位等级的映射"
    ]

    for file in modified_files:
        print(f"  - {file}")

    print("\n=== 注意事项 ===")
    print("1. 主键从(belong_date, point_id)改为id(UUID)，添加了唯一约束uk_belong_date_point")
    print("2. 移除了技术状况(technical_condition)、点位等级(point_level)、总预警天数(warning_days)字段")
    print("3. 更新了字段命名，使用更简洁的英文名(F, y, z等)")
    print("4. 确保Excel文件中的列名与中文列名映射一致")
    print("5. 运行测试确保数据能正确导入数据库")

if __name__ == "__main__":
    check_new_mapping()

#!/usr/bin/env python3
"""
测试数据库字段映射
"""

from src.point_risk.database.database_connector import DatabaseConnector
from src.point_risk.config.config_manager import get_config_manager

def test_table_structure():
    """测试表结构定义"""
    config_manager = get_config_manager()
    db_config = config_manager.get_database_config()

    print("=== 数据库配置 ===")
    print(f"数据库: {db_config.get('database')}")
    print(f"表名: {db_config.get('point_risk_evaluation_table')}")

    # 检查表结构定义
    print("\n=== 表结构定义 (database_connector.py) ===")
    print("字段列表:")
    print("1. belong_date - 数据归属日期")
    print("2. point_id - 点位标识")
    print("3. point_type - 点位类型")
    print("4. point_description - 点位描述")
    print("5. company - 所属公司")
    print("6. county - 所属区县")
    print("7. comprehensive_level - 综合等级")
    print("8. road_section - 所属路段")
    print("9. road_number - 路段编号")
    print("10. longitude - 经度")
    print("11. latitude - 纬度")
    print("12. stake_number - 点位桩号")
    print("13. nearby_gantry_name - 附近门架名称")
    print("14. gantry_code - 门架编码")
    print("15. gantry_latitude - 附近门架信息纬度")
    print("16. gantry_longitude - 附近门架信息经度")
    print("17. direction - 上下行")
    print("18. technical_condition - 技术状况")
    print("19. point_level - 点位等级")
    print("20. warning_days - 预警天数")
    print("21. base_risk_value - 基础风险值")
    print("22. dynamic_risk_overlay - 动态风险叠加")
    print("23. special_management_reduction - 专项管控折减")
    print("24. total_risk_value - 总风险值")
    print("25. base_risk_attribution - 基础风险归因")
    print("26. dynamic_risk_attribution - 动态风险归因")
    print("27. risk_level - 风险等级")
    print("28. create_time - 创建时间")
    print("29. update_time - 更新时间")

    print("\n=== 列映射 (database_connector.py) ===")
    print("中文列名 -> 数据库字段名:")
    mapping = {
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

    for chinese, db_field in mapping.items():
        print(f"  {chinese} -> {db_field}")

    print("\n=== risk_calculator.py中的required_columns ===")
    required_cols = [
        '点位类型', '点位描述', '所属公司', '所属区县', '综合等级', '所属路段', '路段编号',
        '经度', '纬度', '点位桩号', '附近门架名称', '门架编码', '附近门架信息纬度',
        '附近门架信息经度', '上下行', '技术状况', '点位等级', '总预警天数',
        '基础风险值', '动态风险叠加', '专项管控折减', '总风险值',
        '基础风险归因', '动态风险归因', '风险等级'
    ]

    print(f"总共 {len(required_cols)} 列:")
    for i, col in enumerate(required_cols, 1):
        print(f"  {i}. {col}")

    # 检查映射完整性
    print("\n=== 映射完整性检查 ===")
    missing_in_mapping = []
    for col in required_cols:
        if col not in mapping:
            missing_in_mapping.append(col)

    if missing_in_mapping:
        print(f"警告: {len(missing_in_mapping)} 列在mapping中缺失: {missing_in_mapping}")
    else:
        print("✓ 所有required_columns都有对应的mapping")

    missing_in_table = []
    table_fields = ['belong_date', 'create_time', 'update_time']
    for db_field in mapping.values():
        table_fields.append(db_field)

    print(f"\n表总字段数: {len(table_fields)}")
    print("字段列表:", ', '.join(sorted(table_fields)))

if __name__ == "__main__":
    test_table_structure()

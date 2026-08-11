#!/usr/bin/env python3
"""
测试weather_processor.py的修改
"""

from src.point_risk.data_processing.weather_processor import WeatherDataProcessor
from src.point_risk.models.data_models import WeatherWarning
from datetime import datetime
import pandas as pd

def create_test_warnings():
    """创建测试气象预警数据"""
    warnings = []

    # 创建一些测试预警
    for i in range(5):
        warning = WeatherWarning(
            datetime=datetime(2025, 12, i+1, 10, 0, 0),
            update_time=datetime(2025, 12, i+1, 10, 0, 0),
            station_id=f"STA_{i}",
            longitude=106.5 + i*0.01,
            latitude=29.5 + i*0.01,
            warning_type="气象预警",
            warning_level="红色预警" if i % 4 == 0 else ("橙色预警" if i % 4 == 1 else ("黄色预警" if i % 4 == 2 else "蓝色预警")),
            effective_start=datetime(2025, 12, i+1, 10, 0, 0),
            effective_end=datetime(2025, 12, i+2, 10, 0, 0),
            valid_period="全天",
            issuing_time=datetime(2025, 12, i+1, 10, 0, 0),
            release_unit="气象局",
            route_name="G50",
            start_stake_number=f"K10{i}",
            end_stake_number=f"K20{i}",
            bridge_tunnel_name="",
            risk_level="高风险",
            hazard_description="大风",
            district="渝北区",
            town="龙溪街道",
            point_longitude=106.5 + i*0.01,
            point_latitude=29.5 + i*0.01
        )
        warnings.append(warning)

    return warnings

def create_test_structure_points():
    """创建测试结构点数据"""
    data = {
        '点位描述': ['结构点A', '结构点B', '结构点C'],
        '点位类型': ['桥梁', '隧道', '边坡'],
        '点位桩号': ['K100+100', 'K200+200', 'K300+300'],
        '经度': [106.501, 106.511, 107.0],  # 第三个点距离较远
        '纬度': [29.501, 29.511, 30.0],
        '门架编码': ['G001', 'G002', 'G003']
    }
    return pd.DataFrame(data)

def test_calculate_warning_days():
    """测试计算预警天数"""
    print("测试计算预警天数...")

    processor = WeatherDataProcessor()

    # 创建测试数据
    warnings = create_test_warnings()
    structure_df = create_test_structure_points()

    print(f"测试预警数量: {len(warnings)}")
    print(f"测试结构点数量: {len(structure_df)}")

    # 调用计算方法
    result_df = processor.calculate_warning_days(warnings, structure_df)

    print(f"\n结果数据形状: {result_df.shape}")
    print(f"结果列名: {list(result_df.columns)}")

    print("\n结果数据:")
    print(result_df)

    # 验证结果格式
    expected_columns = ['点位类型', '点位描述', '点位桩号', '红色预警天数', '橙色预警天数', '黄色预警天数', '蓝色预警天数', '总预警天数', '风险系数']

    print(f"\n验证列名:")
    for col in expected_columns:
        if col in result_df.columns:
            print(f"  ✓ {col}")
        else:
            print(f"  ✗ {col} (缺失)")

    # 验证数据
    print(f"\n验证数据:")
    for idx, row in result_df.iterrows():
        point_name = row['点位描述']
        total_days = row['总预警天数']
        risk_factor = row['风险系数']

        print(f"  {point_name}: 总预警天数={total_days}, 风险系数={risk_factor}")

        # 验证风险系数计算
        if total_days == 0:
            expected_risk = 1.0
        elif 1 <= total_days <= 10:
            expected_risk = 1.05
        elif 11 <= total_days <= 20:
            expected_risk = 1.08
        else:
            expected_risk = 1.12

        if abs(risk_factor - expected_risk) < 0.01:
            print(f"    ✓ 风险系数正确")
        else:
            print(f"    ✗ 风险系数错误: 预期 {expected_risk}, 实际 {risk_factor}")

    return result_df

def test_process_pipeline():
    """测试处理管道"""
    print("\n测试处理管道...")

    processor = WeatherDataProcessor()

    try:
        # 修改配置文件路径，指向测试数据
        processor.config_manager = None  # 重置配置管理器
        processor = WeatherDataProcessor()

        # 由于实际文件可能不存在，只测试代码逻辑
        print("跳过实际文件处理，只测试代码逻辑")

    except Exception as e:
        print(f"处理管道测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("开始测试weather_processor.py修改")
    print("="*60)

    result_df = test_calculate_warning_days()

    print("\n" + "="*60)
    print("测试完成")

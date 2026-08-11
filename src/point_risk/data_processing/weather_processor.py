"""
气象预警数据处理
处理气象预警JSON文件，统计预警天数
对应原项目中的 [2]newweather_prehandle_1filendays.py 和 [3]newweather_add_to_dynamic.py
"""

import json
import glob
import os
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from .base_processor import BaseDataProcessor
from ..models.data_models import WeatherWarning, StructurePoint
from ..database.database_connector import create_database_connector_from_config
from ..database.database_connector import create_database_connector_from_config


class WeatherDataProcessor(BaseDataProcessor):
    """气象预警数据处理类"""

    def __init__(self):
        """初始化气象预警处理器"""
        super().__init__(config_section='paths')
        self.weather_params = self.config_manager.get_weather_params()
        self.risk_params = self.config_manager.get_risk_params()
        self.warning_radius = self.weather_params.get('warning_radius', 5.0)  # 预警半径(公里)
        self.belong_date = self.weather_params.get('belong_date', '2025-12-01')
        # 新增：初始化数据库连接器
        self.db_connector = create_database_connector_from_config(self.config_manager)
        # 新增：初始化数据库连接器
        self.db_connector = create_database_connector_from_config(self.config_manager)

    def load_weather_warnings(self, json_pattern: str = None) -> List[WeatherWarning]:
        """
        加载气象预警数据

        Args:
            json_pattern: JSON文件通配符模式

        Returns:
            气象预警对象列表
        """
        if json_pattern is None:
            paths_config = self.config_manager.get_paths_config()
            json_pattern = paths_config.get('weather_json_pattern', 'data/input/weather_warnings/*.json')

        self.log_processing_step("加载气象预警数据", f"文件模式: {json_pattern}")

        # 查找JSON文件
        json_files = glob.glob(json_pattern)
        if not json_files:
            print(f"警告: 未找到匹配的JSON文件: {json_pattern}")
            return []

        print(f"找到 {len(json_files)} 个JSON文件")

        warnings = []
        warning_count = 0

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 检查数据格式
                if isinstance(data, list):
                    for item in data:
                        try:
                            warning = WeatherWarning.from_json_dict(item)
                            warnings.append(warning)
                            warning_count += 1
                        except Exception as e:
                            print(f"解析预警数据失败 (文件: {json_file}): {e}")
                elif isinstance(data, dict):
                    try:
                        warning = WeatherWarning.from_json_dict(data)
                        warnings.append(warning)
                        warning_count += 1
                    except Exception as e:
                        print(f"解析预警数据失败 (文件: {json_file}): {e}")
                else:
                    print(f"警告: 不支持的JSON格式 (文件: {json_file})")

            except Exception as e:
                print(f"读取JSON文件失败: {json_file}, 错误: {e}")

        print(f"成功加载 {warning_count} 条气象预警记录")
        return warnings

    def load_structure_points(self, structure_file: str = None) -> pd.DataFrame:
        """
        加载结构点数据

        Args:
            structure_file: 结构点数据文件路径

        Returns:
            结构点数据DataFrame
        """
        if structure_file is None:
            paths_config = self.config_manager.get_paths_config()
            structure_file = paths_config.get('structure_excel')

        self.log_processing_step("加载结构点数据", f"文件: {structure_file}")

        if not Path(structure_file).exists():
            raise FileNotFoundError(f"结构点数据文件不存在: {structure_file}")

        df = self.read_excel_file(structure_file)

        # 验证必需的列
        required_columns = ['点位描述', '经度', '纬度', '门架编码']

        if not self.validate_dataframe(df, required_columns):
            # 尝试重命名列
            df = self._standardize_structure_column_names(df)

        return df

    def _standardize_structure_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化结构点列名

        Args:
            df: 输入DataFrame

        Returns:
            标准化后的DataFrame
        """
        column_mapping = {
            '点位描述': ['PointDescription', 'point_description', '描述', '点位名称'],
            '点位类型': ['point_type', 'PointType', '类型', 'Point_Type'],
            '点位桩号': ['stake_number', 'StakeNumber', '桩号', '点号', 'Point_No'],
            '经度': ['Longitude', 'longitude', 'LON', 'lon', '经度坐标'],
            '纬度': ['Latitude', 'latitude', 'LAT', 'lat', '纬度坐标'],
            '门架编码': ['GANTRYID', 'gantry_code', '门架编号', '门架ID']
        }

        renamed_df = df.copy()
        for target_name, possible_names in column_mapping.items():
            if target_name not in renamed_df.columns:
                for name in possible_names:
                    if name in renamed_df.columns:
                        renamed_df.rename(columns={name: target_name}, inplace=True)
                        print(f"  将列 '{name}' 重命名为 '{target_name}'")
                        break

        return renamed_df

    def calculate_warning_days(self, warnings: List[WeatherWarning], structure_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算每个结构点的预警天数

        Args:
            warnings: 气象预警列表
            structure_df: 结构点数据DataFrame

        Returns:
            包含预警天数统计的DataFrame
        """
        self.log_processing_step("计算预警天数", f"预警数量: {len(warnings)}, 结构点数量: {len(structure_df)}")

        # 确保结构点数据包含必要的列
        required_columns = ['点位描述']

        # 尝试标准化列名
        column_mapping = {
            '点位类型': ['point_type', 'PointType', '类型', 'Point_Type'],
            '点位描述': ['point_description', 'PointDescription', '描述', '点位名称'],
            '点位桩号': ['stake_number', 'StakeNumber', '桩号', '点号', 'Point_No'],
            '经度': ['Longitude', 'longitude', 'LON', 'lon', '经度坐标'],
            '纬度': ['Latitude', 'latitude', 'LAT', 'lat', '纬度坐标']
        }

        structure_df_copy = structure_df.copy()
        for target_name, possible_names in column_mapping.items():
            if target_name not in structure_df_copy.columns:
                for name in possible_names:
                    if name in structure_df_copy.columns:
                        structure_df_copy = structure_df_copy.rename(columns={name: target_name})
                        print(f"  将列 '{name}' 重命名为 '{target_name}'")
                        break

        structure_df = structure_df_copy

        # 创建结果DataFrame，按照参考文件的格式
        result_columns = ['点位类型', '点位描述', '点位桩号', '红色预警天数', '橙色预警天数', '黄色预警天数', '蓝色预警天数', '总预警天数', '风险系数']
        result_data = []

        # 为每个结构点创建初始数据行
        for _, row in structure_df.iterrows():
            point_name = row.get('点位描述', '未知')
            point_type = row.get('点位类型', '')
            stake_number = row.get('点位桩号', '')

            result_data.append({
                '点位类型': point_type,
                '点位描述': point_name,
                '点位桩号': stake_number,
                '红色预警天数': 0,
                '橙色预警天数': 0,
                '黄色预警天数': 0,
                '蓝色预警天数': 0,
                '总预警天数': 0,
                '风险系数': 1.0
            })

        result_df = pd.DataFrame(result_data, columns=result_columns)

        print(f"创建结果DataFrame: {result_df.shape}")
        print(f"列名: {list(result_df.columns)}")
        if len(result_df) > 0:
            print("前3行数据:")
            print(result_df.head(3))

        print(f"创建结果DataFrame: {result_df.shape}")
        print(f"列名: {list(result_df.columns)}")
        if len(result_df) > 0:
            print("前3行数据:")
            print(result_df.head(3))

        if not warnings:
            print("警告: 没有气象预警数据，所有结构点的预警天数将为0")
            return result_df

        # 组织预警数据以便快速查询
        warning_dict = defaultdict(list)
        for warning in warnings:
            # 使用预警的经纬度作为键（四舍五入到小数点后4位以减少计算量）
            key = (round(warning.longitude, 4), round(warning.latitude, 4))
            warning_dict[key].append(warning)

        print(f"组织完成 {len(warning_dict)} 个预警位置")

        # 为每个结构点计算预警天数
        total_points = len(result_df)
        points_with_warnings = 0

        # 我们需要结构点的经纬度信息来计算距离
        # 先构建点位经纬度映射
        point_coords = {}
        for idx, row in structure_df.iterrows():
            point_name = row.get('点位描述', '')
            point_lon = row.get('经度', None)
            point_lat = row.get('纬度', None)

            if point_name and point_lon is not None and point_lat is not None and not pd.isna(point_lon) and not pd.isna(point_lat):
                point_coords[point_name] = (float(point_lat), float(point_lon))

        # 遍历每个结构点
        for idx, row in result_df.iterrows():
            point_name = row['点位描述']

            # 检查是否有该点的经纬度信息
            if point_name not in point_coords:
                print(f"警告: 结构点 '{point_name}' 缺少经纬度信息，无法计算预警天数")
                continue

            point_lat, point_lon = point_coords[point_name]

            # 初始化每种颜色预警的天数集合
            red_days = set()
            orange_days = set()
            yellow_days = set()
            blue_days = set()

            # 检查所有预警位置
            for (warning_lon, warning_lat), warning_list in warning_dict.items():
                # 计算距离
                distance = self.calculate_distance(point_lat, point_lon, warning_lat, warning_lon)

                if distance <= self.warning_radius:
                    for warning in warning_list:
                        # 提取日期部分
                        warning_date = warning.datetime.date()
                        warning_level = warning.warning_level

                        # 根据预警级别添加到对应的集合中
                        if '红' in warning_level or 'red' in warning_level.lower():
                            red_days.add(warning_date)
                        elif '橙' in warning_level or 'orange' in warning_level.lower():
                            orange_days.add(warning_date)
                        elif '黄' in warning_level or 'yellow' in warning_level.lower():
                            yellow_days.add(warning_date)
                        elif '蓝' in warning_level or 'blue' in warning_level.lower():
                            blue_days.add(warning_date)
                        else:
                            # 如果无法识别，默认计入蓝色预警
                            print(f"警告: 无法识别的预警级别 '{warning_level}'，计入蓝色预警")
                            blue_days.add(warning_date)

            # 计算每种预警的天数
            red_count = len(red_days)
            orange_count = len(orange_days)
            yellow_count = len(yellow_days)
            blue_count = len(blue_days)
            total_days = red_count + orange_count + yellow_count + blue_count

            if total_days > 0:
                # 更新结果DataFrame
                result_df.at[idx, '红色预警天数'] = red_count
                result_df.at[idx, '橙色预警天数'] = orange_count
                result_df.at[idx, '黄色预警天数'] = yellow_count
                result_df.at[idx, '蓝色预警天数'] = blue_count
                result_df.at[idx, '总预警天数'] = total_days

                # 根据总预警天数计算风险系数
                risk_factor = self._calculate_risk_factor(total_days)
                result_df.at[idx, '风险系数'] = risk_factor

                points_with_warnings += 1

        print(f"\n预警天数统计:")
        print(f"  总结构点数: {total_points}")
        print(f"  有预警的结构点数: {points_with_warnings} ({points_with_warnings/total_points*100:.1f}%)")

        # 统计每种预警天数的分布
        print(f"\n  红色预警天数分布:")
        red_distribution = result_df['红色预警天数'].value_counts().sort_index()
        for days, count in red_distribution.items():
            if days > 0:
                print(f"    {days}天: {count}个点")

        print(f"\n  橙色预警天数分布:")
        orange_distribution = result_df['橙色预警天数'].value_counts().sort_index()
        for days, count in orange_distribution.items():
            if days > 0:
                print(f"    {days}天: {count}个点")

        print(f"\n  黄色预警天数分布:")
        yellow_distribution = result_df['黄色预警天数'].value_counts().sort_index()
        for days, count in yellow_distribution.items():
            if days > 0:
                print(f"    {days}天: {count}个点")

        print(f"\n  蓝色预警天数分布:")
        blue_distribution = result_df['蓝色预警天数'].value_counts().sort_index()
        for days, count in blue_distribution.items():
            if days > 0:
                print(f"    {days}天: {count}个点")

        print(f"\n  总预警天数分布:")
        total_distribution = result_df['总预警天数'].value_counts().sort_index()
        for days, count in total_distribution.items():
            if days > 0:
                print(f"    {days}天: {count}个点")

        return result_df

    def _calculate_risk_factor(self, warning_days: int) -> float:
        """
        根据预警天数计算风险系数

        Args:
            warning_days: 预警天数

        Returns:
            风险系数
        """
        if warning_days == 0:
            return self.risk_params.get('weather_warnings_0', 1.0)
        elif 1 <= warning_days <= 10:
            return self.risk_params.get('weather_warnings_1_10', 1.05)
        elif 11 <= warning_days <= 20:
            return self.risk_params.get('weather_warnings_11_20', 1.08)
        else:  # warning_days > 20
            return self.risk_params.get('weather_warnings_above_20', 1.12)

    def update_dynamic_risk(self, structure_risk_df: pd.DataFrame, warning_stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        将气象预警风险更新到动态风险中

        Args:
            structure_risk_df: 结构点风险数据DataFrame
            warning_stats_df: 预警统计数据DataFrame

        Returns:
            更新后的DataFrame
        """
        self.log_processing_step("更新动态风险", f"结构点数量: {len(structure_risk_df)}")

        # 创建副本
        updated_df = structure_risk_df.copy()

        # 确保浮点列的类型正确（兼容 pandas 2.x 严格 dtype 检查）
        for col in ['动态风险叠加', '专项管控折减', '基础风险值', '总风险值']:
            if col in updated_df.columns:
                updated_df[col] = updated_df[col].astype(float)

        # 确保必要的列存在
        if '动态风险叠加' not in updated_df.columns:
            updated_df['动态风险叠加'] = 1.0

        if '点位描述' not in updated_df.columns:
            print("错误: 结构点风险数据中缺少'点位描述'列")
            return updated_df

        # 创建预警数据映射字典
        warning_dict = {}
        for _, row in warning_stats_df.iterrows():
            point_name = row['点位描述']
            risk_factor = row.get('风险系数', 1.0)
            warning_dict[point_name] = risk_factor

        # 更新动态风险叠加
        updated_count = 0
        for idx, row in updated_df.iterrows():
            point_name = row['点位描述']
            if point_name in warning_dict:
                current_risk = row.get('动态风险叠加', 1.0)
                weather_risk = warning_dict[point_name]

                # 应用气象风险系数
                updated_risk = current_risk * weather_risk
                updated_df.at[idx, '动态风险叠加'] = updated_risk
                updated_count += 1

        # 重新计算总风险值
        updated_df['总风险值'] = (
            updated_df['基础风险值'] *
            updated_df['动态风险叠加'] *
            updated_df['专项管控折减']
        )

        print(f"动态风险更新完成:")
        print(f"  总结构点数: {len(updated_df)}")
        print(f"  更新了 {updated_count} 个点的动态风险值")

        return updated_df

    def process_pipeline(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        执行完整的气象预警处理管道

        Returns:
            (预警统计DataFrame, 更新后的风险DataFrame)
        """
        # 1. 加载气象预警数据
        warnings = self.load_weather_warnings()

        # 2. 加载结构点数据
        structure_df = self.load_structure_points()

        # 3. 计算预警天数
        warning_stats_df = self.calculate_warning_days(warnings, structure_df)

        # 4. 保存预警统计数据
        paths_config = self.config_manager.get_paths_config()
        warning_output_path = paths_config.get('weather_warning_output', '../new结构点预警天数统计.xlsx')
        self.save_data(warning_stats_df, warning_output_path)

        # 新增：保存气象预警统计数据到数据库
        if self.db_connector and self.db_connector.connection:
            print("保存气象预警统计数据到数据库...")
            if not self.db_connector.create_point_alert_statistic_table(self.belong_date):
                print("❌ 创建气象预警统计表失败")
            else:
                self.db_connector.save_alert_statistics(warning_stats_df, self.belong_date)
        else:
            print("⚠️  数据库连接不可用，跳过数据库保存")

        # 5. 加载现有风险数据
        base_risk_path = paths_config.get('base_risk_output', '../结构点-基础风险值-动态风险值表.xlsx')
        if Path(base_risk_path).exists():
            risk_df = self.read_excel_file(base_risk_path)
            # 6. 更新动态风险
            updated_risk_df = self.update_dynamic_risk(risk_df, warning_stats_df)

            # 7. 保存更新后的风险数据
            updated_output_path = paths_config.get('weather_updated_risk_output', '../结构点-基础风险值-动态风险值表_更新.xlsx')
            self.save_data(updated_risk_df, updated_output_path)

            return warning_stats_df, updated_risk_df
        else:
            print(f"警告: 基础风险文件不存在: {base_risk_path}")
            print("将只生成预警统计数据")
            return warning_stats_df, warning_stats_df

    def load_data(self, data_source: str) -> List:
        """
        加载数据 - 抽象方法实现
        根据数据源类型加载气象预警数据或结构点数据

        Args:
            data_source: 数据源类型或路径，可以是'weather_warnings'或'structure_points'

        Returns:
            加载的数据对象
        """
        if data_source == 'weather_warnings':
            return self.load_weather_warnings()
        elif data_source == 'structure_points':
            return self.load_structure_points()
        else:
            # 假设是文件路径
            if data_source.endswith('.json'):
                return self.load_weather_warnings(data_source)
            elif data_source.endswith(('.xlsx', '.xls')):
                return self.load_structure_points(data_source)
            else:
                raise ValueError(f"不支持的数据源类型: {data_source}")

    def process(self, data: Any) -> pd.DataFrame:
        """
        处理数据 - 抽象方法实现
        根据输入数据类型进行相应处理

        Args:
            data: 输入数据，可以是气象预警列表或结构点DataFrame

        Returns:
            处理后的DataFrame
        """
        if isinstance(data, list) and len(data) > 0 and hasattr(data[0], 'warning_level'):
            # 气象预警数据，需要结构点数据来计算
            structure_df = self.load_structure_points()
            return self.calculate_warning_days(data, structure_df)
        elif isinstance(data, pd.DataFrame):
            # 结构点DataFrame，需要气象预警数据来计算
            warnings = self.load_weather_warnings()
            return self.calculate_warning_days(warnings, data)
        else:
            raise ValueError(f"不支持的数据类型: {type(data)}")

    def save_data(self, data: pd.DataFrame, output_path: str = None) -> bool:
        """
        保存处理后的数据

        Args:
            data: 要保存的DataFrame
            output_path: 输出文件路径

        Returns:
            是否保存成功
        """
        if output_path is None:
            paths_config = self.config_manager.get_paths_config()
            output_path = paths_config.get('weather_warning_output', '../new结构点预警天数统计.xlsx')

        self.log_processing_step("保存气象预警数据", f"输出路径: {output_path}")

        return self.write_excel_file(data, output_path)


if __name__ == "__main__":
    # 测试代码
    processor = WeatherDataProcessor()
    warning_stats, updated_risk = processor.process_pipeline()

    print(f"\n处理完成!")
    print(f"预警统计数据形状: {warning_stats.shape}")
    if not updated_risk.equals(warning_stats):
        print(f"更新后的风险数据形状: {updated_risk.shape}")
"""
结构点数据处理
处理结构物监测基础信息，计算基础风险值
对应原项目中的 [1]pointMesCreator.py
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from pathlib import Path

from .base_processor import BaseDataProcessor
from ..models.data_models import StructurePoint


class StructureDataProcessor(BaseDataProcessor):
    """结构点数据处理类"""

    def __init__(self):
        """初始化结构点处理器"""
        super().__init__(config_section='paths')
        self.risk_params = self.config_manager.get_risk_params()
        self.settings = self.config_manager.get_settings()

    def load_data(self, data_source: str) -> pd.DataFrame:
        """
        加载结构点数据

        Args:
            data_source: 结构物监测基础信息表路径

        Returns:
            结构点数据DataFrame
        """
        self.log_processing_step("加载结构点数据", f"数据源: {data_source}")

        # 如果数据源是配置中的键，则从配置获取路径
        if data_source in ['structure_excel', 'input_file']:
            paths_config = self.config_manager.get_paths_config()
            if data_source == 'structure_excel':
                file_path = paths_config.get('structure_excel')
            else:
                file_path = paths_config.get('input_file')
        else:
            file_path = data_source

        if not file_path or not Path(file_path).exists():
            raise FileNotFoundError(f"结构点数据文件不存在: {file_path}")

        # 读取Excel文件
        df = self.read_excel_file(file_path)

        # 验证必需的列
        required_columns = [
            '点位类型', '点位描述', '所属公司', '所属区县', '综合等级', '所属路段', '路段编号',
            '经度', '纬度', '点位桩号', '附近门架名称', '门架编码', '附近门架信息纬度',
            '附近门架信息经度', '上下行', '技术状况', '点位等级'
        ]

        if not self.validate_dataframe(df, required_columns):
            # 尝试重命名列
            df = self._standardize_column_names(df)

        # 清理数据
        df = self.clean_dataframe(df, drop_na=self.settings.get('drop_na', True))

        return df

    def _standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名

        Args:
            df: 输入DataFrame

        Returns:
            标准化后的DataFrame
        """
        column_mapping = {
            '点位类型': ['PointType', 'point_type', '类型'],
            '点位描述': ['PointDescription', 'point_description', '描述'],
            '所属公司': ['Company', 'company', '所属单位'],
            '所属区县': ['County', 'county', '区县'],
            '综合等级': ['ComprehensiveLevel', 'comprehensive_level', '综合评定', '等级'],
            '所属路段': ['RoadSection', 'road_section', '路段'],
            '路段编号': ['RoadNumber', 'road_number', '编号'],
            '经度': ['Longitude', 'longitude', 'LON', 'lon'],
            '纬度': ['Latitude', 'latitude', 'LAT', 'lat'],
            '点位桩号': ['StakeNumber', 'stake_number', '桩号'],
            '附近门架名称': ['NearbyGantryName', 'nearby_gantry_name', '门架名称'],
            '门架编码': ['GantryCode', 'gantry_code', '门架编号', '门架ID'],
            '附近门架信息纬度': ['GantryLatitude', 'gantry_latitude', '门架纬度'],
            '附近门架信息经度': ['GantryLongitude', 'gantry_longitude', '门架经度'],
            '上下行': ['Direction', 'direction', '方向']
            # 注：技术状况和点位等级根据用户要求已移除
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

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理结构点数据，计算基础风险值

        Args:
            df: 输入的结构点数据DataFrame

        Returns:
            包含基础风险值的DataFrame
        """
        self.log_processing_step("处理结构点数据", f"输入数据形状: {df.shape}")

        # 创建结果DataFrame
        result_df = df.copy()

        # 1. 计算基础风险值
        result_df['基础风险值'] = result_df['综合等级'].apply(
            lambda x: self._map_comprehensive_level_to_risk(x)
        )

        # 2. 计算基础风险归因
        result_df['基础风险归因'] = result_df.apply(
            lambda row: self._determine_risk_attribution(row), axis=1
        )

        # 3. 初始化动态风险字段
        result_df['动态风险叠加'] = 1.0  # 初始值
        result_df['专项管控折减'] = 1.0  # 初始值

        # 4. 计算总风险值（基础值 * 动态叠加 * 管控折减）
        result_df['总风险值'] = (
            result_df['基础风险值'] *
            result_df['动态风险叠加'] *
            result_df['专项管控折减']
        )

        # 5. 记录处理统计
        self._log_processing_statistics(result_df)

        return result_df

    def _map_comprehensive_level_to_risk(self, level: str) -> float:
        """
        将综合等级映射到基础风险值

        Args:
            level: 综合等级字符串

        Returns:
            基础风险值
        """
        if not isinstance(level, str):
            return np.nan

        level = level.strip()

        # 从配置获取风险映射
        level_mapping = {
            '一级': self.risk_params.get('level_1_risk', 83.0),
            '二级': self.risk_params.get('level_2_risk', 72.0),
            '三级': self.risk_params.get('level_3_risk', 55.0),
            '四级': self.risk_params.get('level_4_risk', 48.0)
        }

        return level_mapping.get(level, np.nan)

    def _determine_risk_attribution(self, row: pd.Series) -> str:
        """
        确定基础风险归因

        Args:
            row: DataFrame行数据

        Returns:
            风险归因字符串
        """
        tech_condition = str(row.get('技术状况', '')).strip()
        point_level = str(row.get('点位等级', '')).strip()

        # 处理点位等级中的括号内容（如"四级（低）"）
        if '（' in point_level:
            point_level = point_level.split('（')[0].strip()

        # 映射技术状况到对应的风险等级
        tech_to_level = {
            '1': '四级',
            '2': '三级',
            '3': '二级',
            '4': '一级',
            '1类': '四级',
            '2类': '三级',
            '3类': '二级',
            '4类': '一级'
        }

        # 获取技术状况对应的风险等级
        tech_level = tech_to_level.get(tech_condition.replace('类', ''), None)

        # 如果技术状况或点位等级无效，返回NaN
        if tech_level is None or point_level not in ['一级', '二级', '三级', '四级']:
            return np.nan

        # 定义风险等级权重（值越大风险越高）
        risk_weights = {'一级': 4, '二级': 3, '三级': 2, '四级': 1}

        tech_weight = risk_weights.get(tech_level, 0)
        point_weight = risk_weights.get(point_level, 0)

        if tech_weight > point_weight:
            return '技术状况'
        elif tech_weight < point_weight:
            return '灾害风险'
        else:
            return '技术状况与灾害风险'

    def _log_processing_statistics(self, result_df: pd.DataFrame):
        """记录处理统计信息"""
        total_points = len(result_df)
        valid_risk_points = result_df['基础风险值'].notna().sum()
        valid_attribution_points = result_df['基础风险归因'].notna().sum()

        print(f"\n结构点数据处理统计:")
        print(f"  总点数: {total_points}")
        print(f"  有效基础风险值点数: {valid_risk_points} ({valid_risk_points/total_points*100:.1f}%)")
        print(f"  有效基础风险归因点数: {valid_attribution_points} ({valid_attribution_points/total_points*100:.1f}%)")

        # 风险等级分布统计
        if '综合等级' in result_df.columns:
            level_distribution = result_df['综合等级'].value_counts()
            print(f"\n  综合等级分布:")
            for level, count in level_distribution.items():
                print(f"    {level}: {count}个点")

        # 风险归因分布统计
        if '基础风险归因' in result_df.columns:
            attribution_distribution = result_df['基础风险归因'].value_counts()
            print(f"\n  风险归因分布:")
            for attribution, count in attribution_distribution.items():
                if pd.notna(attribution):
                    print(f"    {attribution}: {count}个点")

    def save_data(self, data: pd.DataFrame, output_path: str = None) -> bool:
        """
        保存处理后的数据

        Args:
            data: 要保存的DataFrame
            output_path: 输出文件路径，如果为None则使用配置中的路径

        Returns:
            是否保存成功
        """
        if output_path is None:
            paths_config = self.config_manager.get_paths_config()
            output_path = paths_config.get('base_risk_output', '../结构点-基础风险值-动态风险值表.xlsx')

        self.log_processing_step("保存结构点数据", f"输出路径: {output_path}")

        return self.write_excel_file(data, output_path)

    def convert_to_models(self, df: pd.DataFrame) -> List[StructurePoint]:
        """
        将DataFrame转换为StructurePoint对象列表

        Args:
            df: 结构点数据DataFrame

        Returns:
            StructurePoint对象列表
        """
        structure_points = []

        for _, row in df.iterrows():
            try:
                structure_point = StructurePoint.from_dataframe_row(row)
                structure_point.base_risk_value = row.get('基础风险值')
                structure_point.base_risk_attribution = row.get('基础风险归因')
                structure_point.dynamic_risk_overlay = row.get('动态风险叠加', 1.0)
                structure_point.special_management_reduction = row.get('专项管控折减', 1.0)
                structure_point.total_risk_value = row.get('总风险值')
                structure_points.append(structure_point)
            except Exception as e:
                print(f"转换结构点数据失败 (行 {_ + 1}): {e}")

        print(f"成功转换 {len(structure_points)} 个结构点对象")
        return structure_points

    def process_pipeline(self, input_path: str = None, output_path: str = None) -> pd.DataFrame:
        """
        执行完整的结构点数据处理管道

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径

        Returns:
            处理后的DataFrame
        """
        # 1. 加载数据
        df = self.load_data(input_path or 'structure_excel')

        # 2. 处理数据
        result_df = self.process(df)

        # 3. 保存数据
        if output_path:
            self.save_data(result_df, output_path)
        else:
            self.save_data(result_df)

        return result_df


if __name__ == "__main__":
    # 测试代码
    processor = StructureDataProcessor()
    result = processor.process_pipeline()
    print(f"\n处理完成! 结果已保存")
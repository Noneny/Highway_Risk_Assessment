"""
风险计算器
将风险值转换为风险等级，生成最终评价结果
对应原项目中的 [7]value_to_level.py
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import uuid

from ..config.config_manager import get_config_manager
from ..database.database_connector import DatabaseConnector, create_database_connector_from_config


class RiskCalculator:
    """风险计算器类"""

    def __init__(self):
        """初始化风险计算器"""
        self.config_manager = get_config_manager()
        self.risk_params = self.config_manager.get_risk_params()
        self.weather_params = self.config_manager.get_weather_params()
        self.db_connector = create_database_connector_from_config(self.config_manager)

    def load_risk_data(self, input_file: str = None) -> pd.DataFrame:
        """
        加载风险数据

        Args:
            input_file: 风险数据文件路径

        Returns:
            风险数据DataFrame
        """
        if input_file is None:
            paths_config = self.config_manager.get_paths_config()
            input_file = paths_config.get('traffic_updated_risk_output',
                                          '../结构点-基础风险值-动态风险值表_更新2.xlsx')

        print(f"\n{'='*60}")
        print(f"加载风险数据: {input_file}")

        if not pd.io.common.file_exists(input_file):
            print(f"错误: 输入文件不存在: {input_file}")
            return pd.DataFrame()

        try:
            df = pd.read_excel(input_file)
            print(f"文件读取成功，共 {len(df)} 行数据")
            print(f"列名: {df.columns.tolist()}")

            # 检查必要的列
            required_columns = ['总风险值']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                print(f"警告: 缺少必要的列: {missing_columns}")
                # 尝试查找可能的列名
                possible_names = {
                    '总风险值': ['总风险值', 'point_risk', 'total_risk', '综合风险值']
                }

                for req_col, possible_list in possible_names.items():
                    if req_col in missing_columns:
                        for name in possible_list:
                            if name in df.columns:
                                df.rename(columns={name: req_col}, inplace=True)
                                print(f"  将列 '{name}' 重命名为 '{req_col}'")
                                missing_columns.remove(req_col)
                                break

            return df

        except Exception as e:
            print(f"读取文件失败: {e}")
            return pd.DataFrame()

    def classify_risk_level(self, total_risk: float) -> str:
        """
        根据总风险值分类风险等级

        Args:
            total_risk: 总风险值

        Returns:
            风险等级字符串
        """
        if pd.isna(total_risk):
            return "未知风险"

        # 获取风险阈值
        low_max = self.risk_params.get('low_risk_max', 60.0)
        medium_max = self.risk_params.get('medium_risk_max', 80.0)
        high_max = self.risk_params.get('high_risk_max', 100.0)

        if total_risk < low_max:
            return "低风险"
        elif low_max <= total_risk < medium_max:
            return "一般风险"
        elif medium_max <= total_risk < high_max:
            return "较高风险"
        else:
            return "高风险"

    def add_dynamic_risk_attribution(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加动态风险归因分析

        Args:
            df: 输入DataFrame

        Returns:
            添加了动态风险归因的DataFrame
        """
        result_df = df.copy()

        if '动态风险归因' not in result_df.columns:
            result_df['动态风险归因'] = ""

        # 检查各种风险因素
        for idx, row in result_df.iterrows():
            attribution_factors = []

            # 检查动态风险叠加值
            dynamic_risk = row.get('动态风险叠加', 1.0)
            if pd.notna(dynamic_risk) and dynamic_risk > 1.0:
                # 分析风险来源
                if dynamic_risk >= 1.3:
                    attribution_factors.append("气象与交通双重高风险")
                elif dynamic_risk >= 1.15:
                    attribution_factors.append("气象或交通高风险")
                elif dynamic_risk >= 1.05:
                    attribution_factors.append("气象或交通中等风险")
                else:
                    attribution_factors.append("轻微动态风险")

            # 检查专项管控折减
            management_reduction = row.get('专项管控折减', 1.0)
            if pd.notna(management_reduction) and management_reduction < 1.0:
                reduction_percent = (1 - management_reduction) * 100
                attribution_factors.append(f"管控折减{reduction_percent:.1f}%")

            # 如果没有识别到风险因素
            if not attribution_factors:
                attribution_factors.append("无显著动态风险")

            # 组合归因描述
            result_df.at[idx, '动态风险归因'] = "；".join(attribution_factors)

        return result_df

    def map_company_name(self, company_name: str) -> str:
        """
        映射公司名称到标准名称

        Args:
            company_name: 原始公司名称

        Returns:
            标准化的公司名称
        """
        if pd.isna(company_name):
            return ""

        company_str = str(company_name).strip()

        # 公司名称映射表
        company_mapping = {
            '渝东公司': '渝东公司',
            '万利万达公司': '万利万达公司',
            '东北公司': '东北公司',
            '东南公司': '东南公司',
            '重庆高速公路集团有限公司东北营运分公司': '东北公司',
            '重庆高速公路集团有限公司东南营运分公司': '东南公司',
            '重庆高速公路集团有限公司渝东营运分公司': '渝东公司',
            '重庆高速公路集团有限公司万利万达营运分公司': '万利万达公司'
        }

        # 精确匹配
        if company_str in company_mapping:
            return company_mapping[company_str]

        # 模糊匹配
        for original_name, mapped_name in company_mapping.items():
            if original_name in company_str:
                return mapped_name

        # 如果未匹配到，返回原值
        return company_str

    def prepare_for_database(self, df: pd.DataFrame, belong_date: str = None) -> pd.DataFrame:
        """
        准备数据用于数据库存储

        Args:
            df: 输入DataFrame
            belong_date: 数据归属日期

        Returns:
            准备好的DataFrame
        """
        if belong_date is None:
            belong_date = self.weather_params.get('belong_date', '2025-12-01')

        result_df = df.copy()

        # 确保有必要的列 - 包含所有数据库表字段对应的中文列名（根据新的映射关系）
        required_columns = [
            '点位类型', '点位描述', '所属公司', '所属区县', '综合等级', '所属路段', '路段编号',
            '经度', '纬度', '点位桩号', '附近门架名称', '门架编码', '附近门架信息纬度',
            '附近门架信息经度', '上下行', '基础风险值', '动态风险叠加', '专项管控折减', '总风险值',
            '基础风险归因', '动态风险归因', '风险等级'
        ]

        # 添加缺失的列
        for col in required_columns:
            if col not in result_df.columns:
                result_df[col] = np.nan

        # 映射公司名称
        if '所属公司' in result_df.columns:
            result_df['所属公司'] = result_df['所属公司'].apply(self.map_company_name)

        # 添加点位标识（基于关键信息生成唯一标识）
        def generate_point_id(row):
            key_parts = []
            for field in ['点位类型', '点位描述', '所属路段', '路段编号']:
                if field in row and pd.notna(row[field]):
                    key_parts.append(str(row[field]).strip())
                else:
                    key_parts.append('')
            return '_'.join(filter(None, key_parts))

        if '点位标识' not in result_df.columns:
            result_df['点位标识'] = result_df.apply(generate_point_id, axis=1)

        # 添加数据归属日期
        result_df['belong_date'] = belong_date

        return result_df

    def save_to_database(self, df: pd.DataFrame, belong_date: str = None) -> bool:
        """
        保存结果到数据库

        Args:
            df: 要保存的DataFrame
            belong_date: 数据归属日期

        Returns:
            是否保存成功
        """
        if belong_date is None:
            belong_date = self.weather_params.get('belong_date', '2025-12-01')

        if self.db_connector is None or self.db_connector.connection is None:
            print("⚠️  数据库连接不可用，跳过数据库保存")
            return False

        # 创建风险评价表
        if not self.db_connector.create_point_risk_evaluation_table(belong_date):
            print("❌ 创建风险评价表失败")
            return False

        # 准备数据
        prepared_df = self.prepare_for_database(df, belong_date)

        # 保存到数据库
        return self.db_connector.save_risk_evaluation(prepared_df, belong_date)

    def save_to_excel(self, df: pd.DataFrame, output_file: str = None) -> bool:
        """
        保存结果到Excel文件

        Args:
            df: 要保存的DataFrame
            output_file: 输出文件路径

        Returns:
            是否保存成功
        """
        if output_file is None:
            paths_config = self.config_manager.get_paths_config()
            output_file = paths_config.get('final_risk_output', '../全结构点通行风险值评价表.xlsx')

        print(f"\n{'='*60}")
        print(f"保存最终结果到Excel文件: {output_file}")

        try:
            # 确保输出目录存在
            from pathlib import Path
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存到Excel
            df.to_excel(output_file, index=False)
            print(f"✅ 文件保存成功: {output_file}")
            print(f"   数据形状: {df.shape}")
            print(f"   文件路径: {output_path.absolute()}")

            return True
        except Exception as e:
            print(f"❌ 保存Excel文件失败: {e}")
            return False

    def process_pipeline(self) -> pd.DataFrame:
        """
        执行完整的风险计算管道

        Returns:
            最终的风险评价DataFrame
        """
        print("\n" + "="*80)
        print("开始风险等级计算流程")
        print("="*80)

        # 1. 加载风险数据
        risk_df = self.load_risk_data()
        if risk_df.empty:
            print("❌ 错误: 无法加载风险数据")
            return pd.DataFrame()

        print(f"加载的风险数据形状: {risk_df.shape}")

        # 2. 计算风险等级
        print("\n计算风险等级...")
        risk_df['风险等级'] = risk_df['总风险值'].apply(self.classify_risk_level)

        # 3. 添加动态风险归因
        print("添加动态风险归因...")
        risk_df = self.add_dynamic_risk_attribution(risk_df)

        # 4. 统计风险等级分布
        self._analyze_risk_distribution(risk_df)

        # 5. 保存到Excel文件
        print("\n保存最终结果...")
        self.save_to_excel(risk_df)

        # 6. 保存到数据库
        if self.db_connector and self.db_connector.connection:
            print("\n保存到数据库...")
            belong_date = self.weather_params.get('belong_date', '2025-12-01')
            self.save_to_database(risk_df, belong_date)
        else:
            print("⚠️  数据库连接不可用，跳过数据库保存")

        print(f"\n{'='*80}")
        print("风险等级计算流程完成")
        print("="*80)

        return risk_df

    def _analyze_risk_distribution(self, df: pd.DataFrame):
        """分析风险等级分布"""
        if '风险等级' not in df.columns:
            print("警告: 无法分析风险等级分布，缺少'风险等级'列")
            return

        risk_distribution = df['风险等级'].value_counts()

        print(f"\n风险等级分布统计:")
        print(f"  总点数: {len(df)}")
        for level, count in risk_distribution.items():
            percentage = count / len(df) * 100
            print(f"  {level}: {count}个点 ({percentage:.1f}%)")

        # 按公司分析
        if '所属公司' in df.columns:
            print(f"\n按公司风险等级分布:")
            company_risks = {}
            for company, group in df.groupby('所属公司'):
                if pd.notna(company):
                    risk_counts = group['风险等级'].value_counts().to_dict()
                    company_risks[company] = risk_counts

            for company, risks in company_risks.items():
                print(f"  {company}:")
                for level, count in risks.items():
                    print(f"    {level}: {count}个点")

        # 按路段分析
        if '所属路段' in df.columns:
            print(f"\n高风险路段分析 (风险等级为'较高风险'或'高风险'):")
            high_risk_df = df[df['风险等级'].isin(['较高风险', '高风险'])]

            if not high_risk_df.empty:
                road_risks = high_risk_df['所属路段'].value_counts()
                for road, count in road_risks.items():
                    if pd.notna(road):
                        print(f"  {road}: {count}个高风险点")


if __name__ == "__main__":
    # 测试代码
    calculator = RiskCalculator()
    final_result = calculator.process_pipeline()

    if not final_result.empty:
        print(f"\n最终结果摘要:")
        print(f"  总点数: {len(final_result)}")
        print(f"  风险等级分布: {final_result['风险等级'].value_counts().to_dict()}")
    else:
        print("❌ 风险计算流程失败")

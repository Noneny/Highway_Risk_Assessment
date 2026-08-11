"""
Excel输出器
将风险评估结果保存到Excel文件
"""

import pandas as pd
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np
from src.db_config import get_belong_date

# 英文列名到中文列名的映射表
COLUMN_NAME_CN_MAP = {
    # Basic risk calculator output
    'F1': '第一风险分量F1',
    'F2': '第二风险分量F2',
    'F3': '第三风险分量F3',
    # Merged data columns
    'road_name': '路段名称',
    'peak_hour_flow': '高峰小时流量',
    'risk_value': '风险值',
    'length': '路段长度(km)',
    'design_flow': '设计流量',
    'company': '所属公司',
    'saturation': '饱和度',
    'weight': '权重',
    'route_name': '路线名称',
}


class ExcelWriter:
    """Excel输出器类"""

    def __init__(self, config_manager):
        """
        初始化Excel输出器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        # 获取输出配置
        paths_config = self.config.get('paths', {})
        self.output_dir = paths_config.get('output_dir', 'data/output')
        self.output_filename = paths_config.get('output_filename', '路网通行风险评估结果')
        self.intermediate_filename = paths_config.get('intermediate_filename', '中间计算数据')
        self.save_intermediate_data = paths_config.get('save_intermediate_data', 'False').lower() == 'true'

        print("Excel输出器初始化完成")

    @staticmethod
    def _rename_columns_to_chinese(df: pd.DataFrame) -> pd.DataFrame:
        """
        将DataFrame的英文列名映射为中文列名

        Args:
            df: 原始DataFrame

        Returns:
            列名映射后的DataFrame
        """
        rename_map = {col: COLUMN_NAME_CN_MAP[col]
                      for col in df.columns if col in COLUMN_NAME_CN_MAP}
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    def save_assessment_results(self, final_results_df: pd.DataFrame,
                                basic_risk_results: Optional[Dict[str, Any]] = None,
                                dynamic_coefficient_results: Optional[Dict[str, Any]] = None,
                                additional_coefficient_results: Optional[Dict[str, Any]] = None,
                                network_risk_results: Optional[pd.DataFrame] = None,
                                risk_attribution_results: Optional[Dict[str, Any]] = None) -> str:
        """
        保存完整的评估结果到Excel

        Args:
            final_results_df: 最终结果DataFrame
            basic_risk_results: 基础风险结果
            dynamic_coefficient_results: 动态系数结果
            additional_coefficient_results: 附加系数结果
            network_risk_results: 网络风险结果
            risk_attribution_results: 风险归因结果

        Returns:
            str: 保存的Excel文件路径
        """
        print("\n========== 保存评估结果到Excel ==========")

        try:
            # 创建输出目录
            os.makedirs(self.output_dir, exist_ok=True)

            # 生成文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"{self.output_filename}_{timestamp}.xlsx"
            excel_path = os.path.join(self.output_dir, excel_filename)

            # 创建Excel写入器，设置引擎为openpyxl
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # 1. 保存最终结果（主工作表）
                self._save_final_results_sheet(writer, final_results_df)

                # 2. 保存详细结果（多工作表）
                self._save_detailed_results_sheet(writer, final_results_df)

                # 3. 保存各阶段计算结果（如果提供了详细数据）
                if basic_risk_results:
                    self._save_basic_risk_sheet(writer, basic_risk_results)

                if dynamic_coefficient_results:
                    self._save_dynamic_coefficient_sheet(writer, dynamic_coefficient_results)

                if additional_coefficient_results:
                    self._save_additional_coefficient_sheet(writer, additional_coefficient_results)

                if network_risk_results is not None and not network_risk_results.empty:
                    self._save_network_risk_sheet(writer, network_risk_results)

                if risk_attribution_results:
                    self._save_risk_attribution_sheet(writer, risk_attribution_results)

                # 4. 保存配置信息
                self._save_config_sheet(writer)

                # 5. 保存执行摘要
                self._save_summary_sheet(writer, final_results_df)

            print(f"✅ Excel结果已保存: {excel_path}")
            print(f"   共 {len(final_results_df)} 条记录")

            return excel_path

        except Exception as e:
            print(f"❌ 保存评估结果到Excel失败: {e}")
            raise

    def save_intermediate_data(self, merged_data: pd.DataFrame,
                               company_grouped_data: Optional[pd.DataFrame] = None,
                               sorted_merged_data: Optional[pd.DataFrame] = None) -> str:
        """
        保存中间计算数据到Excel

        Args:
            merged_data: 合并后的数据
            company_grouped_data: 按公司分组的数据
            sorted_merged_data: 按指定顺序排序的数据

        Returns:
            str: 保存的Excel文件路径
        """
        if not self.save_intermediate_data:
            print("跳过中间数据保存（配置中已禁用）")
            return ""

        print("\n========== 保存中间计算数据到Excel ==========")

        try:
            # 创建输出目录
            os.makedirs(self.output_dir, exist_ok=True)

            # 生成文件名（带时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"{self.intermediate_filename}_{timestamp}.xlsx"
            excel_path = os.path.join(self.output_dir, excel_filename)

            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # 1. 保存合并后的完整数据
                if merged_data is not None and not merged_data.empty:
                    merged_data.to_excel(writer, sheet_name='合并数据', index=False)
                    print(f"  保存合并数据：{len(merged_data)} 个路段")

                # 2. 保存按公司分组的数据
                if company_grouped_data is not None and not company_grouped_data.empty:
                    company_grouped_data.to_excel(writer, sheet_name='公司分组数据', index=False)
                    print(f"  保存公司分组数据：{len(company_grouped_data)} 条记录")

                # 3. 保存按指定顺序排序的数据
                if sorted_merged_data is not None and not sorted_merged_data.empty:
                    sorted_merged_data.to_excel(writer, sheet_name='排序数据', index=False)
                    print(f"  保存排序数据：{len(sorted_merged_data)} 个路段")

                # 4. 保存数据统计信息
                if merged_data is not None and not merged_data.empty:
                    self._save_data_statistics_sheet(writer, merged_data)

            print(f"✅ 中间数据已保存: {excel_path}")
            return excel_path

        except Exception as e:
            print(f"❌ 保存中间计算数据失败: {e}")
            raise

    def _save_final_results_sheet(self, writer: pd.ExcelWriter, final_results_df: pd.DataFrame):
        """
        保存最终结果到主工作表

        Args:
            writer: Excel写入器
            final_results_df: 最终结果DataFrame
        """
        # 确保列顺序符合要求
        expected_columns = [
            '路网划分',
            '路段通行风险综合值',
            '路网密度通行风险值',
            '路网连通度通行风险值',
            '路网基础风险值',
            '平均饱和度',
            '交通流均衡性系数',
            '动态调节系数',
            '30分钟到达率',
            '1小时恢复通行率',
            '附加风险修正系数',
            '路网通行风险值',
            '风险等级',
            '主要贡献部分'
        ]

        # 重新排序列
        available_columns = [col for col in expected_columns if col in final_results_df.columns]
        if available_columns:
            final_results_df = final_results_df[available_columns]

        # 保存到Excel
        final_results_df.to_excel(writer, sheet_name='评估结果', index=False)

    def _save_detailed_results_sheet(self, writer: pd.ExcelWriter, final_results_df: pd.DataFrame):
        """
        保存详细结果到工作表

        Args:
            writer: Excel写入器
            final_results_df: 最终结果DataFrame
        """
        # 创建详细结果工作表
        if final_results_df.empty:
            return

        # 添加更多详细数据（如果有）
        detailed_df = final_results_df.copy()

        # 添加风险等级说明
        risk_levels_config = self.config.get('risk_levels', [])
        risk_level_mapping = {}
        for level_item in risk_levels_config:
            if isinstance(level_item, dict) and 'level' in level_item and 'min' in level_item:
                risk_level_mapping[level_item['level']] = f"风险值 ≥ {level_item['min']}"

        # 添加风险等级说明列
        if '风险等级' in detailed_df.columns:
            detailed_df['风险等级说明'] = detailed_df['风险等级'].map(risk_level_mapping).fillna('')

        # 保存详细结果
        detailed_df.to_excel(writer, sheet_name='详细结果', index=False)

    def _save_basic_risk_sheet(self, writer: pd.ExcelWriter, basic_risk_results: Dict[str, Any]):
        """
        保存基础风险计算结果

        Args:
            writer: Excel写入器
            basic_risk_results: 基础风险结果
        """
        if 'basic_risk_df' in basic_risk_results:
            basic_risk_df = basic_risk_results['basic_risk_df']
            if not basic_risk_df.empty:
                basic_risk_df.to_excel(writer, sheet_name='基础风险', index=False)

    def _save_dynamic_coefficient_sheet(self, writer: pd.ExcelWriter, dynamic_coefficient_results: Dict[str, Any]):
        """
        保存动态调节系数计算结果

        Args:
            writer: Excel写入器
            dynamic_coefficient_results: 动态系数结果（3元组：(dynamic_coef, avg_saturation, equilibrium_coef)）
        """
        if isinstance(dynamic_coefficient_results, tuple) and len(dynamic_coefficient_results) == 3:
            dynamic_coef, avg_saturation, equilibrium_coef = dynamic_coefficient_results

            dynamic_df = pd.DataFrame([
                {
                    '路网划分': company,
                    '动态调节系数': coef,
                    '平均饱和度': avg_saturation.get(company, 0.0),
                    '均衡性系数': equilibrium_coef.get(company, 0.0),
                }
                for company, coef in dynamic_coef.items()
            ])

            dynamic_df.to_excel(writer, sheet_name='动态系数', index=False)

    def _save_additional_coefficient_sheet(self, writer: pd.ExcelWriter, additional_coefficient_results: Dict[str, Any]):
        """
        保存附加风险修正系数计算结果

        Args:
            writer: Excel写入器
            additional_coefficient_results: 附加系数结果（2元组：(additional_coef, additional_stats)）
        """
        if isinstance(additional_coefficient_results, tuple) and len(additional_coefficient_results) == 2:
            additional_coef, additional_stats = additional_coefficient_results

            risk_thresholds = self.config.get('risk_thresholds', {})
            arrival_threshold = float(risk_thresholds.get('arrival_threshold', 0.9))
            recovery_threshold = float(risk_thresholds.get('recovery_threshold', 0.9))
            arrival_coef_high = float(risk_thresholds.get('arrival_coef_high', 0.95))
            arrival_coef_low = float(risk_thresholds.get('arrival_coef_low', 1.02))
            recovery_coef_high = float(risk_thresholds.get('recovery_coef_high', 0.95))
            recovery_coef_low = float(risk_thresholds.get('recovery_coef_low', 1.02))

            additional_df = pd.DataFrame([
                {
                    '路网划分': company,
                    '附加风险修正系数': coef,
                    '事件总数': additional_stats[company].get('total', 0),
                    '30分钟到达事件数': additional_stats[company].get('J1_actual', 0),
                    '1小时恢复事件数': additional_stats[company].get('T1_actual', 0),
                    '30分钟到达率': additional_stats[company].get('J_rate', 0),
                    '1小时恢复率': additional_stats[company].get('T_rate', 0),
                    '到达率系数': (arrival_coef_high
                                   if additional_stats[company].get('J_rate', 0) >= arrival_threshold
                                   else arrival_coef_low),
                    '恢复率系数': (recovery_coef_high
                                   if additional_stats[company].get('T_rate', 0) >= recovery_threshold
                                   else recovery_coef_low)
                }
                for company, coef in additional_coef.items()
            ])

            additional_df.to_excel(writer, sheet_name='附加系数', index=False)

    def _save_network_risk_sheet(self, writer: pd.ExcelWriter, network_risk_results: pd.DataFrame):
        """
        保存网络风险计算结果

        Args:
            writer: Excel写入器
            network_risk_results: 网络风险结果DataFrame
        """
        network_risk_results.to_excel(writer, sheet_name='网络风险', index=False)

    def _save_risk_attribution_sheet(self, writer: pd.ExcelWriter, risk_attribution_results: Dict[str, Any]):
        """
        保存风险归因分析结果

        Args:
            writer: Excel写入器
            risk_attribution_results: 风险归因结果（Dict[str, Dict[str, Any]] 或 {'attribution_df': DataFrame}）
        """
        if 'attribution_df' in risk_attribution_results:
            attribution_df = risk_attribution_results['attribution_df']
            if not attribution_df.empty:
                attribution_df.to_excel(writer, sheet_name='风险归因', index=False)
            return

        if isinstance(risk_attribution_results, dict) and len(risk_attribution_results) > 0:
            rows = []
            for company, info in risk_attribution_results.items():
                if isinstance(info, dict):
                    rows.append({
                        '路网划分': company,
                        '基础风险贡献度(%)': info.get('基础风险贡献度', 0.0),
                        '动态调节贡献度(%)': info.get('动态调节贡献度', 0.0),
                        '附加风险贡献度(%)': info.get('附加风险贡献度', 0.0),
                        '主要贡献部分': info.get('主要贡献部分', ''),
                        '贡献度描述': info.get('贡献度描述', '')
                    })
            if rows:
                attribution_df = pd.DataFrame(rows)
                attribution_df.to_excel(writer, sheet_name='风险归因', index=False)

    def _save_config_sheet(self, writer: pd.ExcelWriter):
        """
        保存配置信息到工作表

        Args:
            writer: Excel写入器
        """
        config_data = []

        # 添加数据库配置
        db_config = self.config.get('DATABASE', {})
        config_data.append({'配置项': '数据库启用', '值': db_config.get('enable', 'False')})
        config_data.append({'配置项': '数据库名称', '值': db_config.get('database', 'risk_assessment')})

        # 添加文件路径配置
        paths_config = self.config.get('paths', {})
        for key, value in paths_config.items():
            config_data.append({'配置项': f'路径配置.{key}', '值': value})

        # 添加评估周期配置
        config_data.append({'配置项': '评估周期', '值': get_belong_date()})

        # 创建DataFrame
        config_df = pd.DataFrame(config_data, columns=['配置项', '值'])

        # 保存配置
        config_df.to_excel(writer, sheet_name='配置信息', index=False)

    def _save_summary_sheet(self, writer: pd.ExcelWriter, final_results_df: pd.DataFrame):
        """
        保存执行摘要到工作表

        Args:
            writer: Excel写入器
            final_results_df: 最终结果DataFrame
        """
        summary_data = []

        # 统计记录数
        summary_data.append(['总记录数', len(final_results_df)])

        # 统计风险等级分布
        if '风险等级' in final_results_df.columns:
            risk_counts = final_results_df['风险等级'].value_counts().to_dict()
            for level, count in risk_counts.items():
                summary_data.append([f'风险等级 {level}', count])

        # 计算统计信息
        numeric_columns = ['路段通行风险综合值', '路网密度通行风险值', '路网连通度通行风险值',
                          '路网基础风险值', '平均饱和度', '交通流均衡性系数', '动态调节系数',
                          '30分钟到达率', '1小时恢复通行率', '附加风险修正系数', '路网通行风险值']

        for col in numeric_columns:
            if col in final_results_df.columns:
                col_data = final_results_df[col].dropna()
                if not col_data.empty:
                    summary_data.append([f'{col} - 最小值', f"{col_data.min():.4f}"])
                    summary_data.append([f'{col} - 最大值', f"{col_data.max():.4f}"])
                    summary_data.append([f'{col} - 平均值', f"{col_data.mean():.4f}"])
                    summary_data.append([f'{col} - 中位数', f"{col_data.median():.4f}"])

        # 创建摘要DataFrame
        summary_df = pd.DataFrame(summary_data, columns=['项目', '值'])
        summary_df.to_excel(writer, sheet_name='执行摘要', index=False)

    def _save_data_statistics_sheet(self, writer: pd.ExcelWriter, merged_data: pd.DataFrame):
        """
        保存数据统计信息

        Args:
            writer: Excel写入器
            merged_data: 合并数据
        """
        stats_data = []

        # 基本统计
        stats_data.append(['路段总数', len(merged_data)])

        # 公司分布
        if 'company' in merged_data.columns:
            company_counts = merged_data['company'].value_counts().to_dict()
            for company, count in company_counts.items():
                stats_data.append([f'{company}路段数', count])

        # 数值字段统计
        numeric_fields = ['risk_value', 'peak_hour_flow', 'weight', 'saturation']
        for field in numeric_fields:
            if field in merged_data.columns:
                col_data = merged_data[field].dropna()
                if not col_data.empty:
                    stats_data.append([f'{field} - 最小值', f"{col_data.min():.4f}"])
                    stats_data.append([f'{field} - 最大值', f"{col_data.max():.4f}"])
                    stats_data.append([f'{field} - 平均值', f"{col_data.mean():.4f}"])
                    stats_data.append([f'{field} - 标准差', f"{col_data.std():.4f}"])

        # 创建统计DataFrame
        stats_df = pd.DataFrame(stats_data, columns=['统计项目', '值'])
        stats_df.to_excel(writer, sheet_name='数据统计', index=False)

    def save_custom_dataframe(self, df: pd.DataFrame, sheet_name: str, filename: Optional[str] = None) -> str:
        """
        保存自定义DataFrame到Excel

        Args:
            df: 要保存的DataFrame
            sheet_name: 工作表名称
            filename: 自定义文件名（可选）

        Returns:
            str: 保存的文件路径
        """
        try:
            # 创建输出目录
            os.makedirs(self.output_dir, exist_ok=True)

            # 生成文件名
            if filename:
                excel_filename = f"{filename}.xlsx"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_filename = f"自定义数据_{sheet_name}_{timestamp}.xlsx"

            excel_path = os.path.join(self.output_dir, excel_filename)

            # 保存到Excel
            df.to_excel(excel_path, sheet_name=sheet_name, index=False)

            print(f"✅ 自定义数据已保存: {excel_path}")
            return excel_path

        except Exception as e:
            print(f"❌ 保存自定义数据失败: {e}")
            raise
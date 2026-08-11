"""
道路名称处理器
处理门架风险评估表，补充公司名称和路段名称信息
对应原项目中的 etc-roadname.py 脚本
"""

import pandas as pd
import os
from typing import Dict, Optional, Tuple, Any
from pathlib import Path

from ..config.config_manager import get_config_manager
from ..data_processing.base_processor import BaseDataProcessor


class RoadNameProcessor(BaseDataProcessor):
    """道路名称处理器类"""

    def __init__(self):
        """初始化道路名称处理器"""
        super().__init__(config_section='paths')

    def read_config(self) -> Dict[str, str]:
        """
        读取配置信息

        Returns:
            配置字典，包含src_file, risk_file, output_file路径
        """
        paths_config = self.config_manager.get_paths_config()

        # 获取配置中的路径，如果不存在则使用默认值
        config = {
            'src_file': paths_config.get('gantry_excel', '../东南东北渝东门架信息(1).xlsx'),
            'risk_file': paths_config.get('gantry_risk_output', '../双月门架风险评估表.xlsx'),
            'output_file': paths_config.get('roadname_output', '../双月门架风险评估表_路段信息.xlsx')
        }

        return config

    def extract_gantry_info(self, src_file: str) -> Dict[str, Dict[str, str]]:
        """
        从源数据文件提取门架信息

        Args:
            src_file: 源数据文件路径（包含门架信息）

        Returns:
            门架信息字典（门架编码 -> {门架名称, 公司名称, 路段名称}）
        """
        self.log_processing_step("提取门架信息", f"文件: {src_file}")

        # 检查文件是否存在
        if not Path(src_file).exists():
            print(f"错误: 源数据文件不存在: {src_file}")
            return {}

        try:
            # 读取源数据
            df = self.read_excel_file(src_file)
            print(f"源数据读取成功，共 {len(df)} 行数据")
            print(f"列名: {df.columns.tolist()}")
        except Exception as e:
            print(f"读取源数据失败: {e}")
            return {}

        # 检查必要的列是否存在
        required_columns = ['门架编码', '门架名称', '公司名称', '路段名称']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"警告: 源数据中缺少必要的列: {missing_columns}")
            print("尝试查找可能的列名...")

            # 尝试常见的列名变体
            column_mapping = {
                '门架编码': ['门架编码', '门架编号', '门架ID', 'GantryID', 'GANTRYID'],
                '门架名称': ['门架名称', '门架名', 'GantryName', 'GANTRY_NAME'],
                '公司名称': ['公司名称', '所属公司', '运营公司', '公司'],
                '路段名称': ['路段名称', '所属路段', '路段', 'RoadName']
            }

            for req_col, possible_names in column_mapping.items():
                if req_col in missing_columns:
                    for col in df.columns:
                        if col in possible_names:
                            df.rename(columns={col: req_col}, inplace=True)
                            print(f"  将列 '{col}' 重命名为 '{req_col}'")
                            missing_columns.remove(req_col)
                            break

            if missing_columns:
                print(f"仍有缺失列: {missing_columns}")
                return {}

        # 用于存储门架信息的字典（门架编号作为键）
        gantry_dict = {}

        # 逐行处理数据
        print("正在提取门架信息...")
        processed_count = 0
        for idx, row in df.iterrows():
            gantry_id = row['门架编码']

            # 确保门架ID不为空
            if pd.isna(gantry_id):
                continue

            # 转换为字符串并去除空格
            gantry_id = str(gantry_id).strip()

            # 如果该门架编号尚未记录，则添加信息
            if gantry_id not in gantry_dict:
                gantry_dict[gantry_id] = {
                    '门架名称': str(row['门架名称']).strip() if not pd.isna(row['门架名称']) else '',
                    '公司名称': str(row['公司名称']).strip() if not pd.isna(row['公司名称']) else '',
                    '路段名称': str(row['路段名称']).strip() if not pd.isna(row['路段名称']) else ''
                }
                processed_count += 1

                # 每处理100个门架打印一次进度
                if processed_count % 100 == 0:
                    print(f"已处理 {processed_count} 个门架...")

        print(f"门架信息提取完成，共提取 {len(gantry_dict)} 个唯一门架")

        # 显示前几个门架信息
        print("\n前5个门架信息:")
        for i, (gantry_id, info) in enumerate(list(gantry_dict.items())[:5]):
            print(f"  {gantry_id}: {info}")

        return gantry_dict

    def supplement_risk_assessment(self, risk_file: str, gantry_dict: Dict[str, Dict[str, str]],
                                  output_file: str) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        为风险评估表补充门架信息

        Args:
            risk_file: 风险评估表文件路径
            gantry_dict: 门架信息字典
            output_file: 输出文件路径

        Returns:
            (是否成功, 补充后的DataFrame)
        """
        self.log_processing_step("补充风险评估表", f"文件: {risk_file}")

        # 检查文件是否存在
        if not Path(risk_file).exists():
            print(f"错误: 风险评估文件不存在: {risk_file}")
            return False, None

        try:
            # 读取风险评估表
            risk_df = self.read_excel_file(risk_file)
            print(f"风险评估表读取成功，共 {len(risk_df)} 行数据")
            print(f"列名: {risk_df.columns.tolist()}")
        except Exception as e:
            print(f"读取风险评估表失败: {e}")
            return False, None

        # 检查必要的列是否存在
        if '门架编码' not in risk_df.columns:
            print("警告: 风险评估表中缺少'门架编码'列")
            print("尝试查找可能的列名...")

            # 尝试常见的列名
            possible_names = ['门架编码', '门架编号', '门架ID', 'GantryID', 'GANTRYID', 'etc_id', 'ETC_ID']
            for col in risk_df.columns:
                if col in possible_names:
                    risk_df.rename(columns={col: '门架编码'}, inplace=True)
                    print(f"  将列 '{col}' 重命名为 '门架编码'")
                    break

            if '门架编码' not in risk_df.columns:
                print(f"错误: 找不到门架编号列，可用列: {risk_df.columns.tolist()}")
                return False, None

        # 新增两列并初始化为空
        risk_df['公司名称'] = ''
        risk_df['路段名称'] = ''

        # 根据门架编号匹配信息
        print("正在匹配门架信息...")
        matched_count = 0
        for idx, row in risk_df.iterrows():
            gantry_id = row['门架编码']

            # 确保门架ID不为空
            if pd.isna(gantry_id):
                continue

            # 转换为字符串并去除空格
            gantry_id = str(gantry_id).strip()

            if gantry_id in gantry_dict:
                risk_df.at[idx, '公司名称'] = gantry_dict[gantry_id]['公司名称']
                risk_df.at[idx, '路段名称'] = gantry_dict[gantry_id]['路段名称']
                matched_count += 1

            # 每处理100行打印一次进度
            if (idx + 1) % 100 == 0 or (idx + 1) == len(risk_df):
                print(f"已处理 {idx + 1}/{len(risk_df)} 行，匹配 {matched_count} 个门架")

        # 计算匹配率
        match_rate = matched_count / len(risk_df) * 100 if len(risk_df) > 0 else 0
        print(f"\n门架信息匹配完成: {matched_count}/{len(risk_df)} ({match_rate:.1f}%)")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")

        return True, risk_df

    def save_roadname_output(self, df: pd.DataFrame, output_file: str) -> bool:
        """
        保存补充后的风险评估表

        Args:
            df: 补充后的DataFrame
            output_file: 输出文件路径

        Returns:
            是否保存成功
        """
        try:
            success = self.write_excel_file(df, output_file)
            if success:
                print(f"补充完成！已保存为: {output_file}")

                # 显示新表格的部分数据
                print("\n新表格前5行数据:")
                if '门架编码' in df.columns and '公司名称' in df.columns and '路段名称' in df.columns:
                    print(df[['门架编码', '公司名称', '路段名称']].head(5))
                else:
                    print("警告: 缺少部分列，显示所有列:")
                    print(df.head(5))

                # 读取并显示输出文件的统计信息
                try:
                    output_df = self.read_excel_file(output_file)
                    print("\n输出文件统计信息:")
                    print(f"总行数: {len(output_df)}")
                    print(f"有公司名称的门架数: {output_df[output_df['公司名称'] != ''].shape[0]}")
                    print(f"有路段名称的门架数: {output_df[output_df['路段名称'] != ''].shape[0]}")

                    # 公司名称分布
                    if output_df['公司名称'].nunique() > 0:
                        print("\n公司名称分布:")
                        company_counts = output_df['公司名称'].value_counts().head(10)
                        for company, count in company_counts.items():
                            if company and str(company).strip():  # 非空字符串
                                print(f"  {company}: {count} 个门架")

                    # 路段名称分布
                    if output_df['路段名称'].nunique() > 0:
                        print("\n路段名称分布:")
                        road_counts = output_df['路段名称'].value_counts().head(10)
                        for road, count in road_counts.items():
                            if road and str(road).strip():  # 非空字符串
                                print(f"  {road}: {count} 个门架")

                except Exception as e:
                    print(f"读取输出文件统计信息失败: {e}")

                return True
            else:
                print(f"保存文件失败")
                return False

        except Exception as e:
            print(f"保存文件失败: {e}")
            return False

    def process_pipeline(self) -> Tuple[bool, Optional[pd.DataFrame]]:
        """
        执行完整的道路名称处理管道

        Returns:
            (是否成功, 处理后的DataFrame)
        """
        self.log_processing_step("道路名称处理", "开始补充门架信息...")

        # 1. 读取配置
        config = self.read_config()
        print("\n配置信息:")
        print(f"源数据文件: {config['src_file']}")
        print(f"风险评估表: {config['risk_file']}")
        print(f"输出文件: {config['output_file']}")

        # 2. 提取门架信息
        gantry_info = self.extract_gantry_info(config['src_file'])
        if not gantry_info:
            print("处理失败: 无法提取门架信息")
            return False, None

        # 3. 补充风险评估表
        success, supplemented_df = self.supplement_risk_assessment(config['risk_file'], gantry_info, config['output_file'])
        if not success:
            print("处理失败: 无法补充风险评估表")
            return False, None

        # 4. 保存输出
        save_success = self.save_roadname_output(supplemented_df, config['output_file'])

        return save_success, supplemented_df

    def load_data(self, data_source: str) -> Any:
        """
        加载数据 - 抽象方法实现

        Args:
            data_source: 数据源类型，可以是'src_file'或'risk_file'

        Returns:
            加载的数据对象
        """
        config = self.read_config()

        if data_source == 'src_file':
            return self.extract_gantry_info(config['src_file'])
        elif data_source == 'risk_file':
            return self.read_excel_file(config['risk_file'])
        else:
            raise ValueError(f"不支持的数据源类型: {data_source}")

    def process(self, data: Any) -> pd.DataFrame:
        """
        处理数据 - 抽象方法实现
        为风险评估表补充门架信息

        Args:
            data: 输入数据，可以是门架信息字典和风险评估表的元组

        Returns:
            处理后的DataFrame
        """
        if isinstance(data, tuple) and len(data) == 2:
            gantry_dict, risk_df = data
            config = self.read_config()
            _, supplemented_df = self.supplement_risk_assessment(config['risk_file'], gantry_dict, config['output_file'])
            return supplemented_df
        elif isinstance(data, dict):
            # 只有门架信息，需要加载风险评估表
            gantry_dict = data
            config = self.read_config()
            success, supplemented_df = self.supplement_risk_assessment(config['risk_file'], gantry_dict, config['output_file'])
            return supplemented_df if success else pd.DataFrame()
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
            config = self.read_config()
            output_path = config['output_file']

        self.log_processing_step("保存道路名称数据", f"输出路径: {output_path}")
        return self.save_roadname_output(data, output_path)


if __name__ == "__main__":
    # 测试代码
    processor = RoadNameProcessor()
    success, result_df = processor.process_pipeline()

    if success and result_df is not None:
        print(f"\n处理成功!")
        print(f"结果数据形状: {result_df.shape}")
    else:
        print("\n处理失败")
"""
路段风险评估工作流 - 整合所有处理步骤
基于原 main.py 中的工作流程
"""
import configparser

import pandas as pd
from datetime import datetime
import os
from typing import Dict, Any, Optional, Tuple
import warnings

# 导入各个处理模块
from ..data_processing.base_risk_processor import BaseRiskProcessor
from ..data_processing.dynamic_risk_processor import DynamicRiskProcessor
from ..data_processing.extra_risk_processor import ExtraRiskProcessor
from ..risk_calculation.risk_calculator import RiskCalculator
from ..database.database_connector import DatabaseConnector
from ..config.config_manager import get_config_manager

warnings.filterwarnings('ignore')


class LineRiskWorkflow:
    """路段风险评估工作流"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化工作流

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()
        self.paths_config = self.config.get('paths', {})
        self.evaluation_config = self.config.get('evaluation', {})

        # 初始化各个处理器
        self.base_processor = BaseRiskProcessor(config_path)
        self.dynamic_processor = DynamicRiskProcessor(config_path)
        self.extra_processor = ExtraRiskProcessor(config_path)
        self.risk_calculator = RiskCalculator(config_path)
        self.db_connector = DatabaseConnector(config_path)

    def get_file_path(self, key: str, base_dir: Optional[str] = None) -> Optional[str]:
        """
        获取文件路径，支持相对路径和绝对路径

        Args:
            key: 配置文件中的路径键
            base_dir: 基准目录，用于拼接相对路径

        Returns:
            完整的文件路径
        """
        path = self.paths_config.get(key)

        if not path:
            return None

        # 如果指定了基准目录，则基于基准目录拼接
        if base_dir:
            return os.path.join(base_dir, path)

        return path

    def load_input_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str, str]:
        """
        加载所有输入数据

        Returns:
            (points_df, template_df, gantry_df, weather_df, accidents_df, etc_dir, start_date, end_date)
        """
        print(">>> 正在加载输入数据...")

        # 获取基本路径
        input_dir = self.paths_config.get('input_dir', 'data/input')
        output_dir = self.paths_config.get('output_dir', 'data/output')

        # 输入文件路径
        points_file = self.get_file_path('points_file', base_dir=input_dir)
        template_file = self.get_file_path('template_file', base_dir=input_dir)
        gantry_file = self.get_file_path('gantry_file', base_dir=input_dir)
        weather_file = self.get_file_path('weather_file', base_dir=input_dir)
        accidents_file = self.get_file_path('accidents_file', base_dir=input_dir)
        etc_data_dir = self.get_file_path('etc_data_dir', base_dir=input_dir)

        # 输出文件路径
        output_file = self.get_file_path('output_file', base_dir=output_dir)

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 加载数据
        try:
            df_points = pd.read_excel(points_file)
            print(f"✅ 已加载结构点数据: {points_file}")
        except Exception as e:
            print(f"❌ 加载结构点数据失败: {e}")
            raise

        try:
            df_template = pd.read_excel(template_file)
            print(f"✅ 已加载模板数据: {template_file}")
        except Exception as e:
            print(f"❌ 加载模板数据失败: {e}")
            raise

        try:
            df_gantry = pd.read_excel(gantry_file)
            print(f"✅ 已加载门架数据: {gantry_file}")
        except Exception as e:
            print(f"❌ 加载门架数据失败: {e}")
            raise

        try:
            df_weather = pd.read_excel(weather_file)
            print(f"✅ 已加载气象数据: {weather_file}")
        except Exception as e:
            print(f"❌ 加载气象数据失败: {e}")
            raise

        try:
            df_accidents = pd.read_excel(accidents_file)
            print(f"✅ 已加载事故数据: {accidents_file}")
        except Exception as e:
            print(f"❌ 加载事故数据失败: {e}")
            raise

        # 获取评估日期
        start_date = self.evaluation_config.get('start_date', '2025-12-01')
        end_date = self.evaluation_config.get('end_date', '2026-01-31')
        belong_date = self.evaluation_config.get('belong_date', '2025-12-01')

        print(f"评估时间范围: {start_date} 至 {end_date}")
        print(f"数据归属日期: {belong_date}")

        return (df_points, df_template, df_gantry, df_weather, df_accidents,
                etc_data_dir, start_date, end_date, belong_date, output_file)

    def run_base_risk_calculation(self, df_points: pd.DataFrame, df_template: pd.DataFrame,
                                 end_date: str) -> pd.DataFrame:
        """
        运行基础风险计算

        Args:
            df_points: 结构点数据
            df_template: 模板数据
            end_date: 结束日期（用于确定月份）

        Returns:
            基础风险计算结果
        """
        print("\n" + "=" * 50)
        print("阶段1: 基础风险计算")
        print("=" * 50)

        # 自动获取结束日期的月份
        current_month = pd.to_datetime(end_date).month
        print(f"当前评价月份: {current_month}月")

        # 获取静态风险配置
        static_cfg = self.config.get('static_risks', {})

        # 运行基础风险计算
        df_base = self.base_processor.run(
            df_points, df_template, current_month, static_cfg
        )

        if df_base is None or df_base.empty:
            raise ValueError("基础风险计算失败")

        print(f"✅ 基础风险计算完成，结果形状: {df_base.shape}")
        return df_base

    def run_dynamic_risk_calculation(self, etc_dir: str, gantry_file: str, template_file: str,
                                    weather_file: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        运行动态风险计算

        Args:
            etc_dir: ETC数据目录
            gantry_file: 门架文件路径
            template_file: 模板文件路径
            weather_file: 气象文件路径
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            动态风险计算结果
        """
        print("\n" + "=" * 50)
        print("阶段2: 动态风险计算")
        print("=" * 50)

        # 运行动态风险计算
        df_dyn = self.dynamic_processor.run(
            etc_dir, gantry_file, template_file, weather_file, start_date, end_date
        )

        if df_dyn is None or df_dyn.empty:
            print("⚠️  动态风险计算返回空结果，使用默认值")
            # 创建默认的动态风险结果
            df_template = pd.read_excel(template_file)
            df_dyn = df_template[['路段', '运行方向']].copy()
            df_dyn['动态风险_总系数'] = 1.0
            df_dyn['交通流_大车系数'] = 1.0
            df_dyn['交通流_拥挤度系数'] = 1.0
            df_dyn['交通流_纵向系数'] = 1.0
            df_dyn['气象预警_系数'] = 1.0
            df_dyn['气象预警_频次'] = 0

        print(f"✅ 动态风险计算完成，结果形状: {df_dyn.shape}")
        return df_dyn

    def run_extra_risk_calculation(self, accidents_file: str, template_file: str) -> pd.DataFrame:
        """
        运行附加风险计算

        Args:
            accidents_file: 事故文件路径
            template_file: 模板文件路径

        Returns:
            附加风险计算结果
        """
        print("\n" + "=" * 50)
        print("阶段3: 附加风险计算")
        print("=" * 50)

        # 运行附加风险计算
        df_extra = self.extra_processor.run(accidents_file, template_file)

        if df_extra is None or df_extra.empty:
            print("⚠️  附加风险计算返回空结果，使用默认值")
            # 创建默认的附加风险结果
            df_template = pd.read_excel(template_file)
            df_extra = df_template[['路段', '运行方向']].copy()
            df_extra['附加风险_总系数'] = 1.0
            df_extra['附加风险_事故系数'] = 1.0
            df_extra['附加风险_道路属性系数'] = 1.0
            df_extra['事故_每公里频数'] = 0
            df_extra['事故_赋分'] = 0

        print(f"✅ 附加风险计算完成，结果形状: {df_extra.shape}")
        return df_extra

    def run_final_assessment(self, df_base: pd.DataFrame, df_dyn: pd.DataFrame,
                            df_extra: pd.DataFrame) -> pd.DataFrame:
        """
        运行最终风险评估

        Args:
            df_base: 基础风险结果
            df_dyn: 动态风险结果
            df_extra: 附加风险结果

        Returns:
            最终风险评估结果
        """
        print("\n" + "=" * 50)
        print("阶段4: 最终风险评估")
        print("=" * 50)

        # 计算最终风险评估
        df_final = self.risk_calculator.calculate_final_risk(df_base, df_dyn, df_extra)

        # 格式化输出列
        df_final = self.risk_calculator.format_output_columns(df_final)

        print(f"✅ 最终风险评估完成，结果形状: {df_final.shape}")
        return df_final

    def save_results(self, df_final: pd.DataFrame, output_file: str, belong_date: str):
        """
        保存结果到文件和数据库

        Args:
            df_final: 最终结果DataFrame
            output_file: 输出文件路径
            belong_date: 数据归属日期
        """
        print("\n" + "=" * 50)
        print("阶段5: 结果保存")
        print("=" * 50)

        # 保存到Excel文件
        try:
            df_final.to_excel(output_file, index=False)
            print(f"✅ Excel结果已保存到: {output_file}")
        except Exception as e:
            print(f"❌ 保存Excel文件失败: {e}")
            raise

        # 生成统计信息
        self.risk_calculator.generate_statistics(df_final)

        # 输出基本信息
        print(f"\n✅ 评价完成! 结果已保存: {output_file}")
        print(f"📊 总计{len(df_final)}条路段评价记录")
        print(f"📈 输出列数: {len(df_final.columns)}列")
        print(f"📄 输出列名: {', '.join(df_final.columns.tolist())}")

        # 保存到数据库（如果启用）
        if self.db_connector.is_enabled():
            print("\n" + "=" * 50)
            print("数据库保存")
            print("=" * 50)

            # 连接到数据库
            connected = self.db_connector.connect()
            if connected:
                # 创建表（如果不存在）
                table_created = self.db_connector.create_table_if_not_exists(belong_date)

                if table_created:
                    # 保存数据到数据库
                    success = self.db_connector.save_results(df_final, belong_date)
                    if success:
                        print(f"✅ 数据已成功保存到数据库")

                # 断开数据库连接
                self.db_connector.disconnect()
        else:
            print("\n⚠️  数据库功能未启用，跳过数据库保存")

    def run(self) -> bool:
        """
        运行完整的工作流程

        Returns:
            是否成功运行
        """
        print("==========================================")
        print("      山区高速公路通行风险评价系统        ")
        print("       (重构版本 - 面向对象设计)        ")
        print("==========================================")

        try:
            # 1. 加载输入数据
            (df_points, df_template, df_gantry, df_weather, df_accidents,
             etc_dir, start_date, end_date, belong_date, output_file) = self.load_input_data()

            # 临时保存文件用于后续处理
            import tempfile
            import os
            with tempfile.TemporaryDirectory() as tmpdir:
                # 保存临时文件
                gantry_temp = os.path.join(tmpdir, 'gantry.xlsx')
                template_temp = os.path.join(tmpdir, 'template.xlsx')
                weather_temp = os.path.join(tmpdir, 'weather.xlsx')
                accidents_temp = os.path.join(tmpdir, 'accidents.xlsx')

                df_gantry.to_excel(gantry_temp, index=False)
                df_template.to_excel(template_temp, index=False)
                df_weather.to_excel(weather_temp, index=False)
                df_accidents.to_excel(accidents_temp, index=False)

                # 2. 基础风险计算
                df_base = self.run_base_risk_calculation(df_points, df_template, end_date)

                # 3. 动态风险计算
                df_dyn = self.run_dynamic_risk_calculation(etc_dir, gantry_temp, template_temp,
                                                          weather_temp, start_date, end_date)

                # 4. 附加风险计算
                df_extra = self.run_extra_risk_calculation(accidents_temp, template_temp)

            # 5. 最终风险评估
            df_final = self.run_final_assessment(df_base, df_dyn, df_extra)

            # 6. 保存结果
            self.save_results(df_final, output_file, belong_date)

            print("\n" + "=" * 50)
            print("✅ 所有处理步骤完成!")
            print("=" * 50)

            return True

        except Exception as e:
            print(f"\n❌ 工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置

        Returns:
            完整配置字典
        """
        return self.config

    def update_config(self, section: str, key: str, value: Any):
        """
        更新配置

        Args:
            section: 配置节名称
            key: 配置键
            value: 配置值
        """
        self.config_manager.update_config(section, key, value)
        self.config = self.config_manager.get_all_config()
        self.paths_config = self.config.get('paths', {})
        self.evaluation_config = self.config.get('evaluation', {})

        # 更新各个处理器的配置
        self.base_processor.update_config(section, key, value)
        self.dynamic_processor.update_config(section, key, value)
        self.extra_processor.update_config(section, key, value)
        self.risk_calculator.update_config(section, key, value)
        self.db_connector.update_config(section, key, value)

        print(f"配置已更新: {section}.{key} = {value}")


def test_workflow():
    """测试工作流"""
    import tempfile
    import os

    # 创建测试数据
    df_points = pd.DataFrame({
        '所属路段': ['G65', 'G65', 'G75', 'G75'],
        '上下行': ['上行', '下行', '上行', '下行'],
        '总风险值': [85, 70, 90, 60]
    })

    df_template = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '里程': [50, 50, 40, 40],
        '途径区域': ['垫江', '垫江', '彭水', '彭水'],
        '单向设计通行能力': [2300, 2300, 2000, 2000]
    })

    df_gantry = pd.DataFrame({
        '路段名称': ['G65', 'G65', 'G75', 'G75'],
        '上下行': ['上行', '下行', '上行', '下行'],
        '门架编码': ['G001', 'G002', 'G003', 'G004'],
        '经度': [108.5, 108.6, 109.1, 109.2],
        '纬度': [30.5, 30.6, 31.1, 31.2]
    })

    df_weather = pd.DataFrame({
        '标题': ['大风蓝色预警', '暴雨黄色预警', '大雾橙色预警'],
        '发布单位': ['垫江县气象局', '垫江县气象局', '彭水县气象局'],
        '发布时间': ['2025-12-15', '2025-12-20', '2026-01-10']
    })

    df_accidents = pd.DataFrame({
        '事故路段': ['G65', 'G65', 'G75'],
        '事故方向': ['上行', '下行', '上行'],
        '其他列': ['data1', 'data2', 'data3']
    })

    # 使用临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config_content = """
[DATABASE]
enable = False

[PATHS]
input_dir = data/input
output_dir = data/output
points_file = points.xlsx
template_file = template.xlsx
gantry_file = gantry.xlsx
weather_file = weather.xlsx
accidents_file = accidents.xlsx
etc_data_dir = etc_data
output_file = result.xlsx

[BASE_RISK]
struct_score_max_theory = 100
struct_score_target_scale = 100
weather_score_unit = 10
alignment_score_unit = 10
ice_months = 11,12,1,2,3
fog_months = 9,10,11,12,1,2,3,4,5

[DYNAMIC_RISK]
truck_types = 一型货车,二型货车,三型货车,四型货车,五型货车,六型货车
peak_hour_capacity = 3000
min_speed = 5
max_speed = 200
min_time_diff_hours = 0.001
congestion_high = 0.95
congestion_medium = 0.85
congestion_low = 0.6
large_vehicle_ratio_high_low = 0.4
large_vehicle_ratio_high_high = 0.6
large_vehicle_ratio_medium_low = 0.3
large_vehicle_ratio_medium_high = 0.7
large_vehicle_ratio_low_low = 0.2
large_vehicle_ratio_low_high = 0.8
discrete_speed_high = 40
discrete_speed_medium = 30
discrete_speed_low = 20
weather_warning_radius = 5

[EXTRA_RISK]
accident_per_km_threshold = 1.0
road_attribute_coefficient = 1.1

[RISK_LEVEL]
threshold_1 = 100
threshold_2 = 80
threshold_3 = 60
label_1 = 一级
label_2 = 二级
label_3 = 三级
label_4 = 四级
coefficient_threshold = 1.05

[MAPPINGS]
road_name_map = G65=G65,G75=G75
direction = 上行=上行,下行=下行

[EVALUATION]


[STATIC_RISKS]
ice_prone_roads = G65=1,G75=1
fog_prone_roads = G65=1,G75=1
bad_alignment_roads = G65=2,G75=1
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建临时目录和文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建必要的子目录
            input_dir = os.path.join(tmpdir, 'data/input')
            etc_dir = os.path.join(input_dir, 'etc_data')
            output_dir = os.path.join(tmpdir, 'data/output')
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(etc_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            # 保存测试文件
            points_file = os.path.join(input_dir, 'points.xlsx')
            template_file = os.path.join(input_dir, 'template.xlsx')
            gantry_file = os.path.join(input_dir, 'gantry.xlsx')
            weather_file = os.path.join(input_dir, 'weather.xlsx')
            accidents_file = os.path.join(input_dir, 'accidents.xlsx')

            df_points.to_excel(points_file, index=False)
            df_template.to_excel(template_file, index=False)
            df_gantry.to_excel(gantry_file, index=False)
            df_weather.to_excel(weather_file, index=False)
            df_accidents.to_excel(accidents_file, index=False)

            # 创建空的ETC数据目录

            # 更新配置路径
            config = configparser.ConfigParser()
            config.read(config_path, encoding='utf-8')
            config['PATHS']['input_dir'] = input_dir
            config['PATHS']['output_dir'] = output_dir
            config['PATHS']['output_file'] = os.path.join(output_dir, 'result.xlsx')

            with open(config_path, 'w', encoding='utf-8') as f:
                config.write(f)

            # 创建工作流
            workflow = LineRiskWorkflow(config_path)

            # 测试工作流
            success = workflow.run()

            if success:
                print("✅ 工作流测试成功!")
                return True
            else:
                print("❌ 工作流测试失败!")
                return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_workflow()
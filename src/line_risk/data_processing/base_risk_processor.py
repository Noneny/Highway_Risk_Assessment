"""
基础风险计算处理器
计算路段固有风险分值，采用递减聚合算法
"""

import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from .base_processor import BaseProcessor
from ..config.config_manager import get_config_manager


class BaseRiskProcessor(BaseProcessor):
    """基础风险计算器"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化基础风险计算器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()

    def run(self, df_points_raw: pd.DataFrame, df_template_raw: pd.DataFrame,
            current_month: int, static_cfg: Optional[Dict[str, Any]] = None) -> Optional[pd.DataFrame]:
        """
        执行基础风险计算

        Args:
            df_points_raw: 结构点原始数据
            df_template_raw: 路段评价模板数据
            current_month: 当前月份 (1-12)
            static_cfg: 静态风险配置，如果为None则从配置文件读取

        Returns:
            包含基础风险计算结果的数据表
        """
        print(f"正在计算基础风险... 当前月份: {current_month}月")

        # ===========================
        # 1. 预处理结构点数据 (Source)
        # ===========================
        df_points = df_points_raw.copy()

        # 获取配置
        road_map = self.config['mappings'].get('road_name_map', {})
        dir_map = self.config['mappings'].get('direction_map', {})
        base_risk_config = self.config['base_risk']
        theory_max = base_risk_config.get('struct_score_max_theory', 100.0)
        scale = base_risk_config.get('struct_score_target_scale', 100.0)

        # 映射与标准化
        df_points['标准路段'] = df_points['所属路段'].apply(
            lambda x: self.standardize_road_name(x, road_map)
        )
        df_points['标准方向'] = df_points['上下行'].map(dir_map)

        # 计算单个点的 Xi
        df_points['总风险值'] = pd.to_numeric(df_points['总风险值'], errors='coerce').fillna(0)
        df_points['Xi_point'] = (df_points['总风险值'] / theory_max) * scale

        # 聚合：按 [标准路段, 标准方向] 收集所有点
        grouped_points = df_points.groupby(['标准路段', '标准方向'])['Xi_point'].apply(list).to_dict()

        # ===========================
        # 2. 预处理模板表 (Target)
        # ===========================
        # 处理合并单元格
        df_result = self.preprocess_template(df_template_raw)

        # ===========================
        # 3. 逐行计算并收集结果
        # ===========================
        base_risks_total = []  # 存放总分 F
        fi_components = []     # 存放列表 [f1, f2, f3...]

        # 获取静态风险配置
        static_risks_config = static_cfg or self.config.get('static_risks', {})
        weather_unit = base_risk_config.get('weather_score_unit', 10.0)
        align_unit = base_risk_config.get('alignment_score_unit', 10.0)
        ice_months = base_risk_config.get('ice_months', [11, 12, 1, 2, 3])
        fog_months = base_risk_config.get('fog_months', [9, 10, 11, 12, 1, 2, 3, 4, 5])

        ice_roads = static_risks_config.get('ice_prone_roads', {})
        fog_roads = static_risks_config.get('fog_prone_roads', {})
        alignment_roads = static_risks_config.get('bad_alignment_roads', {})

        for index, row in df_result.iterrows():
            # 获取关键字段，若读取失败则跳过
            try:
                # 根据附图2，列名应该是 '路段' 和 '运行方向'
                # 如果实际Excel里列名不同，这里需要对应修改
                road_name = row['路段']
                direction = str(row['运行方向']).strip()
            except KeyError as e:
                print(f"Error: 模板表中找不到列 {e}, 请检查表头是否正确读取")
                return None

            xi_vector = []

            # --- A. 结构点风险 ---
            key = (road_name, direction)
            if key in grouped_points:
                xi_vector.extend(grouped_points[key])

            # --- B. 静态风险 (数量累加) ---
            # 1. 易结冰
            if current_month in ice_months:
                count = ice_roads.get(road_name, 0)
                if count > 0:
                    xi_vector.extend([weather_unit] * count)

            # 2. 团雾
            if current_month in fog_months:
                count = fog_roads.get(road_name, 0)
                if count > 0:
                    xi_vector.extend([weather_unit] * count)

            # 3. 不良线形
            count = alignment_roads.get(road_name, 0)
            if count > 0:
                xi_vector.extend([align_unit] * count)

            # --- 计算 ---
            # 得到 (总分, [f1, f2, f3...])
            final_f, fi_list = self.calculate_fi_vector(xi_vector)

            base_risks_total.append(final_f)
            fi_components.append(fi_list)

        # ===========================
        # 4. 动态生成结果列
        # ===========================

        # 1. 找出本批次数据中，分量列表的最大长度 (即最多有几个风险源)
        # 如果所有路段都没有风险，max_len 为 0
        max_len = max([len(comp) for comp in fi_components]) if fi_components else 0

        # 2. 生成动态列名: Fi_分量_1, Fi_分量_2 ...
        comp_cols = [f'Fi_分量_{i+1}' for i in range(max_len)]

        # 3. 填充数据
        # 将 list of lists 转换为 DataFrame，Pandas 会自动对齐，不足的填 NaN
        df_comps = pd.DataFrame(fi_components, columns=comp_cols)

        # 4. 将 NaN 填充为 0 (没数据的地方填0)
        df_comps = df_comps.fillna(0)

        # 5. 拼接到原结果表后面
        # 先把总分放进去
        df_result['基础风险_F总值'] = base_risks_total
        # 再把分量列拼上去
        df_final = pd.concat([df_result, df_comps], axis=1)

        return df_final

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
        print(f"配置已更新: {section}.{key} = {value}")


def test_base_risk_processor():
    """测试基础风险处理器"""
    import os
    import tempfile

    # 创建测试数据
    df_points = pd.DataFrame({
        '所属路段': ['G65', 'G65', 'G75', 'G75'],
        '上下行': ['上行', '下行', '上行', '下行'],
        '总风险值': [85, 70, 90, 60]
    })

    df_template = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '里程': [50, 50, 40, 40]
    })

    # 使用临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config_content = """
[DATABASE]
enable = False

[PATHS]
input_dir = data/input

[BASE_RISK]
struct_score_max_theory = 100
struct_score_target_scale = 100
weather_score_unit = 10
alignment_score_unit = 10
ice_months = 11,12,1,2,3
fog_months = 9,10,11,12,1,2,3,4,5

[MAPPINGS]
road_name_map = G65=G65,G75=G75
direction = 上行=上行,下行=下行

[STATIC_RISKS]
ice_prone_roads = G65=1,G75=1
fog_prone_roads = G65=1,G75=1
bad_alignment_roads = G65=2,G75=1
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建处理器
        processor = BaseRiskProcessor(config_path)

        # 测试12月份的基础风险计算
        result = processor.run(df_points, df_template, current_month=12)

        if result is not None:
            print("基础风险计算测试成功!")
            print(f"结果形状: {result.shape}")
            print(f"结果列名: {list(result.columns)}")
            print(f"基础风险_F总值: {list(result['基础风险_F总值'])}")
            return True
        else:
            print("基础风险计算测试失败!")
            return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_base_risk_processor()
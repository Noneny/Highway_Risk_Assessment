"""
附加风险计算处理器
计算历史事故和道路属性风险
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from .base_processor import BaseProcessor
from ..config.config_manager import get_config_manager


class ExtraRiskProcessor(BaseProcessor):
    """附加风险计算器（事故 + 道路属性）"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化附加风险计算器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()
        self.mappings = self.config.get('mappings', {})
        self.extra_config = self.config.get('extra_risk', {})

    def _load_and_clean_accidents(self, accident_file: str) -> pd.DataFrame:
        """加载并补全事故方向"""
        try:
            df = pd.read_excel(accident_file)
            df.columns = [str(c).strip() for c in df.columns]
        except Exception as e:
            print(f"Error: 读取事故表失败: {e}")
            return pd.DataFrame()

        # 获取映射关系
        direction_map = self.mappings.get('direction_map', {})
        accident_direction_map = self.mappings.get('accident_direction_map', {})
        road_name_map = self.mappings.get('road_name_map', {})
        accident_road_map = self.mappings.get('accident_road_map', {})

        # 查找可能的列名
        name_col = next((c for c in df.columns if '路段' in c or 'ROAD' in c or '路线' in c), None)
        dir_col = next((c for c in df.columns if '方向' in c or 'DIRECTION' in c or '上下行' in c or '流向' in c), None)

        if not name_col or not dir_col:
            print(f"Error: 事故表未找到路段名或方向列。现有列名: {list(df.columns)}")
            return pd.DataFrame()

        print(f"找到事故路段列: {name_col}, 事故方向列: {dir_col}")

        # 标准化方向：先尝试事故方向映射，再尝试普通方向映射
        def map_direction(dir_str):
            clean_dir = str(dir_str).strip()
            # 优先使用事故方向映射
            if clean_dir in accident_direction_map:
                return accident_direction_map[clean_dir]
            # 再尝试普通方向映射
            if clean_dir in direction_map:
                return direction_map[clean_dir]
            # 都不匹配则返回原值
            return clean_dir

        df['标准方向'] = df[dir_col].apply(map_direction)

        # 标准化路段名称：先尝试事故路段映射，再尝试普通路段映射
        def map_road_name(name):
            clean_name = str(name).strip()
            # 优先使用事故路段映射
            if clean_name in accident_road_map:
                return accident_road_map[clean_name]
            # 再尝试普通路段映射
            if clean_name in road_name_map:
                return road_name_map[clean_name]
            # 都不匹配则返回原值
            return clean_name

        df['标准路段'] = df[name_col].apply(map_road_name)

        # 调试输出
        print(f"事故方向映射后统计:")
        print(f"  原始方向值: {df[dir_col].unique()[:5]}")
        print(f"  标准方向值: {df['标准方向'].unique()[:5]}")
        print(f"事故路段映射后统计:")
        print(f"  原始路段值: {df[name_col].unique()[:5]}")
        print(f"  标准路段值: {df['标准路段'].unique()[:5]}")

        df = df.dropna(subset=['标准方向', '标准路段'])

        return df[['标准路段', '标准方向']]

    def _calculate_accident_score(self, df_accidents: pd.DataFrame,
                                 df_template: pd.DataFrame) -> pd.DataFrame:
        """计算事故指标、赋分、系数"""
        results = []

        # 1. 统计每个路段的事故数
        for idx, row in df_template.iterrows():
            road = row.get('路段', '')
            direction = row.get('运行方向', '')
            # 获取长度
            length = float(row.get('里程', row.get('路段长度', 10.0)))
            if length <= 0:
                length = 10.0  # 兜底

            count = 0
            if not df_accidents.empty:
                mask = (
                    (df_accidents['标准路段'] == road) &
                    (df_accidents['标准方向'] == direction)
                )
                count = int(mask.sum())

            acc_per_km = count / length if length > 0 else 0.0

            results.append({
                '路段': road,
                '运行方向': direction,
                '事故_频数': count,
                '事故_每公里频数': acc_per_km
            })

        df_res = pd.DataFrame(results)

        # 2. 计算均值并相对赋分
        if df_res.empty:
            return df_res

        mean_val = df_res['事故_每公里频数'].mean()
        # 防止均值为0
        if mean_val == 0:
            mean_val = 0.0001

        # 读取配置或使用默认值
        # 从配置中读取相关参数
        ratios_str = self.extra_config.get('accident_scoring_ratios', '1.5,1.2,0.8,0.5')
        scores_str = self.extra_config.get('accident_scoring_scores', '10,9,6,3,1')

        ratios = [float(x.strip()) for x in ratios_str.split(',')]
        scores = [int(x.strip()) for x in scores_str.split(',')]

        final_scores = []
        coeffs = []

        for val in df_res['事故_每公里频数']:
            score = 0
            # 逻辑对照表 2.2.3.1
            if val >= mean_val * ratios[0]:  # > +50%
                score = scores[0]  # 10
            elif val >= mean_val * ratios[1]:  # +20% ~ +50%
                score = scores[1]  # 9
            elif val >= mean_val * ratios[2]:  # -20% ~ +20%
                score = scores[2]  # 6
            elif val >= mean_val * ratios[3]:  # -50% ~ -20%
                score = scores[3]  # 3
            else:  # < -50%
                score = scores[4]  # 1

            final_scores.append(score)
            # 系数公式: (赋分 / 100) + 1
            coeffs.append(1 + (score / 100.0))

        df_res['事故_赋分'] = final_scores
        df_res['附加风险_事故系数'] = coeffs

        print(f"事故统计完成。路段均值: {mean_val:.4f} 次/公里")
        return df_res

    def _calculate_road_attribute_risk(self, df_template: pd.DataFrame) -> List[float]:
        """计算道路属性风险系数"""
        # 获取特殊道路配置
        special_attributes = self.extra_config.get('special_attributes', {})
        special_roads = special_attributes.get('tourism_or_freight_roads', [])
        special_coeff = special_attributes.get('coefficient', 1.1)

        if isinstance(special_roads, str):
            special_roads = [s.strip() for s in special_roads.split(',')]

        attr_coeffs = []
        for road in df_template['路段']:
            # 精确或模糊匹配均可，这里用包含匹配
            is_special = any(s in str(road) for s in special_roads)
            attr_coeffs.append(special_coeff if is_special else 1.0)

        return attr_coeffs

    def run(self, accident_file: str, template_file: str) -> pd.DataFrame:
        """
        执行附加风险计算

        Args:
            accident_file: 事故文件路径
            template_file: 模板文件路径

        Returns:
            附加风险计算结果
        """
        print(">>> 开始计算附加风险...")

        # 1. 模板处理
        df_templ = pd.read_excel(template_file)
        for c in ['路段', '路线', '运行方向', '里程']:
            if c in df_templ.columns:
                df_templ[c] = df_templ[c].ffill()

        # 2. 事故风险
        df_acc_clean = self._load_and_clean_accidents(accident_file)
        df_acc_risk = self._calculate_accident_score(df_acc_clean, df_templ)

        # 3. 属性风险
        attr_coeffs = self._calculate_road_attribute_risk(df_templ)

        # 4. 合并输出
        df_final = df_templ[['路段', '运行方向']].copy()

        # 拼接入事故列
        if not df_acc_risk.empty:
            df_final = pd.merge(df_final, df_acc_risk, on=['路段', '运行方向'], how='left')
        else:
            df_final['事故_每公里频数'] = 0
            df_final['事故_赋分'] = 0
            df_final['附加风险_事故系数'] = 1.0

        df_final['附加风险_道路属性系数'] = attr_coeffs

        # 计算附加总系数
        df_final['附加风险_总系数'] = (
            df_final['附加风险_事故系数'] *
            df_final['附加风险_道路属性系数']
        )

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


def test_extra_risk_processor():
    """测试附加风险处理器"""
    import tempfile
    import os

    # 创建测试数据
    df_template = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '路线': ['包茂高速', '包茂高速', '兰海高速', '兰海高速'],
        '里程': [50, 50, 40, 40]
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

[MAPPINGS]
direction = 上行=上行,下行=下行
road_name_map = G65=G65,G75=G75

[EXTRA_RISK]
# 事故评分参数
accident_scoring_ratios = 1.5,1.2,0.8,0.5
accident_scoring_scores = 10,9,6,3,1

# 特殊道路属性
special_roads = 旅游公路,货运通道,观光公路,旅游专线
special_road_coefficient = 1.05
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建临时文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 保存测试文件
            template_file = os.path.join(tmpdir, 'template.xlsx')
            accident_file = os.path.join(tmpdir, 'accident.xlsx')

            df_template.to_excel(template_file, index=False)
            df_accidents.to_excel(accident_file, index=False)

            # 创建处理器
            processor = ExtraRiskProcessor(config_path)

            # 测试附加风险计算
            result = processor.run(accident_file, template_file)

            if result is not None and not result.empty:
                print("附加风险计算测试成功!")
                print(f"结果形状: {result.shape}")
                print(f"结果列名: {list(result.columns)}")
                print(f"事故系数: {list(result['附加风险_事故系数'])}")
                return True
            else:
                print("附加风险计算测试失败!")
                return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_extra_risk_processor()
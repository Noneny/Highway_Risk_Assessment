"""
风险计算器 - 整合风险归因和最终评估逻辑
基于原 reason.py 和 main.py 中的归因逻辑
"""

import pandas as pd
import re
from typing import Dict, Any, List, Optional
from ..config.config_manager import get_config_manager


class RiskCalculator:
    """风险计算器：整合归因逻辑和最终评估"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化风险计算器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()

    def clean_risk_level(self, text: Any) -> str:
        """
        清理风险等级字符串，提取 一/二/三/四级

        Args:
            text: 原始风险等级文本

        Returns:
            清理后的风险等级字符串
        """
        if pd.isna(text):
            return "未知"

        text_str = str(text)
        match = re.search(r'([一二三四]级)', text_str)
        return match.group(1) if match else text_str

    def determine_risk_level(self, score: float) -> str:
        """
        根据P值判断风险等级

        Args:
            score: 风险总分

        Returns:
            风险等级字符串
        """
        risk_config = self.config.get('risk_level', {})
        thresholds = risk_config.get('thresholds', [100, 80, 60])
        labels = risk_config.get('labels', ['一级', '二级', '三级', '四级'])

        if score > thresholds[0]:
            return labels[0]  # 一级
        elif score > thresholds[1]:
            return labels[1]  # 二级
        elif score > thresholds[2]:
            return labels[2]  # 三级
        else:
            return labels[3]  # 四级

    def cap_total_score(self, score: float) -> float:
        """
        限制总分在合理范围内

        Args:
            score: 原始总分

        Returns:
            调整后的总分
        """
        if pd.isna(score):
            return score
        if score > 100:
            return 99 + (score - int(score))
        return score

    def get_risk_attribution(self, row: pd.Series) -> str:
        """
        获取风险归因描述

        Args:
            row: DataFrame中的一行数据

        Returns:
            风险归因描述字符串
        """
        reasons = []

        # 1. 基础风险归因逻辑 (底限阈值 > 70)
        if row.get('基础风险_F总值', 0) > 70:
            reasons.append("道路基础风险偏高")

        # 2. 各类动态系数归因逻辑 (判定系数是否大于阈值)
        threshold = self.config.get('risk_level', {}).get('coefficient_threshold', 1.05)

        # 注意：列名可能需要根据实际列名调整
        # 大车系数
        if row.get('交通流_大车系数', 1.0) > threshold:
            reasons.append("大车占比偏高")

        # 拥挤度系数
        if row.get('交通流_拥挤度系数', 1.0) >= threshold:
            reasons.append("交通状况偏拥堵")

        # 纵向稳定系数
        if row.get('交通流_纵向系数', 1.0) >= threshold:
            reasons.append("纵向稳定性偏低")

        # 气象预警系数
        if row.get('气象预警_系数', 1.0) >= threshold:
            reasons.append("气象预警偏高")

        # 事故系数
        if row.get('附加风险_事故系数', 1.0) > threshold:
            reasons.append("历史事故多发")

        # 道路属性系数
        if row.get('附加风险_道路属性系数', 1.0) >= threshold:
            reasons.append("特殊旅游公路")

        # 3. 组合最终话术
        if not reasons:
            return "运行指标正常"

        return "、".join(reasons)

    def calculate_final_risk(self, df_base: pd.DataFrame, df_dyn: pd.DataFrame,
                            df_extra: pd.DataFrame) -> pd.DataFrame:
        """
        计算最终风险评估结果

        Args:
            df_base: 基础风险结果
            df_dyn: 动态风险结果
            df_extra: 附加风险结果

        Returns:
            最终风险评估结果DataFrame
        """
        print(">>> 正在合并所有评价指标...")

        # 以基础风险表为骨架
        df_final = df_base.copy()

        # 合并动态风险 (根据路段+方向)
        # 排除重复的 key 列
        dyn_merge_cols = [c for c in df_dyn.columns if c not in ['路段', '运行方向', '路线', '途径区域']]
        if dyn_merge_cols:
            df_final = pd.merge(df_final, df_dyn[['路段', '运行方向'] + dyn_merge_cols],
                               on=['路段', '运行方向'], how='left')

        # 合并附加风险
        extra_merge_cols = [c for c in df_extra.columns if c not in ['路段', '运行方向']]
        if extra_merge_cols:
            df_final = pd.merge(df_final, df_extra[['路段', '运行方向'] + extra_merge_cols],
                               on=['路段', '运行方向'], how='left')

        # 填充缺失系数为 1.0
        coeff_cols = ['动态风险_总系数', '附加风险_总系数', '基础风险_F总值']
        for c in coeff_cols:
            if c in df_final.columns:
                df_final[c] = df_final[c].fillna(1.0 if '系数' in c else 0)

        # 计算最终风险值
        df_final['路段风险总评'] = (
            df_final.get('基础风险_F总值', 1.0) *
            df_final.get('动态风险_总系数', 1.0) *
            df_final.get('附加风险_总系数', 1.0)
        )

        # 应用总分限制
        df_final['路段风险总评'] = df_final['路段风险总评'].apply(self.cap_total_score)

        # 计算风险等级
        df_final['风险等级'] = df_final['路段风险总评'].apply(self.determine_risk_level)

        # 计算风险归因
        print(">>> 正在计算风险归因...")
        df_final['风险归因'] = df_final.apply(self.get_risk_attribution, axis=1)

        return df_final

    def format_output_columns(self, df_final: pd.DataFrame) -> pd.DataFrame:
        """
        格式化输出列，去除不需要的列

        Args:
            df_final: 最终结果DataFrame

        Returns:
            格式化后的DataFrame
        """
        # 需要排除的列
        columns_to_exclude = [
            '路线',  # 排除路线列
            '基础风险_Fi_明细',  # 排除Fi明细列
        ]

        # 添加所有Fi分量列
        fi_columns_to_exclude = [c for c in df_final.columns if 'Fi_分量' in c]

        # 添加气象预警的具体类型次数列
        weather_detail_columns = [c for c in df_final.columns if c.startswith('气象预警_') and c.endswith('_次数')]

        columns_to_exclude.extend(fi_columns_to_exclude)
        columns_to_exclude.extend(weather_detail_columns)

        # 从数据框中移除不需要的列
        for col in columns_to_exclude:
            if col in df_final.columns:
                df_final = df_final.drop(columns=[col], errors='ignore')

        # 重新排序列（可选）
        # 可以在此处定义列的顺序，这里保持原有顺序
        return df_final

    def generate_statistics(self, df_final: pd.DataFrame):
        """
        生成统计信息

        Args:
            df_final: 最终结果DataFrame
        """
        print(">>> 风险归因统计:")
        attribution_counts = df_final['风险归因'].value_counts()
        for reason, count in attribution_counts.items():
            print(f"  {reason}: {count}条 ({count / len(df_final) * 100:.1f}%)")

        # 高风险路段统计
        high_risk_df = df_final[df_final['路段风险总评'] >= 80]
        if not high_risk_df.empty:
            print(f"\n>>> 高风险路段({len(high_risk_df)}条, 占比{len(high_risk_df) / len(df_final) * 100:.1f}%):")
            for idx, row in high_risk_df.iterrows():
                print(f"  {row['路段']}({row['运行方向']}): {row['路段风险总评']:.1f}分 - {row['风险归因']}")

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


def test_risk_calculator():
    """测试风险计算器"""
    import tempfile
    import os

    # 创建测试数据
    df_base = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '基础风险_F总值': [85, 72, 90, 65]
    })

    df_dyn = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '动态风险_总系数': [1.10, 1.05, 1.08, 1.02]
    })

    df_extra = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '附加风险_总系数': [1.08, 1.02, 1.05, 1.01]
    })

    # 使用临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config_content = """
[DATABASE]
enable = False

[PATHS]
input_dir = data/input

[RISK_LEVEL]
threshold_1 = 100
threshold_2 = 80
threshold_3 = 60
label_1 = 一级
label_2 = 二级
label_3 = 三级
label_4 = 四级
coefficient_threshold = 1.05
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建风险计算器
        calculator = RiskCalculator(config_path)

        # 测试最终风险计算
        result = calculator.calculate_final_risk(df_base, df_dyn, df_extra)

        if result is not None and not result.empty:
            print("风险计算器测试成功!")
            print(f"结果形状: {result.shape}")
            print(f"结果列名: {list(result.columns)}")
            print(f"路段风险总评: {list(result['路段风险总评'])}")
            print(f"风险等级: {list(result['风险等级'])}")
            print(f"风险归因: {list(result['风险归因'])}")

            # 测试统计信息
            calculator.generate_statistics(result)

            return True
        else:
            print("风险计算器测试失败!")
            return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_risk_calculator()
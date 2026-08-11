"""
基础处理器 - 提供通用的数据处理工具函数
"""

import numpy as np
import pandas as pd
from math import radians, cos, sin, asin, sqrt
from typing import List, Tuple, Optional, Any, Dict


class BaseProcessor:
    """基础数据处理类，提供通用工具函数"""

    @staticmethod
    def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        计算两点间球面距离(km)

        Args:
            lon1: 第一点经度
            lat1: 第一点纬度
            lon2: 第二点经度
            lat2: 第二点纬度

        Returns:
            两点间距离(km)
        """
        try:
            lon1, lat1, lon2, lat2 = map(radians, [float(lon1), float(lat1), float(lon2), float(lat2)])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # 地球半径 km
            return c * r
        except:
            return 1.0  # 默认返回1km防止除零

    @staticmethod
    def find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
        """
        在DataFrame中查找存在的列名 (模糊匹配)

        Args:
            df: 数据表
            aliases: 候选列名列表

        Returns:
            实际列名 or None
        """
        clean_cols = [str(c).strip() for c in df.columns]
        for alias in aliases:
            if alias in clean_cols:
                return df.columns[clean_cols.index(alias)]
        return None

    @staticmethod
    def standardize_road_name(raw_name: str, mapping_dict: Dict[str, str]) -> Optional[str]:
        """
        路段名称标准化

        Args:
            raw_name: 原始名称
            mapping_dict: 映射字典

        Returns:
            标准化后的路段名称，如果无法标准化则返回原始名称
        """
        if not isinstance(raw_name, str):
            return None
        clean_name = raw_name.strip()
        return mapping_dict.get(clean_name, clean_name)

    @staticmethod
    def calculate_fi_vector(scores_vector: List[float]) -> Tuple[float, List[float]]:
        """
        实现递减聚合公式，返回 fi 的列表

        算法公式：
        第1个风险源：f₁ = x₁
        第i个风险源：fᵢ = (100 - Σ前i-1个f) × (xᵢ / 100)
        总分：F = Σfᵢ (上限100分)

        Args:
            scores_vector: 原始分值列表 [x1, x2, x3...]

        Returns:
            (总分F, [f1, f2, f3...])
        """
        if not scores_vector or len(scores_vector) == 0:
            return 0.0, []

        # 转换为浮点数并降序排列 (大风险优先计算)
        X = sorted([float(x) for x in scores_vector], reverse=True)

        fi_list = []
        current_sum_F = 0.0

        for i, x_i in enumerate(X):
            if i == 0:
                f_i = x_i
            else:
                # 公式: Fi = (100 - Sum(Prev)) * (Xi / 100)
                remaining_capacity = 100.0 - current_sum_F
                f_i = remaining_capacity * (x_i / 100.0)

            # 边界保护：防止总分超过100
            if current_sum_F + f_i > 100:
                f_i = 100.0 - current_sum_F

            fi_list.append(round(f_i, 4))  # 保留4位小数
            current_sum_F += f_i

            if current_sum_F >= 100:
                current_sum_F = 100.0
                break

        return current_sum_F, fi_list

    @staticmethod
    def preprocess_template(df_template: pd.DataFrame, fill_columns: List[str] = None) -> pd.DataFrame:
        """
        处理模板表：解决合并单元格读取为 NaN 的问题

        Args:
            df_template: 原始模板数据表
            fill_columns: 需要向下填充的列名列表，默认为 ['路段']

        Returns:
            处理后的数据表
        """
        df = df_template.copy()

        if fill_columns is None:
            fill_columns = ['路段']

        # 检查列是否存在，存在则执行向下填充 (Forward Fill)
        for col in fill_columns:
            if col in df.columns:
                df[col] = df[col].ffill()

        # 也可以顺手把路段名称两端的空格去掉
        if '路段' in df.columns:
            df['路段'] = df['路段'].astype(str).str.strip()

        return df

    @staticmethod
    def get_path_from_config(paths_config: Dict[str, str], key: str, default: Optional[str] = None,
                            base_dir: Optional[str] = None) -> Optional[str]:
        """
        从路径配置中获取路径，支持相对路径和绝对路径

        Args:
            paths_config: 路径配置字典
            key: 配置键
            default: 默认值
            base_dir: 基准目录，用于拼接相对路径

        Returns:
            完整的文件路径
        """
        path = paths_config.get(key, default)

        if not path:
            return None

        # 如果指定了基准目录，则基于基准目录拼接
        if base_dir:
            return os.path.join(base_dir, path)

        return path

    @staticmethod
    def ensure_directory_exists(path: str) -> None:
        """
        确保目录存在

        Args:
            path: 目录路径
        """
        import os
        os.makedirs(path, exist_ok=True)


import os

# 添加到模块的全局函数，保持与原始代码的兼容性
def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """计算两点间球面距离(km) - 兼容性函数"""
    return BaseProcessor.haversine_distance(lon1, lat1, lon2, lat2)

def find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    """在DataFrame中查找存在的列名 - 兼容性函数"""
    return BaseProcessor.find_column(df, aliases)

def standardize_road_name(raw_name: str, mapping_dict: Dict[str, str]) -> Optional[str]:
    """路段名称标准化 - 兼容性函数"""
    return BaseProcessor.standardize_road_name(raw_name, mapping_dict)

def calculate_fi_vector(scores_vector: List[float]) -> Tuple[float, List[float]]:
    """递减聚合公式计算 - 兼容性函数"""
    return BaseProcessor.calculate_fi_vector(scores_vector)
"""
数据处理基类
定义数据处理器的通用接口和功能
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np

from ..config.config_manager import get_config_manager


class BaseDataProcessor(ABC):
    """数据处理基类"""

    def __init__(self, config_section: str = None):
        """
        初始化数据处理器

        Args:
            config_section: 配置节名称，用于获取特定配置
        """
        self.config_manager = get_config_manager()
        self.config_section = config_section
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        all_config = self.config_manager.get_all_config()

        if self.config_section:
            # 获取特定配置节
            config_dict = {}
            if self.config_section == 'database':
                config_dict = all_config['database']
            elif self.config_section == 'paths':
                config_dict = all_config['paths']
            elif self.config_section == 'risk_params':
                config_dict = all_config['risk_params']
            elif self.config_section == 'weather_params':
                config_dict = all_config['weather_params']
            elif self.config_section == 'traffic_params':
                config_dict = all_config['traffic_params']
            elif self.config_section == 'settings':
                config_dict = all_config['settings']
            else:
                # 自定义配置节
                config_dict = {}
        else:
            # 获取所有配置
            config_dict = all_config

        return config_dict

    @abstractmethod
    def load_data(self, data_source: Union[str, Path, pd.DataFrame]) -> Any:
        """
        加载数据

        Args:
            data_source: 数据源，可以是文件路径或DataFrame

        Returns:
            加载的数据对象
        """
        pass

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        处理数据

        Args:
            data: 输入数据

        Returns:
            处理后的数据
        """
        pass

    @abstractmethod
    def save_data(self, data: Any, output_path: Union[str, Path]) -> bool:
        """
        保存数据

        Args:
            data: 要保存的数据
            output_path: 输出路径

        Returns:
            是否保存成功
        """
        pass

    def ensure_directory_exists(self, file_path: Union[str, Path]) -> bool:
        """
        确保文件所在目录存在

        Args:
            file_path: 文件路径

        Returns:
            目录是否存在或创建成功
        """
        path = Path(file_path)
        directory = path.parent

        if not directory.exists():
            try:
                directory.mkdir(parents=True, exist_ok=True)
                print(f"创建目录: {directory}")
                return True
            except Exception as e:
                print(f"创建目录失败: {directory}, 错误: {e}")
                return False

        return True

    def read_excel_file(self, file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        """
        读取Excel文件

        Args:
            file_path: Excel文件路径
            **kwargs: 传递给pandas.read_excel的参数

        Returns:
            DataFrame对象
        """
        try:
            df = pd.read_excel(file_path, **kwargs)
            print(f"成功读取Excel文件: {file_path}, 数据形状: {df.shape}")
            return df
        except Exception as e:
            print(f"读取Excel文件失败: {file_path}, 错误: {e}")
            raise

    def write_excel_file(self, df: pd.DataFrame, file_path: Union[str, Path], **kwargs) -> bool:
        """
        写入Excel文件

        Args:
            df: 要保存的DataFrame
            file_path: 输出文件路径
            **kwargs: 传递给pandas.to_excel的参数

        Returns:
            是否保存成功
        """
        try:
            if self.ensure_directory_exists(file_path):
                df.to_excel(file_path, index=False, **kwargs)
                print(f"成功保存Excel文件: {file_path}, 数据形状: {df.shape}")
                return True
            else:
                return False
        except Exception as e:
            print(f"保存Excel文件失败: {file_path}, 错误: {e}")
            return False

    def clean_dataframe(self, df: pd.DataFrame, drop_na: bool = True) -> pd.DataFrame:
        """
        清理DataFrame数据

        Args:
            df: 输入DataFrame
            drop_na: 是否删除全为NaN的行

        Returns:
            清理后的DataFrame
        """
        # 创建副本避免修改原数据
        cleaned_df = df.copy()

        # 删除全为NaN的行
        if drop_na:
            initial_rows = len(cleaned_df)
            cleaned_df = cleaned_df.dropna(how='all')
            dropped_rows = initial_rows - len(cleaned_df)
            if dropped_rows > 0:
                print(f"删除了 {dropped_rows} 行全为NaN的数据")

        # 重置索引
        cleaned_df = cleaned_df.reset_index(drop=True)

        return cleaned_df

    def map_risk_level(self, level: str, mapping: Dict[str, float]) -> float:
        """
        映射风险等级到数值

        Args:
            level: 风险等级字符串
            mapping: 等级到数值的映射字典

        Returns:
            风险数值，如果等级不在映射中则返回NaN
        """
        return mapping.get(level, np.nan)

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点之间的距离（公里）
        使用Haversine公式

        Args:
            lat1: 点1纬度
            lon1: 点1经度
            lat2: 点2纬度
            lon2: 点2经度

        Returns:
            距离（公里）
        """
        # 将十进制度数转换为弧度
        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)

        # Haversine公式
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))

        # 地球半径（公里）
        r = 6371.0

        return c * r

    def filter_by_distance(self, points_df: pd.DataFrame, target_lat: float, target_lon: float,
                          max_distance: float) -> pd.DataFrame:
        """
        根据距离过滤点

        Args:
            points_df: 点数据DataFrame，需包含'latitude'和'longitude'列
            target_lat: 目标纬度
            target_lon: 目标经度
            max_distance: 最大距离（公里）

        Returns:
            过滤后的DataFrame
        """
        if 'latitude' not in points_df.columns or 'longitude' not in points_df.columns:
            print("警告: DataFrame中缺少'latitude'或'longitude'列")
            return points_df

        # 计算距离
        distances = points_df.apply(
            lambda row: self.calculate_distance(row['latitude'], row['longitude'], target_lat, target_lon),
            axis=1
        )

        # 添加距离列
        points_df = points_df.copy()
        points_df['distance_km'] = distances

        # 过滤
        filtered_df = points_df[points_df['distance_km'] <= max_distance].copy()

        print(f"距离过滤: 共 {len(points_df)} 个点，过滤后剩余 {len(filtered_df)} 个点（距离 ≤ {max_distance}km）")

        return filtered_df

    def validate_dataframe(self, df: pd.DataFrame, required_columns: List[str]) -> bool:
        """
        验证DataFrame是否包含必需的列

        Args:
            df: 要验证的DataFrame
            required_columns: 必需的列名列表

        Returns:
            是否验证通过
        """
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            print(f"验证失败: DataFrame缺少以下必需的列: {missing_columns}")
            print(f"现有列: {df.columns.tolist()}")
            return False

        return True

    def log_processing_step(self, step_name: str, details: str = ""):
        """
        记录处理步骤
        过于冗杂，需要时开启

        Args:
            step_name: 步骤名称
            details: 详细信息
        """
        # print(f"\n{'='*60}")
        # print(f"处理步骤: {step_name}")
        # if details:
        #     print(f"详细信息: {details}")
        # print(f"{'='*60}")
"""
流量数据处理
处理门架交易数据，计算交通流量统计和风险
对应原项目中的 [4]newflow_prehandle.py, [5]newflow-risk-fuse.py, [6]flow_add_to_dynamic.py
"""

import glob
import os
import chardet
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import warnings

from ..data_processing.base_processor import BaseDataProcessor
from ..models.data_models import TrafficFlow, GantryRiskAssessment
from ..database.database_connector import create_database_connector_from_config
from src.db_config import get_belong_date

warnings.filterwarnings('ignore')

# 尝试导入numba用于加速计算
try:
    from numba import jit
    NUMBA_AVAILABLE = True
    print("numba已安装，将使用JIT加速计算")
except ImportError:
    NUMBA_AVAILABLE = False
    print("警告: numba未安装，使用普通Python版本的计算，性能可能较低")


class TrafficDataProcessor(BaseDataProcessor):
    """流量数据处理类"""

    def __init__(self):
        """初始化流量处理器"""
        super().__init__(config_section='paths')
        self.traffic_params = self.config_manager.get_traffic_params()
        self.risk_params = self.config_manager.get_risk_params()
        self._gantry_info_cache = None
        self.db_connector = create_database_connector_from_config(self.config_manager)
        self.etc_point_mapping = self.config_manager.get_etc_point_mapping()

    def load_gantry_info(self, gantry_file: str = None) -> Dict[str, Tuple[float, float]]:
        """
        加载门架基础信息（经纬度）

        Args:
            gantry_file: 门架信息Excel文件路径

        Returns:
            门架编码到经纬度的映射字典
        """
        if self._gantry_info_cache is not None:
            return self._gantry_info_cache

        if gantry_file is None:
            paths_config = self.config_manager.get_paths_config()
            gantry_file = paths_config.get('gantry_excel')

        self.log_processing_step("加载门架信息", f"文件: {gantry_file}")

        if not Path(gantry_file).exists():
            print(f"警告: 门架信息文件不存在: {gantry_file}")
            return {}

        try:
            gantry_df = self.read_excel_file(gantry_file)
        except Exception as e:
            print(f"读取门架信息Excel文件失败: {e}")
            return {}

        # 检查必要的列
        required_columns = ['门架编码', '经度', '纬度']
        missing_columns = [col for col in required_columns if col not in gantry_df.columns]

        if missing_columns:
            print(f"警告：缺少必要的列: {missing_columns}")
            # 尝试使用其他可能的列名
            possible_columns = {
                '门架编码': ['门架编码', 'GANTRYID', '门架ID', '门架编号'],
                '经度': ['经度', 'LONGITUDE', 'LON', 'X'],
                '纬度': ['纬度', 'LATITUDE', 'LAT', 'Y']
            }

            for req_col, possible_names in possible_columns.items():
                if req_col in missing_columns:
                    for name in possible_names:
                        if name in gantry_df.columns:
                            gantry_df.rename(columns={name: req_col}, inplace=True)
                            print(f"已将列名 '{name}' 重命名为 '{req_col}'")
                            if req_col in missing_columns:
                                missing_columns.remove(req_col)
                            break

            # 如果仍有缺失的列，尝试使用默认列名
            if missing_columns:
                print(f"仍有缺失列: {missing_columns}，尝试使用默认列名")
                if '门架编码' in missing_columns and len(gantry_df.columns) > 0:
                    gantry_df['门架编码'] = gantry_df.iloc[:, 0]
                if '经度' in missing_columns and len(gantry_df.columns) > 1:
                    gantry_df['经度'] = gantry_df.iloc[:, 1]
                if '纬度' in missing_columns and len(gantry_df.columns) > 2:
                    gantry_df['纬度'] = gantry_df.iloc[:, 2]

        # 创建门架编码到经纬度的映射字典
        gantry_info = {}
        for _, row in gantry_df.iterrows():
            if pd.notna(row['门架编码']) and pd.notna(row['经度']) and pd.notna(row['纬度']):
                gantry_id = str(row['门架编码']).strip()
                lon = float(row['经度'])
                lat = float(row['纬度'])
                gantry_info[gantry_id] = (lon, lat)

        print(f"成功提取 {len(gantry_info)} 个门架的经纬度信息")
        self._gantry_info_cache = gantry_info
        return gantry_info

    def load_traffic_data(self, data_dir: str = None) -> List[pd.DataFrame]:
        """
        加载流量数据

        Args:
            data_dir: 流量数据目录

        Returns:
            流量数据DataFrame列表
        """
        if data_dir is None:
            paths_config = self.config_manager.get_paths_config()
            data_dir = paths_config.get('traffic_data_dir')

        self.log_processing_step("加载流量数据", f"目录: {data_dir}")

        if not Path(data_dir).exists():
            print(f"警告: 流量数据目录不存在: {data_dir}")
            return []

        # 查找CSV文件
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        if not csv_files:
            print(f"警告: 目录中没有找到CSV文件: {data_dir}")
            return []

        print(f"找到 {len(csv_files)} 个CSV文件")

        data_frames = []
        for csv_file in csv_files:
            try:
                df = self._read_csv_file(csv_file)
                if df is not None and not df.empty:
                    data_frames.append(df)
                    print(f"成功读取: {Path(csv_file).name}, 数据形状: {df.shape}")
            except Exception as e:
                print(f"读取CSV文件失败: {csv_file}, 错误: {e}")

        return data_frames

    def load_traffic_data_in_chunks(self, data_dir: str = None, chunk_size: int = 50000) -> Dict[str, pd.DataFrame]:
        """
        分批加载流量数据，返回字典（文件路径 -> DataFrame）

        Args:
            data_dir: 流量数据目录
            chunk_size: 每批处理的行数

        Returns:
            文件路径到DataFrame的映射字典
        """
        if data_dir is None:
            paths_config = self.config_manager.get_paths_config()
            data_dir = paths_config.get('traffic_data_dir')

        self.log_processing_step("分批加载流量数据", f"目录: {data_dir}, 分块大小: {chunk_size}")

        if not Path(data_dir).exists():
            print(f"警告: 流量数据目录不存在: {data_dir}")
            return {}

        # 查找CSV文件
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        if not csv_files:
            print(f"警告: 目录中没有找到CSV文件: {data_dir}")
            return {}

        print(f"找到 {len(csv_files)} 个CSV文件，将进行分批处理")

        data_dict = {}
        for csv_file in csv_files:
            # 分批处理文件
            df = self._process_large_file_in_chunks(csv_file, chunk_size)
            if df is not None and not df.empty:
                data_dict[csv_file] = df
                print(f"成功分批处理: {Path(csv_file).name}, 数据形状: {df.shape}")

        return data_dict

    def _process_large_file_in_chunks(self, file_path: str, chunk_size: int = 50000) -> pd.DataFrame:
        """
        分批处理大文件（内存优化版）

        Args:
            file_path: CSV文件路径
            chunk_size: 每批处理的行数

        Returns:
            合并后的DataFrame
        """
        print(f"分批处理大文件: {file_path}，块大小: {chunk_size}")

        # 先检查文件大小
        try:
            import os
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"文件大小: {file_size_mb:.2f} MB")
        except:
            pass

        # 分批处理，直接处理每个分块，避免积累太多数据
        temp_results_dir = None
        temp_files = []
        chunk_number = 0
        total_rows = 0

        # 检测文件编码
        with open(file_path, 'rb') as f:
            rawdata = f.read(10000)  # 读取前10000字节来检测
        detected_encoding = chardet.detect(rawdata)['encoding']
        print(f"检测到文件编码: {detected_encoding}")

        # 定义尝试的编码列表
        encodings_to_try = [detected_encoding, 'utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'big5', 'latin1', 'cp1252']

        # 创建临时目录存储中间结果
        try:
            import tempfile
            temp_results_dir = tempfile.mkdtemp(prefix="traffic_chunk_")
            print(f"创建临时目录用于中间结果: {temp_results_dir}")
        except Exception as e:
            print(f"创建临时目录失败: {e}")
            temp_results_dir = None

        # 分批读取和处理CSV文件
        for encoding in encodings_to_try:
            if encoding is None:
                continue
            try:
                print(f"尝试使用 {encoding} 编码分批读取文件...")
                chunk_iterator = pd.read_csv(file_path, encoding=encoding, chunksize=chunk_size, on_bad_lines='skip')

                for chunk in chunk_iterator:
                    chunk_number += 1
                    total_rows += len(chunk)
                    print(f"处理第 {chunk_number} 批数据，大小: {len(chunk)}，累计行数: {total_rows:,}")

                    # 转换时间列
                    if '交易时间' in chunk.columns:
                        chunk['交易时间'] = pd.to_datetime(chunk['交易时间'])
                        # 只保留必要的列以减少内存
                        required_cols = ['GANTRYID', 'PASSID', '交易时间']
                        if '车型' in chunk.columns:
                            required_cols.append('车型')
                        if set(required_cols).issubset(chunk.columns):
                            chunk = chunk[required_cols].copy()
                            chunk['GANTRYID'] = chunk['GANTRYID'].astype(str)
                            chunk['PASSID'] = chunk['PASSID'].astype(str)
                        else:
                            print(f"警告: 第 {chunk_number} 批数据缺少必要的列，跳过")
                            continue
                    else:
                        print(f"警告: 第 {chunk_number} 批数据缺少'交易时间'列，跳过")
                        continue

                    # 将分块保存到临时文件，避免内存积累
                    if temp_results_dir:
                        temp_file = os.path.join(temp_results_dir, f"chunk_{chunk_number:04d}.parquet")
                        try:
                            chunk.to_parquet(temp_file, compression='snappy')
                            temp_files.append(temp_file)
                            print(f"保存分块到临时文件: {temp_file}")
                        except Exception as e:
                            print(f"保存临时文件失败: {e}")
                            # 如果保存失败，直接处理这个分块
                            temp_files.append(chunk)
                    else:
                        temp_files.append(chunk)

                    # 定期清理内存
                    del chunk

                    # 每处理10批数据就检查一下内存使用
                    if chunk_number % 10 == 0:
                        import gc
                        gc.collect()
                        print(f"已处理 {chunk_number} 批数据，累计 {total_rows:,} 行")

                # 如果成功读取，跳出循环
                print(f"文件读取完成，共 {chunk_number} 批，总计 {total_rows:,} 行")
                break
            except (UnicodeDecodeError, LookupError, pd.errors.ParserError) as e:
                print(f"使用 {encoding} 编码读取失败: {e}")
                continue
            except Exception as e:
                print(f"使用 {encoding} 编码读取时发生其他错误: {e}")
                continue

        # 如果没有数据，返回空DataFrame
        if not temp_files:
            print("没有读取到有效数据")
            return pd.DataFrame()

        print(f"开始合并 {len(temp_files)} 个数据分块...")

        # 合并所有分块数据，不进行速度计算
        all_chunks = []
        processed_chunks = 0

        for i, chunk_item in enumerate(temp_files):
            processed_chunks += 1
            print(f"读取分块 {processed_chunks}/{len(temp_files)}...")

            try:
                # 从临时文件或直接使用数据
                if isinstance(chunk_item, str) and os.path.exists(chunk_item):
                    # 从临时文件读取
                    chunk_df = pd.read_parquet(chunk_item)
                else:
                    # 已经是DataFrame
                    chunk_df = chunk_item

                # 只保留必要的列：GANTRYID, PASSID, 交易时间（及车型，如果存在）
                required_cols = ['GANTRYID', 'PASSID', '交易时间']
                if '车型' in chunk_df.columns:
                    required_cols.append('车型')
                if set(required_cols).issubset(chunk_df.columns):
                    chunk_df = chunk_df[required_cols].copy()
                    # 确保数据类型正确
                    chunk_df['GANTRYID'] = chunk_df['GANTRYID'].astype(str)
                    chunk_df['PASSID'] = chunk_df['PASSID'].astype(str)
                    chunk_df['交易时间'] = pd.to_datetime(chunk_df['交易时间'])

                    all_chunks.append(chunk_df)
                else:
                    print(f"警告: 分块 {processed_chunks} 缺少必要的列，跳过")

                # 清理内存
                del chunk_df
                if processed_chunks % 5 == 0:
                    import gc
                    gc.collect()

            except Exception as e:
                print(f"读取分块 {processed_chunks} 失败: {e}")

        # 清理临时文件
        if temp_results_dir and os.path.exists(temp_results_dir):
            try:
                import shutil
                shutil.rmtree(temp_results_dir)
                print(f"清理临时目录: {temp_results_dir}")
            except Exception as e:
                print(f"清理临时目录失败: {e}")

        # 合并所有分块
        if all_chunks:
            final_result = pd.concat(all_chunks, ignore_index=True)
            print(f"数据合并完成，最终结果大小: {final_result.shape}")
            print(f"数据列名: {final_result.columns.tolist()}")
            return final_result
        else:
            print("警告: 没有有效的数据分块")
            return pd.DataFrame()

    def _read_csv_file(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        读取CSV文件（支持多种编码）

        Args:
            file_path: CSV文件路径

        Returns:
            DataFrame对象
        """
        # 检测文件编码
        with open(file_path, 'rb') as f:
            rawdata = f.read(10000)
        detected_encoding = chardet.detect(rawdata)['encoding']

        # 定义尝试的编码列表
        encodings_to_try = [detected_encoding, 'utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'big5', 'latin1', 'cp1252']

        for encoding in encodings_to_try:
            if encoding is None:
                continue
            try:
                df = pd.read_csv(file_path, encoding=encoding, on_bad_lines='skip')
                print(f"成功使用 {encoding} 编码读取文件: {file_path}")
                return df
            except (UnicodeDecodeError, LookupError, pd.errors.ParserError) as e:
                continue
            except Exception as e:
                print(f"使用 {encoding} 编码读取时发生其他错误: {e}")
                continue

        # 如果所有编码都失败，尝试不指定编码
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip')
            print(f"成功不指定编码读取文件: {file_path}")
            return df
        except Exception as e:
            print(f"所有编码尝试都失败: {file_path}, 错误: {e}")
            return None

    def _haversine_distance(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """
        计算两点之间的距离（公里）

        Args:
            lon1: 点1经度
            lat1: 点1纬度
            lon2: 点2经度
            lat2: 点2纬度

        Returns:
            距离（公里）
        """
        if NUMBA_AVAILABLE:
            return self._haversine_distance_numba(lon1, lat1, lon2, lat2)
        else:
            return self._haversine_distance_python(lon1, lat1, lon2, lat2)

    @staticmethod
    def _haversine_distance_python(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Python版本的Haversine距离计算"""
        # 将十进制度数转化为弧度
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # Haversine公式
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        r = 6371  # 地球半径，单位公里
        return c * r

    @staticmethod
    @jit(nopython=True) if NUMBA_AVAILABLE else lambda func: func
    def _haversine_distance_numba(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """使用numba加速的Haversine距离计算"""
        # 将十进制度数转化为弧度
        lon1_r = radians(lon1)
        lat1_r = radians(lat1)
        lon2_r = radians(lon2)
        lat2_r = radians(lat2)

        # Haversine公式
        dlon = lon2_r - lon1_r
        dlat = lat2_r - lat1_r
        a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        r = 6371  # 地球半径，单位公里
        return c * r

    def _haversine_distance_vectorized(self, lon1_arr: np.ndarray, lat1_arr: np.ndarray,
                                       lon2_arr: np.ndarray, lat2_arr: np.ndarray) -> np.ndarray:
        """
        向量化计算距离（极致内存优化版）- 向后兼容方法
        现在使用分批版本的方法
        """
        return self._haversine_distance_vectorized_batch(lon1_arr, lat1_arr, lon2_arr, lat2_arr)

    def _haversine_distance_vectorized_batch(self, lon1_arr: np.ndarray, lat1_arr: np.ndarray,
                                            lon2_arr: np.ndarray, lat2_arr: np.ndarray) -> np.ndarray:
        """
        向量化计算距离（极致内存优化版）

        Args:
            lon1_arr: 起点经度数组
            lat1_arr: 起点纬度数组
            lon2_arr: 终点经度数组
            lat2_arr: 终点纬度数组

        Returns:
            距离数组（公里）
        """
        # 检查输入数组形状
        n = len(lon1_arr)
        if n != len(lat1_arr) or n != len(lon2_arr) or n != len(lat2_arr):
            raise ValueError("输入数组长度不一致")

        # 创建结果数组（使用float32节省内存）
        distances = np.full(n, np.nan, dtype=np.float32)

        # 使用批量处理，避免一次性处理太多数据
        batch_size = 100000  # 每批处理10万条记录
        num_batches = (n + batch_size - 1) // batch_size

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, n)

            # 提取当前批次数据
            batch_lon1 = lon1_arr[start_idx:end_idx]
            batch_lat1 = lat1_arr[start_idx:end_idx]
            batch_lon2 = lon2_arr[start_idx:end_idx]
            batch_lat2 = lat2_arr[start_idx:end_idx]

            # 创建布尔掩码，过滤掉NaN值
            mask = ~(np.isnan(batch_lon1) | np.isnan(batch_lat1) |
                     np.isnan(batch_lon2) | np.isnan(batch_lat2))

            if mask.any():
                # 提取有效数据
                valid_lon1 = batch_lon1[mask]
                valid_lat1 = batch_lat1[mask]
                valid_lon2 = batch_lon2[mask]
                valid_lat2 = batch_lat2[mask]

                if NUMBA_AVAILABLE:
                    # 使用numba加速计算
                    valid_distances = np.zeros(len(valid_lon1), dtype=np.float32)
                    for i in range(len(valid_lon1)):
                        valid_distances[i] = self._haversine_distance_numba(
                            valid_lon1[i], valid_lat1[i], valid_lon2[i], valid_lat2[i]
                        )
                else:
                    # 普通Python版本，使用numpy的向量化操作
                    # 将角度转换为弧度
                    lon1_rad = np.radians(valid_lon1)
                    lat1_rad = np.radians(valid_lat1)
                    lon2_rad = np.radians(valid_lon2)
                    lat2_rad = np.radians(valid_lat2)

                    # Haversine公式
                    dlon = lon2_rad - lon1_rad
                    dlat = lat2_rad - lat1_rad
                    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
                    c = 2 * np.arcsin(np.sqrt(a))
                    r = 6371  # 地球半径，单位公里

                    valid_distances = c * r

                # 将结果放回对应位置
                distances[start_idx:end_idx][mask] = valid_distances.astype(np.float32)

            # 每处理5批数据输出一次进度
            if batch_idx % 5 == 0:
                print(f"距离计算进度: {batch_idx+1}/{num_batches}批")

        return distances

    def process_traffic_data_optimized(self, df: pd.DataFrame, gantry_info: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
        """
        优化后的车辆速度计算函数（基于[4]newflow_prehandle.py）

        Args:
            df: 原始流量数据DataFrame
            gantry_info: 门架经纬度信息

        Returns:
            处理后的DataFrame（包含速度信息）
        """
        self.log_processing_step("优化处理流量数据", f"原始数据形状: {df.shape}")

        # 调试：打印输入数据列名
        print(f"调试-输入数据列名: {df.columns.tolist()}")
        print(f"调试-输入数据形状: {df.shape}")
        if not df.empty and 'GANTRYID' in df.columns:
            print(f"调试-输入数据前几行GANTRYID值: {df['GANTRYID'].head().tolist()}")

        # 检查必要的列 - 优化版本只需要这些列
        required_columns = ['GANTRYID', 'PASSID', '交易时间']
        if not self.validate_dataframe(df, required_columns):
            print(f"错误: 流量数据缺少必要的列。现有列: {df.columns.tolist()}")
            return pd.DataFrame()

        # 如果数据量太大，使用分批处理
        total_rows = len(df)
        chunk_size = self.traffic_params.get('chunksize', 50000)

        # 自动检测是否需要分批处理
        auto_chunk_threshold_mb = self.traffic_params.get('auto_chunk_threshold_mb', 100)
        # 估算内存使用：每行大约200字节
        estimated_memory_mb = (total_rows * 200) / (1024 * 1024)
        use_chunks = self.traffic_params.get('use_chunks', True) or estimated_memory_mb > auto_chunk_threshold_mb

        if use_chunks and total_rows > chunk_size * 2:
            print(f"数据量较大（{total_rows}行，估计占用{estimated_memory_mb:.1f}MB），使用分批处理，块大小: {chunk_size}")
            return self._process_traffic_in_chunks(df, gantry_info, chunk_size)
        else:
            print(f"数据量适中（{total_rows}行），使用单批处理")
            return self._process_traffic_single_batch(df, gantry_info)

    def _process_traffic_single_batch(self, df: pd.DataFrame, gantry_info: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
        """
        单批处理流量数据（内存优化版）
        """
        # 1. 预处理：只保留必要的列，减少内存占用
        required_cols = ['PASSID', 'GANTRYID', '交易时间']
        # 保留车型列用于大型车比例计算（参考[4]newflow_prehandle.py）
        if '车型' in df.columns:
            required_cols.append('车型')
        if not set(required_cols).issubset(df.columns):
            print("数据框缺少必要的列")
            return pd.DataFrame()

        # 使用视图而不是副本，减少内存使用
        df = df[required_cols].copy()  # 需要副本因为会修改列类型

        # 优化数据类型
        df['GANTRYID'] = df['GANTRYID'].astype('category')  # 使用分类类型减少内存
        df['PASSID'] = df['PASSID'].astype('category')

        # 2. 按车辆ID分组，并按时间排序
        self.log_processing_step("优化处理", "按车辆ID分组排序...")
        df = df.sort_values(['PASSID', '交易时间']).reset_index(drop=True)

        # 3. 使用shift快速获取下一门架信息
        self.log_processing_step("优化处理", "获取下一门架信息...")
        df['下一门架ID'] = df.groupby('PASSID')['GANTRYID'].shift(-1)
        df['下一门架时间'] = df.groupby('PASSID')['交易时间'].shift(-1)

        # 4. 过滤掉没有下一门架的记录
        mask = df['下一门架ID'].notna() & df['下一门架时间'].notna()
        df = df[mask].copy()

        print(f"有效记录数: {len(df)}")

        if len(df) == 0:
            print("没有有效的连续门架记录")
            return pd.DataFrame()

        # 5. 批量添加经纬度信息（避免重复映射）
        self.log_processing_step("优化处理", "批量添加经纬度信息...")

        # 创建经纬度映射数组（使用float32减少内存）
        gantry_ids = list(gantry_info.keys())
        gantry_lons = np.array([gantry_info[gid][0] for gid in gantry_ids], dtype=np.float32)
        gantry_lats = np.array([gantry_info[gid][1] for gid in gantry_ids], dtype=np.float32)

        # 创建映射字典（使用float32）
        lon_map = dict(zip(gantry_ids, gantry_lons))
        lat_map = dict(zip(gantry_ids, gantry_lats))

        # 批量映射，使用float32类型
        df['当前门架_经度'] = df['GANTRYID'].map(lon_map).astype(np.float32)
        df['当前门架_纬度'] = df['GANTRYID'].map(lat_map).astype(np.float32)
        df['下一门架_经度'] = df['下一门架ID'].map(lon_map).astype(np.float32)
        df['下一门架_纬度'] = df['下一门架ID'].map(lat_map).astype(np.float32)

        # 6. 过滤掉经纬度为空的记录
        mask_coords = (df['当前门架_经度'].notna() &
                       df['当前门架_纬度'].notna() &
                       df['下一门架_经度'].notna() &
                       df['下一门架_纬度'].notna())

        df = df[mask_coords].copy()

        print(f"有有效经纬度的记录数: {len(df)}")

        if len(df) == 0:
            print("没有有效的经纬度信息")
            return pd.DataFrame()

        # 7. 向量化计算时间差
        self.log_processing_step("优化处理", "计算时间差...")
        df['时间差_小时'] = (df['下一门架时间'] - df['交易时间']).dt.total_seconds() / 3600
        df['时间差_小时'] = df['时间差_小时'].astype(np.float32)

        # 过滤时间差过小或过大的记录
        min_time_diff = self.traffic_params.get('min_time_diff_hours', 0.001)
        max_time_diff = self.traffic_params.get('max_time_diff_hours', 24)

        time_mask = (df['时间差_小时'] > min_time_diff) & (df['时间差_小时'] < max_time_diff)
        df = df[time_mask].copy()

        print(f"时间差合理的记录数: {len(df)}")

        if len(df) == 0:
            print("没有时间差合理的记录")
            return pd.DataFrame()

        # 8. 批量计算距离（向量化）- 内存优化版
        self.log_processing_step("优化处理", "批量计算距离...")

        # 使用分批计算，避免一次性创建大数组
        n = len(df)
        batch_size = 100000  # 每批计算10万条记录

        # 创建结果数组
        distances = np.zeros(n, dtype=np.float32)

        for i in range(0, n, batch_size):
            end_idx = min(i + batch_size, n)
            batch_size_actual = end_idx - i

            # 提取当前批次数据（使用视图而不是副本）
            batch_lon1 = df['当前门架_经度'].iloc[i:end_idx].values.astype(np.float64)
            batch_lat1 = df['当前门架_纬度'].iloc[i:end_idx].values.astype(np.float64)
            batch_lon2 = df['下一门架_经度'].iloc[i:end_idx].values.astype(np.float64)
            batch_lat2 = df['下一门架_纬度'].iloc[i:end_idx].values.astype(np.float64)

            # 计算当前批次的距离
            batch_distances = self._haversine_distance_vectorized_batch(
                batch_lon1, batch_lat1, batch_lon2, batch_lat2
            )

            distances[i:end_idx] = batch_distances

            # 清理当前批次的内存
            del batch_lon1, batch_lat1, batch_lon2, batch_lat2, batch_distances

            # 每处理5批输出一次进度
            if (i // batch_size) % 5 == 0:
                print(f"距离计算进度: {end_idx}/{n} ({end_idx/n*100:.1f}%)")

        df['距离_km'] = distances

        # 过滤距离为0的记录
        df = df[df['距离_km'] > 0].copy()

        if len(df) == 0:
            print("没有有效的距离记录")
            return pd.DataFrame()

        # 9. 批量计算速度（使用float32）
        self.log_processing_step("优化处理", "批量计算速度...")
        df['速度_km_h'] = (df['距离_km'] / df['时间差_小时']).astype(np.float32)

        # 10. 过滤不合理速度
        self.log_processing_step("优化处理", "过滤不合理速度...")
        min_speed = self.traffic_params.get('min_speed', 5)
        max_speed = self.traffic_params.get('max_speed', 200)

        speed_mask = (df['速度_km_h'] >= min_speed) & (df['速度_km_h'] <= max_speed)
        df = df[speed_mask].copy()

        print(f"速度合理的记录数: {len(df)}")

        # 11. 只返回需要的列，保持与原始函数相同的列名结构
        result_cols = ['GANTRYID', 'PASSID', '交易时间', '速度_km_h']
        has_vehicle_type = '车型' in df.columns

        if df.empty:
            print("警告: 过滤后没有有效的速度数据，返回空DataFrame")
            result = pd.DataFrame(columns=['当前门架', 'PASSID', '交易时间', '速度'])
        else:
            # 转换回原始数据类型
            df['GANTRYID'] = df['GANTRYID'].astype(str)
            df['PASSID'] = df['PASSID'].astype(str)

            if has_vehicle_type:
                result_cols.append('车型')
            result = df[result_cols].copy()
            rename_map = {
                'GANTRYID': '当前门架',
                '速度_km_h': '速度'
            }
            if has_vehicle_type:
                rename_map['车型'] = '车型'
            result = result.rename(columns=rename_map)

        # 确保列名正确
        required_result_cols = ['当前门架', 'PASSID', '交易时间', '速度']
        missing_cols = [col for col in required_result_cols if col not in result.columns]
        if missing_cols:
            print(f"错误: 结果DataFrame缺少必需的列: {missing_cols}")
            result = pd.DataFrame(columns=required_result_cols)

        print(f"优化速度计算完成! 结果形状: {result.shape}")
        if not result.empty:
            print(f"结果前几行:\n{result.head(3)}")

        # 强制垃圾回收
        import gc
        gc.collect()

        return result

    def _process_traffic_in_chunks(self, df: pd.DataFrame, gantry_info: Dict[str, Tuple[float, float]], chunk_size: int = 50000) -> pd.DataFrame:
        """
        分批处理大型流量数据

        Args:
            df: 原始流量数据DataFrame
            gantry_info: 门架经纬度信息
            chunk_size: 每批处理的行数

        Returns:
            处理后的DataFrame（包含速度信息）
        """
        print(f"开始分批处理流量数据，总共{len(df)}行，每批{chunk_size}行")

        results = []
        total_chunks = (len(df) + chunk_size - 1) // chunk_size

        for i in range(0, len(df), chunk_size):
            chunk_end = min(i + chunk_size, len(df))
            chunk_df = df.iloc[i:chunk_end].copy()

            print(f"处理第{i//chunk_size + 1}/{total_chunks}批数据，行数: {len(chunk_df)}")

            # 处理当前分块
            chunk_result = self._process_traffic_single_batch(chunk_df, gantry_info)

            if not chunk_result.empty:
                results.append(chunk_result)

            # 定期清理内存
            if len(results) >= 5:
                temp_result = pd.concat(results, ignore_index=True)
                results = [temp_result]
                print(f"已合并中间结果，当前总行数: {len(temp_result)}")

        # 合并所有结果
        if results:
            final_result = pd.concat(results, ignore_index=True)
            print(f"分批处理完成，最终结果形状: {final_result.shape}")
            return final_result
        else:
            print("警告: 分批处理后没有有效的速度数据")
            return pd.DataFrame(columns=['当前门架', 'PASSID', '交易时间', '速度'])

    def process_traffic_data(self, df: pd.DataFrame, gantry_info: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
        """
        处理流量数据，计算车辆速度

        Args:
            df: 原始流量数据DataFrame
            gantry_info: 门架经纬度信息

        Returns:
            处理后的DataFrame（包含速度信息）
        """
        self.log_processing_step("处理流量数据", f"原始数据形状: {df.shape}")

        # 检查必要的列
        required_columns = ['GANTRYID', 'PASSID', '车型', '交易时间']
        if not self.validate_dataframe(df, required_columns):
            print("错误: 流量数据缺少必要的列")
            return pd.DataFrame()

        # 创建副本
        processed_df = df.copy()

        # 转换时间列
        processed_df['交易时间'] = pd.to_datetime(processed_df['交易时间'])

        # 按车辆ID分组，计算行程时间和速度
        vehicle_groups = processed_df.groupby('PASSID')

        speeds = []
        processed_vehicles = 0

        for vehicle_id, group in vehicle_groups:
            # 按时间排序
            group = group.sort_values('交易时间')

            if len(group) >= 2:
                # 计算相邻门架之间的距离和时间差
                for i in range(len(group) - 1):
                    current_row = group.iloc[i]
                    next_row = group.iloc[i + 1]

                    current_gantry = str(current_row['GANTRYID']).strip()
                    next_gantry = str(next_row['GANTRYID']).strip()

                    # 获取经纬度
                    if current_gantry in gantry_info and next_gantry in gantry_info:
                        lon1, lat1 = gantry_info[current_gantry]
                        lon2, lat2 = gantry_info[next_gantry]

                        # 计算距离
                        distance_km = self._haversine_distance(lon1, lat1, lon2, lat2)

                        # 计算时间差（小时）
                        time_diff = (next_row['交易时间'] - current_row['交易时间']).total_seconds() / 3600

                        # 过滤不合理的时间差
                        min_time_diff = self.traffic_params.get('min_time_diff_hours', 0.001)
                        max_time_diff = 24  # 最大24小时

                        if min_time_diff <= time_diff <= max_time_diff and distance_km > 0:
                            # 计算速度（km/h）
                            speed = distance_km / time_diff

                            # 过滤不合理的速度
                            min_speed = self.traffic_params.get('min_speed', 5)
                            max_speed = self.traffic_params.get('max_speed', 200)

                            if min_speed <= speed <= max_speed:
                                # 记录速度
                                speeds.append({
                                    '车辆ID': vehicle_id,
                                    '当前门架': current_gantry,
                                    '下一门架': next_gantry,
                                    '交易时间': current_row['交易时间'],
                                    '距离_km': distance_km,
                                    '时间差_h': time_diff,
                                    '速度_km_h': speed
                                })

                processed_vehicles += 1

                # 进度显示
                if processed_vehicles % 1000 == 0:
                    print(f"已处理 {processed_vehicles} 辆车...")

        # 创建速度DataFrame
        if speeds:
            speed_df = pd.DataFrame(speeds)
            print(f"成功计算 {len(speed_df)} 条速度记录")
            return speed_df
        else:
            print("警告: 未计算出任何有效的速度记录")
            return pd.DataFrame()

    def calculate_monthly_statistics(self, speed_df: pd.DataFrame, month_str: str,
                                     original_traffic_dfs: List[pd.DataFrame] = None) -> pd.DataFrame:
        """
        计算月度统计指标

        Args:
            speed_df: 包含速度信息的DataFrame
            month_str: 月份字符串（格式: YYYY-MM）
            original_traffic_dfs: 原始流量数据DataFrame列表，用于计算大型车比例
                                  (不要使用处理过的speed_df，因为它已过滤掉无效记录)

        Returns:
            月度统计DataFrame
        """
        self.log_processing_step("计算月度统计", f"月份: {month_str}")

        if speed_df.empty:
            print("警告: 速度数据为空")
            return pd.DataFrame()

        # 获取货车类型配置
        truck_types = self.traffic_params.get('truck_types',
            ['一型货车','二型货车','三型货车','四型货车','五型货车','六型货车'])

        # 增量计算大型车比例（逐文件处理，避免一次性全量concat导致内存溢出）
        if original_traffic_dfs is not None and len(original_traffic_dfs) > 0:
            vehicle_counts = {}  # {gantry_id: [total, truck]}
            _gantry_col = None
            _vehicle_col = None
            for df in original_traffic_dfs:
                if _gantry_col is None:
                    for col in ['GANTRYID', '门架编码', '门架ID']:
                        if col in df.columns:
                            _gantry_col = col
                            break
                if _vehicle_col is None:
                    for col in ['车型', '车辆类型', 'VEHICLETYPE']:
                        if col in df.columns:
                            _vehicle_col = col
                            break
                _gantry_col = _gantry_col or 'GANTRYID'
                if _vehicle_col and _vehicle_col in df.columns:
                    for gid, grp in df.groupby(_gantry_col):
                        gid = str(gid).strip()
                        total = len(grp)
                        truck = int(grp[_vehicle_col].isin(truck_types).sum())
                        if gid in vehicle_counts:
                            vehicle_counts[gid][0] += total
                            vehicle_counts[gid][1] += truck
                        else:
                            vehicle_counts[gid] = [total, truck]
            large_vehicle_ratio_map = {}
            for gid, (t, tr) in vehicle_counts.items():
                large_vehicle_ratio_map[gid] = tr / t if t > 0 else 0.3
        else:
            large_vehicle_ratio_map = {}

        for gantry_id, group in speed_df.groupby('当前门架'):
            # 按天分组
            daily_stats = []

            group['交易日期'] = group['交易时间'].dt.date

            for date, daily_group in group.groupby('交易日期'):
                # 高峰小时（假设为9-10点）
                peak_hour_group = daily_group[
                    (daily_group['交易时间'].dt.hour >= 9) &
                    (daily_group['交易时间'].dt.hour < 10)
                    ]

                if len(peak_hour_group) > 0:
                    # 高峰小时流量
                    peak_hour_traffic = len(peak_hour_group)

                    # 高峰小时速度统计
                    peak_hour_speeds = peak_hour_group['速度_km_h'].values
                    speed_std = np.std(peak_hour_speeds) if len(peak_hour_speeds) > 1 else 0

                    daily_stats.append({
                        '日期': date,
                        '高峰小时流量': peak_hour_traffic,
                        '高峰小时速度离散差': speed_std
                    })

            if daily_stats:
                daily_stats_df = pd.DataFrame(daily_stats)

                # 月度统计
                monthly_peak_traffic = daily_stats_df['高峰小时流量'].mean()
                monthly_speed_discrete = daily_stats_df['高峰小时速度离散差'].mean()

                # 计算大型车比例（优先使用原始流量数据预计算的映射）
                if large_vehicle_ratio_map and gantry_id in large_vehicle_ratio_map:
                    large_vehicle_ratio = large_vehicle_ratio_map[gantry_id]
                elif '车型' in speed_df.columns:
                    total_vehicles = speed_df[speed_df['当前门架'] == gantry_id].shape[0]
                    truck_vehicles = speed_df[(speed_df['当前门架'] == gantry_id) & (speed_df['车型'].isin(truck_types))].shape[0]
                    large_vehicle_ratio = truck_vehicles / total_vehicles if total_vehicles > 0 else 0.3
                else:
                    large_vehicle_ratio = 0.3

                gantry_stats.append({
                    '门架编码': gantry_id,
                    '日期': month_str,
                    '日均高峰小时流量': monthly_peak_traffic,
                    '日均高峰小时车速离散差': monthly_speed_discrete,
                    '日均大型车占比': large_vehicle_ratio
                })

        if gantry_stats:
            stats_df = pd.DataFrame(gantry_stats)
            print(f"计算了 {len(stats_df)} 个门架的月度统计")
            return stats_df
        else:
            print("警告: 未计算出任何门架统计")
            return pd.DataFrame()

    def calculate_monthly_statistics_optimized(self, speed_df: pd.DataFrame, month_str: str,
                                               original_traffic_dfs: List[pd.DataFrame] = None) -> pd.DataFrame:
        """
        优化版的月度统计指标计算（基于[4]newflow_prehandle.py）

        Args:
            speed_df: 包含速度信息的DataFrame
            month_str: 月份字符串（格式: YYYY-MM）
            original_traffic_dfs: 原始流量数据DataFrame列表，用于计算大型车比例
                                  (不要使用处理过的speed_df，因为它已过滤掉无效记录)

        Returns:
            月度统计DataFrame
        """
        self.log_processing_step("优化计算月度统计", f"月份: {month_str}")

        if speed_df.empty:
            print("警告: 速度数据为空")
            return pd.DataFrame()

        # 详细调试：打印列名和数据类型
        print(f"调试: speed_df 列名: {speed_df.columns.tolist()}")
        print(f"调试: speed_df 形状: {speed_df.shape}")
        print(f"调试: speed_df 数据类型:\n{speed_df.dtypes}")
        if not speed_df.empty:
            print(f"调试: 前3行数据:\n{speed_df.head(3)}")
            # 特别检查'交易时间'列
            if '交易时间' in speed_df.columns:
                print(f"调试: '交易时间'列类型: {speed_df['交易时间'].dtype}")
                print(f"调试: '交易时间'前几个值: {speed_df['交易时间'].head(3).tolist()}")
            else:
                print("警告: '交易时间'列不存在!")

            # 检查是否有'当前门架'列
            if '当前门架' in speed_df.columns:
                print(f"调试: '当前门架'列存在，前几个值: {speed_df['当前门架'].head(3).tolist()}")
            else:
                print("警告: '当前门架'列不存在，尝试查找替代列名")

        # 需要原始数据来计算大型车比例，这里简化处理
        # 实际应用中需要从配置中获取大型车类型
        truck_types = self.traffic_params.get('truck_types',
            ['一型货车','二型货车','三型货车','四型货车','五型货车','六型货车'])

        # 1. 标准化列名：确保有'当前门架'列
        speed_df = speed_df.copy()
        print(f"调试: speed_df原始列名: {speed_df.columns.tolist()}")

        # 检查是否有'当前门架'列，如果没有则尝试映射可能的列名
        if '当前门架' not in speed_df.columns:
            print("警告: speed_df中没有'当前门架'列，尝试查找替代列名")
            possible_gantry_columns = ['GANTRYID', '门架编码', '门架ID', '门架编号', 'etc_id', 'ETC_ID', 'gantry_id']
            found_gantry_col = None
            for col in possible_gantry_columns:
                if col in speed_df.columns:
                    found_gantry_col = col
                    print(f"找到替代列名: '{col}'，将其重命名为'当前门架'")
                    speed_df = speed_df.rename(columns={col: '当前门架'})
                    break

            if found_gantry_col is None:
                print(f"错误: 无法找到门架列。现有列: {speed_df.columns.tolist()}")
                print(f"速度数据前几行:\n{speed_df.head() if not speed_df.empty else '空DataFrame'}")
                return pd.DataFrame()

        # 2. 添加日期和小时列（向量化操作）
        speed_df['日期'] = speed_df['交易时间'].dt.date
        speed_df['小时'] = speed_df['交易时间'].dt.hour

        # 预处理原始流量数据（增量处理，避免一次性全量concat导致内存溢出）
        hourly_flow = None
        vehicle_counts = {}  # {gantry_id: [total_count, truck_count]}
        if original_traffic_dfs is not None and len(original_traffic_dfs) > 0:
            hourly_flow_parts = []
            _gantry_col = None
            _vehicle_col = None
            for df in original_traffic_dfs:
                df_part = df.copy()
                if _gantry_col is None:
                    for col in ['GANTRYID', '门架编码', '门架ID']:
                        if col in df_part.columns:
                            _gantry_col = col
                            break
                if _vehicle_col is None:
                    for col in ['车型', '车辆类型', 'VEHICLETYPE']:
                        if col in df_part.columns:
                            _vehicle_col = col
                            break
                _gantry_col = _gantry_col or 'GANTRYID'
                df_part['交易时间'] = pd.to_datetime(df_part['交易时间'], errors='coerce')
                df_part = df_part.dropna(subset=['交易时间'])
                df_part['日期'] = df_part['交易时间'].dt.date
                df_part['小时'] = df_part['交易时间'].dt.hour
                hf = df_part.groupby([_gantry_col, '日期', '小时']).size().reset_index(name='流量')
                hf = hf.rename(columns={_gantry_col: 'GANTRYID'})
                hourly_flow_parts.append(hf)
                if _vehicle_col and _vehicle_col in df_part.columns:
                    for gid, grp in df_part.groupby('GANTRYID'):
                        gid = str(gid).strip()
                        total = len(grp)
                        truck = int(grp[_vehicle_col].isin(truck_types).sum())
                        if gid in vehicle_counts:
                            vehicle_counts[gid][0] += total
                            vehicle_counts[gid][1] += truck
                        else:
                            vehicle_counts[gid] = [total, truck]
                del df_part
            import gc
            gc.collect()
            hourly_flow = pd.concat(hourly_flow_parts, ignore_index=True)
            hourly_flow = hourly_flow.groupby(['GANTRYID', '日期', '小时'])['流量'].sum().reset_index()
            hourly_flow = hourly_flow.rename(columns={'GANTRYID': '当前门架'})
            del hourly_flow_parts
        else:
            # 回退：使用speed_df（仅包含有下一门架的记录）
            required_cols = ['当前门架', '日期', '小时']
            missing_cols = [col for col in required_cols if col not in speed_df.columns]
            if missing_cols:
                print(f"错误: speed_df缺少必需的列: {missing_cols}")
                return pd.DataFrame()
            hourly_flow = speed_df.groupby(['当前门架', '日期', '小时']).size().reset_index(name='流量')

        # 3. 找到每个门架每天的高峰小时
        print("计算高峰小时...")
        daily_peak_hour = hourly_flow.loc[hourly_flow.groupby(['当前门架', '日期'])['流量'].idxmax()]

        # 4. 计算日均高峰小时流量
        avg_peak_flow = daily_peak_hour.groupby('当前门架')['流量'].mean().reset_index(name='日均高峰小时流量')
        avg_peak_flow = avg_peak_flow.rename(columns={'当前门架': '门架编码'})

        # 5. 计算大型车比例（这里简化，实际需要从原始数据获取）
        # 获取高峰小时车辆数据
        peak_hour_speeds = []
        for (gantry_id, date, hour), group in speed_df.groupby(['当前门架', '日期', '小时']):
            if len(group) > 0:
                # 计算速度离散差
                speeds = group['速度'].dropna()
                if len(speeds) > 0:
                    q15 = speeds.quantile(0.15)
                    q85 = speeds.quantile(0.85)
                    speed_dispersion = q85 - q15
                    peak_hour_speeds.append({
                        '门架编码': gantry_id,
                        '日期': date,
                        '小时': hour,
                        '车速离散差': speed_dispersion
                    })

        # 6. 创建速度离散差DataFrame
        if peak_hour_speeds:
            speed_dispersion_df = pd.DataFrame(peak_hour_speeds)
            # 合并到高峰小时数据
            daily_peak_hour = daily_peak_hour.rename(columns={'当前门架': '门架编码'})
            peak_with_dispersion = pd.merge(
                daily_peak_hour[['门架编码', '日期', '小时']],
                speed_dispersion_df,
                on=['门架编码', '日期', '小时'],
                how='left'
            )
            # 计算日均离散差
            avg_dispersion = peak_with_dispersion.groupby('门架编码')['车速离散差'].mean().reset_index(
                name='日均高峰小时车速离散差')
        else:
            avg_dispersion = pd.DataFrame(columns=['门架编码', '日均高峰小时车速离散差'])

        # 7. 合并所有结果（外连接，保留流量统计中的所有门架，即使无速度离散差）
        result = avg_peak_flow

        if not avg_dispersion.empty:
            result = pd.merge(result, avg_dispersion, on='门架编码', how='outer').fillna(0)
        else:
            result['日均高峰小时车速离散差'] = 0

        # 8. 计算大型车比例（基于增量统计的车辆计数，避免全量concat）
        if vehicle_counts:
            print("使用增量统计计算大型车比例...")
            ratio_data = []
            for gid, (total, truck) in vehicle_counts.items():
                ratio_data.append({
                    '门架编码': gid,
                    '日均大型车占比': truck / total if total > 0 else 0.3
                })
            vehicle_ratio_df = pd.DataFrame(ratio_data)
            result = pd.merge(result, vehicle_ratio_df, on='门架编码', how='left')
            result['日均大型车占比'] = result['日均大型车占比'].fillna(0.3)
            del vehicle_ratio_df, ratio_data
        elif '车型' in speed_df.columns:
            print("警告: 未提供原始流量数据，回退使用速度数据中的车型列计算大型车比例（可能不准确）")
            total_vehicles = speed_df.groupby('当前门架').size().reset_index(name='总车流量')
            truck_vehicles = speed_df[speed_df['车型'].isin(truck_types)].groupby('当前门架').size().reset_index(name='货车流量')
            vehicle_ratio = pd.merge(total_vehicles, truck_vehicles, on='当前门架', how='left').fillna(0)
            vehicle_ratio['日均大型车占比'] = vehicle_ratio['货车流量'] / vehicle_ratio['总车流量']
            result = pd.merge(result, vehicle_ratio[['当前门架', '日均大型车占比']], left_on='门架编码', right_on='当前门架', how='left')
            result = result.drop(columns=['当前门架'], errors='ignore')
            result['日均大型车占比'] = result['日均大型车占比'].fillna(0.3)
        else:
            print("警告: 数据中缺少'车型'列，使用默认大型车占比0.3")
            result['日均大型车占比'] = 0.3

        # 9. 计算拥挤度
        design_capacity = self.traffic_params.get('peak_hour_capacity', 3000)
        result['拥挤度'] = result['日均高峰小时流量'] / design_capacity

        print(f"优化统计完成，共计算了 {len(result)} 个门架的统计指标")
        return result

    def calculate_risk_assessment(self, stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算门架风险评估

        Args:
            stats_df: 统计指标DataFrame

        Returns:
            风险评估DataFrame
        """
        self.log_processing_step("计算风险评估", f"统计数据形状: {stats_df.shape}")

        if stats_df.empty:
            print("警告: 统计数据为空")
            return pd.DataFrame()

        # 创建结果DataFrame
        result_df = stats_df.copy()

        # 获取风险阈值参数
        thresholds = {
            'congestion_high': self.traffic_params.get('congestion_high', 0.95),
            'congestion_medium': self.traffic_params.get('congestion_medium', 0.85),
            'congestion_low': self.traffic_params.get('congestion_low', 0.6),
            'large_vehicle_ratio_high_low': self.traffic_params.get('large_vehicle_ratio_high_low', 0.4),
            'large_vehicle_ratio_high_high': self.traffic_params.get('large_vehicle_ratio_high_high', 0.6),
            'large_vehicle_ratio_medium_low': self.traffic_params.get('large_vehicle_ratio_medium_low', 0.3),
            'large_vehicle_ratio_medium_high': self.traffic_params.get('large_vehicle_ratio_medium_high', 0.7),
            'large_vehicle_ratio_low_low': self.traffic_params.get('large_vehicle_ratio_low_low', 0.2),
            'large_vehicle_ratio_low_high': self.traffic_params.get('large_vehicle_ratio_low_high', 0.8),
            'discrete_speed_high': self.traffic_params.get('discrete_speed_high', 40),
            'discrete_speed_medium': self.traffic_params.get('discrete_speed_medium', 30),
            'discrete_speed_low': self.traffic_params.get('discrete_speed_low', 20)
        }

        # 计算拥挤度（假设设计通行能力为3000辆/小时）
        design_capacity = self.traffic_params.get('peak_hour_capacity', 3000)
        result_df['拥挤度'] = result_df['日均高峰小时流量'] / design_capacity

        # 计算拥挤度风险值
        def calculate_congestion_risk(congestion):
            if congestion >= thresholds['congestion_high']:
                return 1.1
            elif congestion >= thresholds['congestion_medium']:
                return 1.08
            elif congestion >= thresholds['congestion_low']:
                return 1.05
            else:
                return 1.0

        result_df['拥挤度风险值'] = result_df['拥挤度'].apply(calculate_congestion_risk)

        # 计算交通组成风险值
        def calculate_composition_risk(ratio):
            if thresholds['large_vehicle_ratio_high_low'] <= ratio <= thresholds['large_vehicle_ratio_high_high']:
                return 1.1
            elif thresholds['large_vehicle_ratio_medium_low'] <= ratio <= thresholds['large_vehicle_ratio_medium_high']:
                return 1.08
            elif thresholds['large_vehicle_ratio_low_low'] <= ratio <= thresholds['large_vehicle_ratio_low_high']:
                return 1.05
            else:
                return 1.0

        result_df['交通组成风险值'] = result_df['日均大型车占比'].apply(calculate_composition_risk)

        # 计算离散差风险值
        def calculate_discrete_risk(discrete):
            if discrete >= thresholds['discrete_speed_high']:
                return 1.1
            elif discrete >= thresholds['discrete_speed_medium']:
                return 1.08
            elif discrete >= thresholds['discrete_speed_low']:
                return 1.05
            else:
                return 1.0

        result_df['离散差风险值'] = result_df['日均高峰小时车速离散差'].apply(calculate_discrete_risk)

        # 计算总风险值
        result_df['总风险值'] = (
            result_df['拥挤度风险值'] *
            result_df['交通组成风险值'] *
            result_df['离散差风险值']
        )

        # 确定风险等级
        def determine_risk_level(total_risk):
            if total_risk >= 1.2:
                return '高风险'
            elif total_risk >= 1.12:
                return '较高风险'
            elif total_risk >= 1.05:
                return '中等风险'
            else:
                return '低风险'

        result_df['风险等级'] = result_df['总风险值'].apply(determine_risk_level)

        print(f"风险评估完成，共评估 {len(result_df)} 个门架")

        return result_df

    def update_structure_risk_with_traffic(self, structure_risk_df: pd.DataFrame,
                                          traffic_risk_df: pd.DataFrame) -> pd.DataFrame:
        """
        将交通流风险整合到结构点风险中

        Args:
            structure_risk_df: 结构点风险数据
            traffic_risk_df: 交通流风险评估数据

        Returns:
            更新后的结构点风险数据
        """
        self.log_processing_step("更新交通流风险", f"结构点: {len(structure_risk_df)}, 门架: {len(traffic_risk_df)}")

        # 创建副本
        updated_df = structure_risk_df.copy()

        # 确保浮点列的类型正确（兼容 pandas 2.x 严格 dtype 检查）
        for col in ['动态风险叠加', '专项管控折减', '基础风险值', '总风险值']:
            if col in updated_df.columns:
                updated_df[col] = updated_df[col].astype(float)

        # 确保必要的列存在
        if '动态风险叠加' not in updated_df.columns:
            updated_df['动态风险叠加'] = 1.0

        if '门架编码' not in updated_df.columns:
            print("错误: 结构点风险数据中缺少'门架编码'列")
            return updated_df

        # 创建交通风险映射字典
        traffic_risk_dict = {}
        for _, row in traffic_risk_df.iterrows():
            gantry_code = str(row['门架编码']).strip()
            traffic_risk_dict[gantry_code] = {
                '拥挤度风险值': row.get('拥挤度风险值', 1.0),
                '交通组成风险值': row.get('交通组成风险值', 1.0),
                '离散差风险值': row.get('离散差风险值', 1.0)
            }

        # 更新动态风险叠加和专项管控折减
        updated_count = 0
        reduction_base = self.risk_params.get('reduction_base', 0.98)
        risk_threshold = self.risk_params.get('risk_threshold', 1.0)

        for idx, row in updated_df.iterrows():
            gantry_code = str(row['门架编码']).strip() if pd.notna(row['门架编码']) else None

            if gantry_code and gantry_code in traffic_risk_dict:
                traffic_risk = traffic_risk_dict[gantry_code]

                # 计算交通风险因子
                traffic_factor = (
                    traffic_risk['拥挤度风险值'] *
                    traffic_risk['交通组成风险值'] *
                    traffic_risk['离散差风险值']
                )

                # 获取当前动态风险
                current_risk = row.get('动态风险叠加', 1.0)

                # 应用交通风险到动态风险叠加
                if current_risk > risk_threshold:
                    # 如果已有高风险，则进一步增加
                    updated_risk = current_risk * traffic_factor
                    multi_dynamic_risk = True  # 表示动态风险由气象/交通流两方面决定
                else:
                    # 否则只考虑交通风险因子，不应用折减到动态风险叠加
                    updated_risk = current_risk * traffic_factor
                    multi_dynamic_risk = False

                updated_df.at[idx, '动态风险叠加'] = updated_risk

                # 应用折减到专项管控折减字段
                if '专项管控折减' in updated_df.columns:
                    current_reduction = row.get('专项管控折减', 1.0)
                    # 应用折减到专项管控折减字段
                    if multi_dynamic_risk:
                        updated_reduction = current_reduction * reduction_base * reduction_base
                    else:
                        updated_reduction = current_reduction * reduction_base
                    updated_df.at[idx, '专项管控折减'] = updated_reduction

                updated_count += 1

        # 重新计算总风险值
        if '基础风险值' in updated_df.columns and '专项管控折减' in updated_df.columns:
            updated_df['总风险值'] = (
                updated_df['基础风险值'] *
                updated_df['动态风险叠加'] *
                updated_df['专项管控折减']
            )

        print(f"交通流风险更新完成:")
        print(f"  总结构点数: {len(updated_df)}")
        print(f"  更新了 {updated_count} 个点的动态风险值")

        return updated_df

    def process_pipeline(self, use_streaming: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        执行完整的流量数据处理管道

        Args:
            use_streaming: 是否使用流式处理（默认True，避免一次性加载全部数据到内存）

        Returns:
            (门架风险评估DataFrame, 更新后的结构点风险DataFrame)
        """
        if use_streaming:
            return self.process_pipeline_streaming()
        else:
            return self.process_pipeline_optimized()

    def process_pipeline_optimized(self, use_chunks: bool = True) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        优化后的流量数据处理管道（基于[4]newflow_prehandle.py的优化算法）

        Args:
            use_chunks: 是否使用分批处理

        Returns:
            (门架风险评估DataFrame, 更新后的结构点风险DataFrame)
        """
        self.log_processing_step("优化流量数据处理", f"使用分批处理: {use_chunks}")

        # 1. 加载门架信息
        gantry_info = self.load_gantry_info()
        if not gantry_info:
            print("错误: 无法加载门架信息")
            return pd.DataFrame(), pd.DataFrame()

        # 2. 加载流量数据
        if use_chunks:
            # 获取配置文件中的chunksize设置
            chunk_size = self.traffic_params.get('chunksize', 50000)
            traffic_data_dict = self.load_traffic_data_in_chunks(chunk_size=chunk_size)
            traffic_data_list = list(traffic_data_dict.values())
        else:
            traffic_data_list = self.load_traffic_data()

        if not traffic_data_list:
            print("警告: 没有流量数据可处理")
            return pd.DataFrame(), pd.DataFrame()

        print(f"成功加载 {len(traffic_data_list)} 个流量数据文件")

        # 3. 优化处理流量数据
        all_speed_data = []
        for df in traffic_data_list:
            speed_df = self.process_traffic_data_optimized(df, gantry_info)
            if not speed_df.empty:
                all_speed_data.append(speed_df)

        if not all_speed_data:
            print("警告: 未处理出有效的速度数据")
            return pd.DataFrame(), pd.DataFrame()

        # 合并所有速度数据
        combined_speed_df = pd.concat(all_speed_data, ignore_index=True)
        print(f"合并后的速度数据形状: {combined_speed_df.shape}")
        del all_speed_data
        import gc
        gc.collect()

        # 4. 计算月度统计（这里假设处理一个月的数据）
        # 传入原始流量数据用于准确计算大型车比例
        stats_df = self.calculate_monthly_statistics_optimized(combined_speed_df, "2025-12",
                                                                    original_traffic_dfs=traffic_data_list)

        # 5. 计算风险评估
        traffic_risk_df = self.calculate_risk_assessment(stats_df)

        # 调试信息
        print(f"DEBUG - traffic_risk_df列名: {traffic_risk_df.columns.tolist()}")
        print(f"DEBUG - traffic_risk_df形状: {traffic_risk_df.shape}")
        if not traffic_risk_df.empty:
            print(f"DEBUG - traffic_risk_df前3行:")
            print(traffic_risk_df.head(3))
            # 检查是否有'门架编码'列
            if '门架编码' in traffic_risk_df.columns:
                print(f"DEBUG - 有'门架编码'列，前几个值: {traffic_risk_df['门架编码'].head(5).tolist()}")
            else:
                print(f"DEBUG - 没有'门架编码'列，当前列名: {traffic_risk_df.columns.tolist()}")

        # 6. 保存交通风险评估数据
        paths_config = self.config_manager.get_paths_config()
        traffic_output_path = paths_config.get('gantry_risk_output', '../双月门架风险评估表.xlsx')
        self.save_data(traffic_risk_df, traffic_output_path)

        # 新增：保存门架流量评估数据到数据库
        # 获取归属日期（从统一 output_db.ini 读取）
        belong_date = get_belong_date()

        if self.db_connector and self.db_connector.connection:
            print("保存门架流量评估数据到数据库...")
            if not self.db_connector.create_point_etc_traffic_evaluation_table(belong_date):
                print("❌ 创建门架流量评估表失败")
            else:
                self.db_connector.save_traffic_evaluation(traffic_risk_df, belong_date, self.etc_point_mapping)
        else:
            print("⚠️  数据库连接不可用，跳过数据库保存")

        # 7. 加载现有结构点风险数据
        base_risk_path = paths_config.get('weather_updated_risk_output',
                                          '../结构点-基础风险值-动态风险值表_更新.xlsx')
        if Path(base_risk_path).exists():
            structure_risk_df = self.read_excel_file(base_risk_path)

            # 8. 更新结构点风险
            updated_structure_risk_df = self.update_structure_risk_with_traffic(
                structure_risk_df, traffic_risk_df
            )

            # 9. 保存更新后的风险数据
            updated_output_path = paths_config.get('traffic_updated_risk_output',
                                                   '../结构点-基础风险值-动态风险值表_更新2.xlsx')
            self.save_data(updated_structure_risk_df, updated_output_path)

            return traffic_risk_df, updated_structure_risk_df
        else:
            print(f"警告: 结构点风险文件不存在: {base_risk_path}")
            return traffic_risk_df, traffic_risk_df

    def _stream_process_csv_file(self, file_path: str, gantry_info: dict, chunk_size: int = 50000) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
        """
        流式处理单个CSV文件：逐chunk读取→计算速度→聚合统计→丢弃原始chunk
        全程不将原始数据全部加载到内存

        Args:
            file_path: CSV文件路径
            gantry_info: 门架经纬度信息字典
            chunk_size: 每批读取的行数

        Returns:
            (speed_df, hourly_flow_df, vehicle_counts_dict)
            - speed_df: 合并后的速度DataFrame（已过滤，列少，远小于原始数据）
            - hourly_flow_df: 按(门架,日期,小时)聚合的流量DataFrame
            - vehicle_counts_dict: {gantry_id: [total_count, truck_count]}
        """
        truck_types = self.traffic_params.get('truck_types', [])
        if isinstance(truck_types, str):
            truck_types = [t.strip() for t in truck_types.split(',')]
        if not truck_types:
            truck_types = ['一型货车', '二型货车', '三型货车', '四型货车', '五型货车', '六型货车']

        print(f"\n流式处理文件: {Path(file_path).name}")

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        print(f"文件大小: {file_size_mb:.2f} MB")

        with open(file_path, 'rb') as f:
            detected_encoding = chardet.detect(f.read(10000))['encoding']
        print(f"检测到文件编码: {detected_encoding}")

        encodings_to_try = [detected_encoding, 'utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'big5', 'latin1', 'cp1252']

        all_speed_data = []
        hourly_flow_parts = []
        vehicle_counts = {}
        total_rows = 0
        chunk_number = 0

        for encoding in encodings_to_try:
            if encoding is None:
                continue
            try:
                chunk_iterator = pd.read_csv(file_path, encoding=encoding, chunksize=chunk_size, on_bad_lines='skip')
                for chunk in chunk_iterator:
                    chunk_number += 1
                    chunk_rows = len(chunk)
                    total_rows += chunk_rows

                    if chunk_number % 10 == 1 or chunk_number == 1:
                        print(f"处理第 {chunk_number} 批数据，大小: {chunk_rows}，累计行数: {total_rows:,}")

                    if '交易时间' not in chunk.columns:
                        print(f"警告: 第 {chunk_number} 批缺少'交易时间'列，跳过")
                        del chunk
                        continue

                    required_cols = ['GANTRYID', 'PASSID', '交易时间']
                    _has_vehicle = '车型' in chunk.columns
                    if _has_vehicle:
                        required_cols.append('车型')
                    if not set(required_cols).issubset(chunk.columns):
                        print(f"警告: 第 {chunk_number} 批缺少必要列，跳过")
                        del chunk
                        continue

                    chunk = chunk[required_cols].copy()
                    chunk['GANTRYID'] = chunk['GANTRYID'].astype(str)
                    chunk['PASSID'] = chunk['PASSID'].astype(str)
                    chunk['交易时间'] = pd.to_datetime(chunk['交易时间'], errors='coerce')

                    if chunk['交易时间'].isna().all():
                        del chunk
                        continue

                    chunk_flow = chunk.dropna(subset=['交易时间']).copy()
                    if len(chunk_flow) > 0:
                        chunk_flow['日期'] = chunk_flow['交易时间'].dt.date
                        chunk_flow['小时'] = chunk_flow['交易时间'].dt.hour
                        hf = chunk_flow.groupby(['GANTRYID', '日期', '小时']).size().reset_index(name='流量')
                        hourly_flow_parts.append(hf)

                    if _has_vehicle:
                        for gid, grp in chunk.groupby('GANTRYID'):
                            gid_str = str(gid).strip()
                            total = len(grp)
                            truck = int(grp['车型'].isin(truck_types).sum())
                            if gid_str in vehicle_counts:
                                vehicle_counts[gid_str][0] += total
                                vehicle_counts[gid_str][1] += truck
                            else:
                                vehicle_counts[gid_str] = [total, truck]

                    try:
                        speed_df = self._process_traffic_single_batch(chunk, gantry_info)
                        if not speed_df.empty:
                            all_speed_data.append(speed_df)
                    except Exception as e:
                        print(f"处理第 {chunk_number} 批数据时出错: {e}")

                    del chunk, chunk_flow

                    if chunk_number % 10 == 0:
                        import gc
                        gc.collect()
                        print(f"已处理 {chunk_number} 批数据，累计 {total_rows:,} 行")

                print(f"文件读取完成，共 {chunk_number} 批，总计 {total_rows:,} 行")
                break
            except (UnicodeDecodeError, LookupError, pd.errors.ParserError) as e:
                print(f"使用 {encoding} 编码读取失败: {e}")
                continue
            except Exception as e:
                print(f"使用 {encoding} 编码读取时发生其他错误: {e}")
                continue

        if not all_speed_data:
            print("警告: 未处理出有效的速度数据")
            return pd.DataFrame(), pd.DataFrame(), {}

        speed_df = pd.concat(all_speed_data, ignore_index=True)
        del all_speed_data

        hourly_flow = None
        if hourly_flow_parts:
            hourly_flow = pd.concat(hourly_flow_parts, ignore_index=True)
            hourly_flow = hourly_flow.groupby(['GANTRYID', '日期', '小时'])['流量'].sum().reset_index()
            hourly_flow = hourly_flow.rename(columns={'GANTRYID': '当前门架'})
        del hourly_flow_parts

        import gc
        gc.collect()
        print(f"流式处理完成: 速度数据 {speed_df.shape}, 流量统计 {hourly_flow.shape if hourly_flow is not None else 'None'}, 车辆统计 {len(vehicle_counts)} 个门架")

        return speed_df, hourly_flow, vehicle_counts

    def _calculate_monthly_statistics_streaming(self, speed_df: pd.DataFrame, month_str: str,
                                                  hourly_flow: pd.DataFrame = None,
                                                  vehicle_counts: dict = None) -> pd.DataFrame:
        """
        基于预计算数据的月度统计（流式处理版本）
        与 calculate_monthly_statistics_optimized 逻辑相同，但直接接受预计算的
        hourly_flow 和 vehicle_counts，不再传入 original_traffic_dfs 全量数据

        Args:
            speed_df: 速度数据DataFrame（列: 当前门架, PASSID, 交易时间, 速度, [车型]）
            month_str: 月份字符串
            hourly_flow: 预计算的(门架,日期,小时)流量DataFrame
            vehicle_counts: 预计算的 {gantry_id: [total, truck]} 字典

        Returns:
            月度统计DataFrame
        """
        self.log_processing_step("流式计算月度统计", f"月份: {month_str}")

        if speed_df.empty:
            print("警告: 速度数据为空")
            return pd.DataFrame()

        print(f"调试: speed_df 列名: {speed_df.columns.tolist()}")
        print(f"调试: speed_df 形状: {speed_df.shape}")

        truck_types = self.traffic_params.get('truck_types', [])
        if isinstance(truck_types, str):
            truck_types = [t.strip() for t in truck_types.split(',')]
        if not truck_types:
            truck_types = ['一型货车', '二型货车', '三型货车', '四型货车', '五型货车', '六型货车']

        speed_df = speed_df.copy()
        print(f"调试: speed_df原始列名: {speed_df.columns.tolist()}")

        if '当前门架' not in speed_df.columns:
            print("警告: speed_df中没有'当前门架'列，尝试查找替代列名")
            possible_gantry_columns = ['GANTRYID', '门架编码', '门架ID', '门架编号', 'etc_id', 'ETC_ID', 'gantry_id']
            found_gantry_col = None
            for col in possible_gantry_columns:
                if col in speed_df.columns:
                    found_gantry_col = col
                    print(f"找到替代列名: '{col}'，将其重命名为'当前门架'")
                    speed_df = speed_df.rename(columns={col: '当前门架'})
                    break
            if found_gantry_col is None:
                print(f"错误: 无法找到门架列。现有列: {speed_df.columns.tolist()}")
                return pd.DataFrame()

        speed_df['日期'] = speed_df['交易时间'].dt.date
        speed_df['小时'] = speed_df['交易时间'].dt.hour

        if hourly_flow is not None and not hourly_flow.empty:
            print(f"使用预计算的流量数据: {hourly_flow.shape}")
            hourly_flow = hourly_flow.copy()
            if '当前门架' not in hourly_flow.columns and 'GANTRYID' in hourly_flow.columns:
                hourly_flow = hourly_flow.rename(columns={'GANTRYID': '当前门架'})
        else:
            required_cols = ['当前门架', '日期', '小时']
            missing_cols = [col for col in required_cols if col not in speed_df.columns]
            if missing_cols:
                print(f"错误: speed_df缺少必需的列: {missing_cols}")
                return pd.DataFrame()
            hourly_flow = speed_df.groupby(['当前门架', '日期', '小时']).size().reset_index(name='流量')

        print("计算高峰小时...")
        daily_peak_hour = hourly_flow.loc[hourly_flow.groupby(['当前门架', '日期'])['流量'].idxmax()]

        avg_peak_flow = daily_peak_hour.groupby('当前门架')['流量'].mean().reset_index(name='日均高峰小时流量')
        avg_peak_flow = avg_peak_flow.rename(columns={'当前门架': '门架编码'})

        peak_hour_speeds = []
        for (gantry_id, date, hour), group in speed_df.groupby(['当前门架', '日期', '小时']):
            if len(group) > 0:
                speeds = group['速度'].dropna()
                if len(speeds) > 0:
                    q15 = speeds.quantile(0.15)
                    q85 = speeds.quantile(0.85)
                    peak_hour_speeds.append({
                        '门架编码': gantry_id,
                        '日期': date,
                        '小时': hour,
                        '车速离散差': q85 - q15
                    })

        if peak_hour_speeds:
            speed_dispersion_df = pd.DataFrame(peak_hour_speeds)
            daily_peak_hour = daily_peak_hour.rename(columns={'当前门架': '门架编码'})
            peak_with_dispersion = pd.merge(
                daily_peak_hour[['门架编码', '日期', '小时']],
                speed_dispersion_df,
                on=['门架编码', '日期', '小时'],
                how='left'
            )
            avg_dispersion = peak_with_dispersion.groupby('门架编码')['车速离散差'].mean().reset_index(
                name='日均高峰小时车速离散差')
        else:
            avg_dispersion = pd.DataFrame(columns=['门架编码', '日均高峰小时车速离散差'])

        result = avg_peak_flow

        if not avg_dispersion.empty:
            result = pd.merge(result, avg_dispersion, on='门架编码', how='outer').fillna(0)
        else:
            result['日均高峰小时车速离散差'] = 0

        if vehicle_counts:
            print("使用预计算的车辆统计数据计算大型车比例...")
            ratio_data = []
            for gid, (total, truck) in vehicle_counts.items():
                ratio_data.append({
                    '门架编码': gid,
                    '日均大型车占比': truck / total if total > 0 else 0.3
                })
            vehicle_ratio_df = pd.DataFrame(ratio_data)
            result = pd.merge(result, vehicle_ratio_df, on='门架编码', how='left')
            result['日均大型车占比'] = result['日均大型车占比'].fillna(0.3)
            del vehicle_ratio_df, ratio_data
        elif '车型' in speed_df.columns:
            print("警告: 未提供车辆统计数据，回退使用速度数据中的车型列计算大型车比例（可能不准确）")
            total_vehicles = speed_df.groupby('当前门架').size().reset_index(name='总车流量')
            truck_vehicles = speed_df[speed_df['车型'].isin(truck_types)].groupby('当前门架').size().reset_index(name='货车流量')
            vehicle_ratio = pd.merge(total_vehicles, truck_vehicles, on='当前门架', how='left').fillna(0)
            vehicle_ratio['日均大型车占比'] = vehicle_ratio['货车流量'] / vehicle_ratio['总车流量']
            result = pd.merge(result, vehicle_ratio[['当前门架', '日均大型车占比']], left_on='门架编码', right_on='当前门架', how='left')
            result = result.drop(columns=['当前门架'], errors='ignore')
            result['日均大型车占比'] = result['日均大型车占比'].fillna(0.3)
        else:
            print("警告: 使用默认大型车占比0.3")
            result['日均大型车占比'] = 0.3

        design_capacity = self.traffic_params.get('peak_hour_capacity', 3000)
        result['拥挤度'] = result['日均高峰小时流量'] / design_capacity

        print(f"流式统计完成，共计算了 {len(result)} 个门架的统计指标")
        return result

    def process_pipeline_streaming(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        流式流量数据处理管道：不将原始CSV数据全部加载到内存
        逐chunk读取→计算速度→增量聚合→丢弃chunk

        对比 process_pipeline_optimized，此方法完全消除了：
         - _process_large_file_in_chunks 中 pd.concat(all_chunks) 的全量原始数据拷贝
         - traffic_data_list 中所有文件全部原始数据的累积

        Returns:
            (门架风险评估DataFrame, 更新后的结构点风险DataFrame)
        """
        import gc

        self.log_processing_step("流式流量数据处理", "使用流式处理避免内存溢出")

        gantry_info = self.load_gantry_info()
        if not gantry_info:
            print("错误: 无法加载门架信息")
            return pd.DataFrame(), pd.DataFrame()

        paths_config = self.config_manager.get_paths_config()
        data_dir = paths_config.get('traffic_data_dir')

        if not Path(data_dir).exists():
            print(f"警告: 流量数据目录不存在: {data_dir}")
            return pd.DataFrame(), pd.DataFrame()

        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        if not csv_files:
            print(f"警告: 目录中没有找到CSV文件: {data_dir}")
            return pd.DataFrame(), pd.DataFrame()

        print(f"找到 {len(csv_files)} 个CSV文件，使用流式处理")

        chunk_size = self.traffic_params.get('chunksize', 50000)

        all_speed_data = []
        all_hourly_flow_parts = []
        global_vehicle_counts = {}

        for csv_file in csv_files:
            speed_df, hourly_flow, vehicle_counts = self._stream_process_csv_file(
                csv_file, gantry_info, chunk_size
            )

            if not speed_df.empty:
                all_speed_data.append(speed_df)
            if hourly_flow is not None and not hourly_flow.empty:
                all_hourly_flow_parts.append(hourly_flow)

            for gid, (total, truck) in vehicle_counts.items():
                if gid in global_vehicle_counts:
                    global_vehicle_counts[gid][0] += total
                    global_vehicle_counts[gid][1] += truck
                else:
                    global_vehicle_counts[gid] = [total, truck]

            gc.collect()

        if not all_speed_data:
            print("警告: 未处理出有效的速度数据")
            return pd.DataFrame(), pd.DataFrame()

        combined_speed_df = pd.concat(all_speed_data, ignore_index=True)
        print(f"合并后的速度数据形状: {combined_speed_df.shape}")
        del all_speed_data
        gc.collect()

        hourly_flow = None
        if all_hourly_flow_parts:
            hourly_flow = pd.concat(all_hourly_flow_parts, ignore_index=True)
            hourly_flow = hourly_flow.groupby(['当前门架', '日期', '小时'])['流量'].sum().reset_index()
            del all_hourly_flow_parts

        stats_df = self._calculate_monthly_statistics_streaming(
            combined_speed_df, "2025-12", hourly_flow, global_vehicle_counts
        )

        traffic_risk_df = self.calculate_risk_assessment(stats_df)

        print(f"DEBUG - traffic_risk_df列名: {traffic_risk_df.columns.tolist()}")
        print(f"DEBUG - traffic_risk_df形状: {traffic_risk_df.shape}")
        if not traffic_risk_df.empty:
            print(f"DEBUG - traffic_risk_df前3行:")
            print(traffic_risk_df.head(3))
            if '门架编码' in traffic_risk_df.columns:
                print(f"DEBUG - 有'门架编码'列，前几个值: {traffic_risk_df['门架编码'].head(5).tolist()}")
            else:
                print(f"DEBUG - 没有'门架编码'列，当前列名: {traffic_risk_df.columns.tolist()}")

        traffic_output_path = paths_config.get('gantry_risk_output', '../双月门架风险评估表.xlsx')
        self.save_data(traffic_risk_df, traffic_output_path)

        belong_date = get_belong_date()
        if self.db_connector and self.db_connector.connection:
            print("保存门架流量评估数据到数据库...")
            if not self.db_connector.create_point_etc_traffic_evaluation_table(belong_date):
                print("创建门架流量评估表失败")
            else:
                self.db_connector.save_traffic_evaluation(traffic_risk_df, belong_date, self.etc_point_mapping)
        else:
            print("数据库连接不可用，跳过数据库保存")

        base_risk_path = paths_config.get('weather_updated_risk_output',
                                           '../结构点-基础风险值-动态风险值表_更新.xlsx')
        if Path(base_risk_path).exists():
            structure_risk_df = self.read_excel_file(base_risk_path)
            updated_structure_risk_df = self.update_structure_risk_with_traffic(
                structure_risk_df, traffic_risk_df
            )
            updated_output_path = paths_config.get('traffic_updated_risk_output',
                                                    '../结构点-基础风险值-动态风险值表_更新2.xlsx')
            self.save_data(updated_structure_risk_df, updated_output_path)
            return traffic_risk_df, updated_structure_risk_df
        else:
            print(f"警告: 结构点风险文件不存在: {base_risk_path}")
            return traffic_risk_df, traffic_risk_df

    def load_data(self, data_source: str) -> Any:
        """
        加载数据 - 抽象方法实现
        根据数据源类型加载门架信息或流量数据

        Args:
            data_source: 数据源类型，可以是'gantry_info'或'traffic_data'

        Returns:
            加载的数据对象
        """
        if data_source == 'gantry_info':
            return self.load_gantry_info()
        elif data_source == 'traffic_data':
            return self.load_traffic_data()
        else:
            # 假设是目录路径
            if os.path.isdir(data_source):
                return self.load_traffic_data(data_source)
            elif data_source.endswith(('.xlsx', '.xls')):
                # 门架信息Excel文件
                return self.load_gantry_info(data_source)
            else:
                raise ValueError(f"不支持的数据源类型: {data_source}")

    def process(self, data: Any) -> pd.DataFrame:
        """
        处理数据 - 抽象方法实现
        处理流量数据，计算速度统计和风险评估

        Args:
            data: 输入数据，可以是流量数据DataFrame列表或单DataFrame

        Returns:
            处理后的DataFrame
        """
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], pd.DataFrame):
            # 流量数据列表
            gantry_info = self.load_gantry_info()
            if not data:
                return pd.DataFrame()

            all_speed_data = []
            for df in data:
                speed_df = self.process_traffic_data(df, gantry_info)
                if not speed_df.empty:
                    all_speed_data.append(speed_df)

            if not all_speed_data:
                return pd.DataFrame()

            # 合并数据并计算统计
            combined_speed_df = pd.concat(all_speed_data, ignore_index=True)
            stats_df = self.calculate_monthly_statistics(combined_speed_df, "2025-12",
                                                         original_traffic_dfs=data)
            return self.calculate_risk_assessment(stats_df)
        elif isinstance(data, pd.DataFrame):
            # 单个DataFrame
            gantry_info = self.load_gantry_info()
            speed_df = self.process_traffic_data(data, gantry_info)
            if speed_df.empty:
                return pd.DataFrame()

            stats_df = self.calculate_monthly_statistics(speed_df, "2025-12",
                                                         original_traffic_dfs=[data] if data is not None and not data.empty else None)
            return self.calculate_risk_assessment(stats_df)
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
            paths_config = self.config_manager.get_paths_config()
            output_path = paths_config.get('gantry_risk_output', '../双月门架风险评估表.xlsx')

        self.log_processing_step("保存流量数据", f"输出路径: {output_path}")

        return self.write_excel_file(data, output_path)


if __name__ == "__main__":
    # 测试代码
    processor = TrafficDataProcessor()
    traffic_risk, updated_structure_risk = processor.process_pipeline()

    print(f"\n处理完成!")
    print(f"交通风险评估数据形状: {traffic_risk.shape}")
    if not updated_structure_risk.equals(traffic_risk):
        print(f"更新后的结构点风险数据形状: {updated_structure_risk.shape}")
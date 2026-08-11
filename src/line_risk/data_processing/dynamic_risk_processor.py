"""
动态风险计算处理器
计算交通流和气象风险
"""

import pandas as pd
import numpy as np
import os
import glob
import re
import hashlib
from tqdm import tqdm
from typing import Dict, Any, Optional, List, Tuple
from .base_processor import BaseProcessor
from ..config.config_manager import get_config_manager


class DynamicRiskProcessor(BaseProcessor):
    """动态风险计算器（交通流 + 气象）"""

    # 各目标列的候选别名（优先级从前到后）
    _ETC_COL_ALIASES = {
        'GANTRYID':  ['GANTRYID', 'gantryid', '门架编码', '门架ID', '门架id', 'gantry_id', 'GantryID'],
        'PASSID':    ['PASSID', 'passid', '通行ID', '交易流水号', '车牌号', 'pass_id', 'PassID'],
        '车型':       ['车型', 'vtype', 'VType', 'vehicle_type', 'axle_type', '轴型', '车辆类型'],
        '交易时间':   ['交易时间', 'passtime', 'PassTime', 'pass_time', 'time', 'Time', '通行时间', '过车时间'],
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化动态风险计算器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()
        self.dynamic_config = self.config.get('dynamic_risk', {})

    def _normalize_etc_columns(self, df_raw: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
        """
        标准化ETC列（别名匹配优先，位置fallback兜底）：
        1) 将实际列名 strip + 建立 lower 映射
        2) 按 _ETC_COL_ALIASES 逐一找到对应实际列名
        3) 全部找到 → 取目标列并重命名
        4) 找不到 → 按位置取前N列（打印警告，方便排查）
        """
        if df_raw is None or df_raw.empty:
            return pd.DataFrame(columns=required_cols)

        df = df_raw.copy()
        # 建立 "strip后原名" → "原始列名" 的映射
        strip_map = {str(c).strip(): c for c in df.columns}
        # 建立 lower → strip后名 的映射（用于大小写不敏感匹配）
        lower_map = {k.lower(): k for k in strip_map}

        rename = {}  # 目标列名 → 实际列名
        for target in required_cols:
            aliases = self._ETC_COL_ALIASES.get(target, [target])
            found = None
            for alias in aliases:
                # 先精确匹配
                if alias in strip_map:
                    found = strip_map[alias]
                    break
                # 再大小写不敏感匹配
                if alias.lower() in lower_map:
                    found = strip_map[lower_map[alias.lower()]]
                    break
            if found is not None:
                rename[found] = target

        if len(rename) == len(required_cols):
            result = df[list(rename.keys())].rename(columns=rename)
            return result[required_cols].copy()

        # fallback：位置映射（列数足够时）
        if len(df.columns) >= len(required_cols):
            actual_cols = list(df.columns[:len(required_cols)])
            print(f"  [Warning] ETC列名未匹配，按位置取前{len(required_cols)}列: {actual_cols} → {required_cols}")
            temp = df.iloc[:, :len(required_cols)].copy()
            temp.columns = required_cols
            return temp

        return pd.DataFrame(columns=required_cols)

    def _get_etc_source_files(self, data_folder: str) -> List[str]:
        """获取ETC源文件列表"""
        patterns = ["*.csv", "*.xlsx", "*.xls"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(data_folder, p)))
        files = sorted(
            f for f in files
            if not os.path.basename(f).startswith("~$")
        )
        return files

    def _load_etc_data(self, data_folder: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        加载ETC原始流水数据（简化版本，实际项目中可能需要缓存优化）

        Args:
            data_folder: ETC数据目录
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            ETC数据DataFrame
        """
        print("正在加载ETC数据...")

        files = self._get_etc_source_files(data_folder)
        if not files:
            print("Warning: 未找到ETC数据文件")
            return pd.DataFrame()

        all_data = []
        required_cols = ['GANTRYID', 'PASSID', '车型', '交易时间']

        for file in tqdm(files, desc="读取ETC文件"):
            try:
                if file.endswith('.csv'):
                    df_chunk = pd.read_csv(file, encoding='utf-8')
                elif file.endswith(('.xlsx', '.xls')):
                    df_chunk = pd.read_excel(file)
                else:
                    continue

                # 标准化列名
                df_normalized = self._normalize_etc_columns(df_chunk, required_cols)
                if not df_normalized.empty:
                    all_data.append(df_normalized)

            except Exception as e:
                print(f"Warning: 读取文件 {file} 失败: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        # 合并所有数据
        df_etc = pd.concat(all_data, ignore_index=True)

        # 统一数据类型
        df_etc['GANTRYID'] = df_etc['GANTRYID'].astype(str).str.strip()
        df_etc['车型'] = df_etc['车型'].astype(str).str.strip()

        # 转换时间
        df_etc['交易时间'] = pd.to_datetime(df_etc['交易时间'], errors='coerce')

        # 过滤时间范围
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.to_datetime(end_date)
        df_etc = df_etc[(df_etc['交易时间'] >= start_ts) & (df_etc['交易时间'] <= end_ts)]

        # 标记大车
        truck_types = self.dynamic_config.get('truck_types', [])
        if isinstance(truck_types, str):
            truck_types = [t.strip() for t in truck_types.split(',')]

        df_etc['is_large'] = df_etc['车型'].isin(truck_types)

        return df_etc

    def _build_topology_chain(self, df_gantry_subset: pd.DataFrame) -> pd.DataFrame:
        """
        构建门架链条：按经度(主要)或纬度排序，形成 G1->G2->G3 结构
        """
        df = df_gantry_subset.copy()

        # 源头兜底：门架数不足直接返回
        if df.shape[0] < 2:
            return pd.DataFrame()

        # 判断走向 (东西走经度，南北走纬度)
        lon_std = df['经度'].std()
        lat_std = df['纬度'].std()
        use_lon = lon_std > lat_std

        # 空间排序
        if use_lon:
            df_sorted = df.sort_values(by='经度')
        else:
            df_sorted = df.sort_values(by='纬度')

        # 上下行方向反转（如果有）
        if '上下行' in df_sorted.columns:
            direction = df_sorted['上下行'].iloc[0]
            if direction == '上行':
                df_sorted = df_sorted.iloc[::-1]

        # 关键修正：重置索引
        df_sorted = df_sorted.reset_index(drop=True)

        # 构建 Next 指针
        df_sorted['Next_GANTRYID'] = df_sorted['门架编码'].shift(-1)
        df_sorted['Next_Lon'] = df_sorted['经度'].shift(-1)
        df_sorted['Next_Lat'] = df_sorted['纬度'].shift(-1)

        # 计算距离
        dists = []
        for i in range(len(df_sorted)):
            if pd.isna(df_sorted.loc[i, 'Next_Lon']):
                dists.append(np.nan)
            else:
                d = self.haversine_distance(
                    df_sorted.loc[i, '经度'], df_sorted.loc[i, '纬度'],
                    df_sorted.loc[i, 'Next_Lon'], df_sorted.loc[i, 'Next_Lat']
                )
                dists.append(d)

        df_sorted['Distance_Next'] = dists

        return df_sorted

    def _calc_speed_and_flow(self, df_etc: pd.DataFrame, gantry_chain: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], List[Dict]]:
        """
        计算区间速度(通过车辆匹配) 和 单门架流量

        Args:
            df_etc: ETC数据
            gantry_chain: 门架链条

        Returns:
            tuple: (gantry_stats, segment_stats)
            - gantry_stats: 字典 {门架编码: DataFrame with columns ['Q', 'Large_Q']}
            - segment_stats: 列表 [{'G_Up': 上游门架, 'G_Dn': 下游门架, 'Distance': 距离, 'Hourly_Speed': Series}]
        """
        segment_stats = []
        gantry_stats = {}

        print(f"[DEBUG _calc_speed_and_flow] 输入: df_etc shape={df_etc.shape}, gantry_chain shape={gantry_chain.shape}")

        # 获取配置
        min_speed = self.dynamic_config.get('min_speed', 5.0)
        max_speed = self.dynamic_config.get('max_speed', 200.0)
        max_time_gap = self.dynamic_config.get('max_time_gap', 5.0)

        # 1. 统计单门架流量 (快速)
        if 'GANTRYID' not in df_etc.columns:
            return gantry_stats, segment_stats

        # 确保交易时间是datetime类型
        if not pd.api.types.is_datetime64_any_dtype(df_etc['交易时间']):
            df_etc['交易时间'] = pd.to_datetime(df_etc['交易时间'], errors='coerce')

        for gid, group in df_etc.groupby('GANTRYID'):
            if group.empty:
                continue

            # 设置时间索引并按小时重采样
            try:
                group_with_time = group.set_index('交易时间')
                hourly = group_with_time.resample('1h')
                gantry_stats[gid] = pd.DataFrame({
                    'Q': hourly.size(),
                    'Large_Q': hourly['is_large'].sum()
                }).fillna(0)
            except Exception as e:
                print(f"Warning: 门架 {gid} 流量统计失败: {e}")
                continue

        # 2. 计算区间速度 (匹配车辆)
        # 遍历链条 G_Up -> G_Dn
        for idx, row in gantry_chain.iterrows():
            g_up, g_dn = row['门架编码'], row['Next_GANTRYID']
            dist = row['Distance_Next']

            if pd.isna(g_dn) or dist <= 0.05:
                print(f"[DEBUG _calc_speed_and_flow] 区间 {idx}: 无效的下游门架或距离")
                continue

            print(f"[DEBUG _calc_speed_and_flow] 处理区间 {idx}: {g_up} -> {g_dn}, 距离: {dist}km")

            # 提取数据
            df_up = df_etc[df_etc['GANTRYID'] == g_up]
            df_dn = df_etc[df_etc['GANTRYID'] == g_dn]

            print(f"[DEBUG _calc_speed_and_flow] 上游门架数据: {df_up.shape}, 下游门架数据: {df_dn.shape}")

            if df_up.empty or df_dn.empty:
                print(f"[DEBUG _calc_speed_and_flow] 上游或下游数据为空")
                continue

            # 匹配车辆 (Inner Join)
            df_up_s = df_up[['PASSID', '交易时间']].rename(columns={'交易时间': 't_up'})
            df_dn_s = df_dn[['PASSID', '交易时间']].rename(columns={'交易时间': 't_dn'})

            merged = pd.merge(df_up_s, df_dn_s, on='PASSID', how='inner')
            print(f"[DEBUG _calc_speed_and_flow] 匹配后数据: {merged.shape}")

            if merged.empty:
                print(f"[DEBUG _calc_speed_and_flow] 没有匹配的车辆")
                continue

            # 计算速度
            merged['dt'] = (merged['t_dn'] - merged['t_up']).dt.total_seconds() / 3600.0
            print(f"[DEBUG _calc_speed_and_flow] 时间差统计: min={merged['dt'].min():.4f}h, max={merged['dt'].max():.4f}h, mean={merged['dt'].mean():.4f}h")

            # 过滤异常时间
            valid = merged[(merged['dt'] > 0.001) & (merged['dt'] < max_time_gap)].copy()
            print(f"[DEBUG _calc_speed_and_flow] 时间过滤后: {valid.shape}")

            if valid.empty:
                print(f"[DEBUG _calc_speed_and_flow] 时间过滤后无有效数据")
                continue

            valid['speed'] = dist / valid['dt']
            print(f"[DEBUG _calc_speed_and_flow] 速度统计: min={valid['speed'].min():.1f}km/h, max={valid['speed'].max():.1f}km/h, mean={valid['speed'].mean():.1f}km/h")

            # 过滤异常速度
            valid = valid[(valid['speed'] >= min_speed) & (valid['speed'] <= max_speed)]
            print(f"[DEBUG _calc_speed_and_flow] 速度过滤后: {valid.shape}, 阈值: min={min_speed}, max={max_speed}")

            if valid.empty:
                print(f"[DEBUG _calc_speed_and_flow] 速度过滤后无有效数据")
                continue

            # 按小时聚合速度
            try:
                hourly_speed = valid.set_index('t_dn').resample('1h')['speed'].mean()
                print(f"[DEBUG _calc_speed_and_flow] 小时速度数据: 长度={len(hourly_speed)}")

                segment_stats.append({
                    'G_Up': g_up,
                    'G_Dn': g_dn,
                    'Distance': dist,
                    'Hourly_Speed': hourly_speed
                })
                print(f"[DEBUG _calc_speed_and_flow] 成功添加区间速度数据")
            except Exception as e:
                print(f"Warning: 区间 {g_up}->{g_dn} 速度计算失败: {e}")
                continue

        return gantry_stats, segment_stats

    def _calc_traffic_metrics(self, df_etc: pd.DataFrame, gantry_chain: pd.DataFrame,
                             road: str, direction: str, design_capacity: float) -> Dict[str, float]:
        """
        计算交通流指标

        Args:
            df_etc: ETC数据
            gantry_chain: 门架链条
            road: 路段名称
            direction: 运行方向
            design_capacity: 设计通行能力

        Returns:
            包含交通流指标的字典
        """
        # 获取配置
        min_speed = self.dynamic_config.get('min_speed', 5.0)
        max_speed = self.dynamic_config.get('max_speed', 200.0)
        max_time_gap = self.dynamic_config.get('max_time_gap', 5.0)

        # 筛选该路段门架
        gids = gantry_chain['门架编码'].astype(str).str.strip().unique()
        sub_etc = df_etc[df_etc['GANTRYID'].isin(gids)]

        if sub_etc.empty:
            # 返回默认值
            return {
                '交通流_大车比': 0.0,
                '交通流_拥挤度': 0.0,
                '交通流_纵向稳定': 0.0,
                '交通流_大车系数': 1.0,
                '交通流_拥挤度系数': 1.0,
                '交通流_纵向系数': 1.0
            }

        # 计算流量和速度
        gantry_stats, segment_stats = self._calc_speed_and_flow(sub_etc, gantry_chain)

        print(f"[DEBUG _calc_traffic_metrics] gantry_stats keys: {list(gantry_stats.keys())}")
        print(f"[DEBUG _calc_traffic_metrics] segment_stats length: {len(segment_stats)}")

        if segment_stats:
            print(f"[DEBUG _calc_traffic_metrics] 第一个segment: G_Up={segment_stats[0]['G_Up']}, G_Dn={segment_stats[0]['G_Dn']}")
            if 'Hourly_Speed' in segment_stats[0]:
                speed_series = segment_stats[0]['Hourly_Speed']
                print(f"[DEBUG _calc_traffic_metrics] 速度系列类型: {type(speed_series)}, 长度: {len(speed_series) if hasattr(speed_series, '__len__') else 'N/A'}")
                if not speed_series.empty:
                    print(f"[DEBUG _calc_traffic_metrics] 速度系列前3个值: {speed_series.head(3).tolist() if not speed_series.empty else 'empty'}")

        # 1. 大车比 & 拥挤度 (基于门架流量统计)
        flow_metrics = self._compute_flow_metrics(gantry_stats, design_capacity)

        # 2. 纵向稳定性 (密度差) Formula: |Q_dn/V - Q_up/V| / L
        max_long_stab = 0.0
        for seg_idx, seg in enumerate(segment_stats):
            g_up, g_dn, dist, speed_series = seg['G_Up'], seg['G_Dn'], seg['Distance'], seg['Hourly_Speed']

            print(f"[DEBUG 纵向稳定性] 区间 {seg_idx}: {g_up} -> {g_dn}, 距离: {dist}km")
            print(f"[DEBUG 纵向稳定性] speed_series类型: {type(speed_series)}, 长度: {len(speed_series) if hasattr(speed_series, '__len__') else 'N/A'}")

            # 获取对应门架的流量数据
            if g_up not in gantry_stats or g_dn not in gantry_stats:
                print(f"[DEBUG 纵向稳定性] 缺少门架流量数据: g_up={g_up in gantry_stats}, g_dn={g_dn in gantry_stats}")
                continue

            q_up = gantry_stats[g_up]['Q']
            q_dn = gantry_stats[g_dn]['Q']
            print(f"[DEBUG 纵向稳定性] q_up类型: {type(q_up)}, q_dn类型: {type(q_dn)}")
            print(f"[DEBUG 纵向稳定性] q_up长度: {len(q_up)}, q_dn长度: {len(q_dn)}")

            # 对齐时间索引
            try:
                df_calc = pd.concat([q_up, q_dn, speed_series], axis=1, keys=['q1', 'q2', 'v']).dropna()
                print(f"[DEBUG 纵向稳定性] df_calc形状: {df_calc.shape}")

                if df_calc.empty:
                    print("[DEBUG 纵向稳定性] df_calc为空，跳过")
                    continue

                # 密度差计算：|(q2/v - q1/v)| / dist
                diff = ((df_calc['q2'] / df_calc['v']) - (df_calc['q1'] / df_calc['v'])).abs() / dist
                mean_diff = diff.mean()
                print(f"[DEBUG 纵向稳定性] 密度差均值: {mean_diff}")

                if mean_diff > max_long_stab:
                    max_long_stab = mean_diff

            except Exception as e:
                print(f"[DEBUG 纵向稳定性] 对齐计算错误: {e}")
                import traceback
                traceback.print_exc()
                continue

        # 3. 纵向稳定性系数 - 从配置中读取阈值
        longitudinal_high = self.dynamic_config.get('longitudinal_high', 20.0)
        longitudinal_medium = self.dynamic_config.get('longitudinal_medium', 5.0)

        print(f"[DEBUG 纵向稳定性系数] max_long_stab={max_long_stab}, thresholds: high={longitudinal_high}, medium={longitudinal_medium}")

        if max_long_stab >= longitudinal_high:
            longitudinal_coeff = 1.10
        elif max_long_stab >= longitudinal_medium:
            longitudinal_coeff = 1.05
        else:
            longitudinal_coeff = 1.00

        print(f"[DEBUG 纵向稳定性系数] 最终系数: {longitudinal_coeff}")

        return {
            **flow_metrics,
            '交通流_纵向稳定': max_long_stab,
            '交通流_纵向系数': longitudinal_coeff
        }

    def _compute_flow_metrics(self, gantry_stats: Dict[str, pd.DataFrame],
                              design_capacity: float) -> Dict[str, float]:
        """
        仅基于门架流量统计(gantry_stats)计算大车比和拥挤度及其系数。
        不涉及纵向稳定性（需要至少2个门架构成区间）。

        Args:
            gantry_stats: {gantry_id: DataFrame with columns Q, Large_Q}
            design_capacity: 设计通行能力

        Returns:
            包含大车比、拥挤度及其系数的字典
        """
        max_q, best_ratio = -1, 0.0
        for gid, df in gantry_stats.items():
            s_q, s_l = df['Q'].sum(), df['Large_Q'].sum()
            if s_q > max_q:
                max_q = s_q
                best_ratio = s_l / s_q if s_q > 0 else 0.0

        max_sat = 0.0
        for gid, df in gantry_stats.items():
            if df.empty:
                continue
            df_temp = df.copy()
            df_temp['Date'] = df_temp.index.date
            daily_max_q = df_temp.groupby('Date')['Q'].max()
            if not daily_max_q.empty:
                mean_daily_max = daily_max_q.mean()
                sat = mean_daily_max / design_capacity if design_capacity > 0 else 0.0
                if sat > max_sat:
                    max_sat = sat

        large_ratio_low = self.dynamic_config.get('large_vehicle_ratio_low_low', 0.2)
        large_ratio_high = self.dynamic_config.get('large_vehicle_ratio_low_high', 0.8)

        if best_ratio >= self.dynamic_config.get('large_vehicle_ratio_high_low', 0.4) and \
           best_ratio <= self.dynamic_config.get('large_vehicle_ratio_high_high', 0.6):
            large_coeff = 1.10
        elif (best_ratio >= self.dynamic_config.get('large_vehicle_ratio_medium_low', 0.3) and \
              best_ratio <= self.dynamic_config.get('large_vehicle_ratio_medium_high', 0.7)) or \
             (best_ratio >= large_ratio_low and best_ratio <= large_ratio_high):
            large_coeff = 1.05
        else:
            large_coeff = 1.00

        congestion_high = self.dynamic_config.get('congestion_high', 0.95)
        congestion_medium = self.dynamic_config.get('congestion_medium', 0.85)
        congestion_low = self.dynamic_config.get('congestion_low', 0.6)

        if max_sat >= congestion_high:
            congestion_coeff = 1.10
        elif max_sat >= congestion_medium:
            congestion_coeff = 1.08
        elif max_sat >= congestion_low:
            congestion_coeff = 1.05
        else:
            congestion_coeff = 1.00

        return {
            '交通流_大车比': best_ratio,
            '交通流_拥挤度': max_sat,
            '交通流_大车系数': large_coeff,
            '交通流_拥挤度系数': congestion_coeff
        }

    def _calc_weather_risk(self, weather_file: str, df_template: pd.DataFrame,
                          start_date: str, end_date: str) -> pd.DataFrame:
        """
        计算气象预警风险：智能列名识别 + 模糊匹配 + 相对评价

        Args:
            weather_file: 气象预警文件路径
            df_template: 模板数据
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            气象风险统计结果
        """
        print("正在计算气象预警风险...")

        try:
            df_weather = pd.read_excel(weather_file)
            # 去除列名空格
            df_weather.columns = [str(c).strip() for c in df_weather.columns]
        except Exception as e:
            print(f"Error: 读取气象文件失败: {e}")
            return pd.DataFrame()

        # 1. 查找关键列
        col_title = next((c for c in df_weather.columns if 'bt' in c or '名称' in c), None)
        col_auth = next((c for c in df_weather.columns if 'fbdw' in c or '发布机构' in c), None)
        col_time = next((c for c in df_weather.columns if 'sync_time' in c or 'create_time' in c or '发布时间' in c), None)

        if not col_title or not col_auth:
            print("Error: 气象表列名不匹配，请检查列名")
            return pd.DataFrame()

        # 2. 过滤数据 (优先使用sync_time列，该列包含完整日期时间)
        if col_time and col_time in df_weather.columns:
            df_weather[col_time] = pd.to_datetime(df_weather[col_time], errors='coerce')
            mask = (df_weather[col_time] >= pd.to_datetime(start_date)) & \
                   (df_weather[col_time] <= pd.to_datetime(end_date))
            df_weather = df_weather[mask]
        else:
            print("Warning: 未找到有效的时间列，跳过时间过滤")

        # 排除无效词
        exclude_keywords = ['取消', '解除', '终止']
        pattern_excl = '|'.join(exclude_keywords)
        df_weather = df_weather[~df_weather[col_title].str.contains(pattern_excl, na=False, regex=True)]

        # 3. 识别预警类型
        warning_types = ['大风', '暴雨', '大雾', '雷电', '冰雹', '高温', '道路结冰', '暴雪']

        def classify_warning_type(title):
            title_text = str(title)
            for kw in warning_types:
                if kw in title_text:
                    return kw
            return '其他'

        if warning_types:
            all_warning_types = warning_types + ['其他']
            df_weather['_warning_type'] = df_weather[col_title].apply(classify_warning_type)
        else:
            all_warning_types = ['其他']
            df_weather['_warning_type'] = '其他'

        # 4. 按标题统计预警类型频次（标题含具体区县气象台名称，用于后续空间匹配）
        auth_type_counts = (
            df_weather.groupby([col_title, '_warning_type'])
            .size()
            .reset_index(name='count')
        )
        auth_type_records = [
            (str(r[col_title]), str(r['_warning_type']), int(r['count']))
            for _, r in auth_type_counts.iterrows()
        ]

        # 5. 空间匹配
        results = []
        for idx, row in df_template.iterrows():
            road_name = row.get('路段', '')
            direction = row.get('运行方向', '')
            area_str = str(row.get('途径区域', ''))  # 模板表中需有此列

            # 分割区域 (支持 "垫江, 彭水")
            areas = re.split(r'[，, \s]+', area_str)
            areas = [a.strip() for a in areas if a.strip()]

            type_counter = {w_type: 0 for w_type in all_warning_types}
            for area in areas:
                for unit_name, warn_type, c in auth_type_records:
                    if area in str(unit_name):
                        type_counter[warn_type] += c

            row_result = {'路段': road_name, '运行方向': direction}
            for w_type in all_warning_types:
                row_result[f'气象预警_{w_type}_次数'] = type_counter[w_type]
            row_result['气象预警_频次'] = sum(type_counter.values())

            results.append(row_result)

        df_stats = pd.DataFrame(results)

        # 6. 计算相对系数
        if df_stats.empty:
            return df_stats

        mean_val = df_stats['气象预警_频次'].mean()

        # 计算系数
        coeffs = []
        for freq in df_stats['气象预警_频次']:
            if mean_val == 0:
                coeffs.append(1.0)
            elif freq >= mean_val * 1.1:
                coeffs.append(1.10)  # 高
            elif freq < mean_val * 0.9:
                coeffs.append(1.00)  # 低
            else:
                coeffs.append(1.05)  # 中

        df_stats['气象预警_系数'] = coeffs
        return df_stats

    def run(self, etc_folder: str, gantry_file: str, template_file: str,
            weather_file: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        主执行函数：串联交通流和气象计算

        Args:
            etc_folder: ETC数据目录
            gantry_file: 门架信息文件
            template_file: 模板文件
            weather_file: 气象预警文件
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            动态风险计算结果
        """
        print(">>> 开始计算动态风险...")

        # 1. 准备模板
        df_templ = pd.read_excel(template_file)
        # 处理合并单元格
        for col in ['路段', '路线', '运行方向', '途径区域']:
            if col in df_templ.columns:
                df_templ[col] = df_templ[col].ffill()

        # ---------------------------
        # Step A: 计算交通流风险
        # ---------------------------
        print(">>> [1/2] 开始计算交通流风险...")
        traffic_results = []

        # 加载数据
        df_etc = self._load_etc_data(etc_folder, start_date, end_date)
        df_gantry = pd.read_excel(gantry_file)

        # 按路段循环
        for (road, direction), sub_gantry in tqdm(
            df_gantry.groupby(['路段名称', '上下行']),
            desc="处理路段交通流"
        ):
            # 构建门架链条
            chain = self._build_topology_chain(sub_gantry)
            if chain.empty:
                # 单门架路段兜底：无法构建链条计算区间速度/纵向稳定性，
                # 但可基于单门架小时流量统计计算大车比和拥挤度
                gids = sub_gantry['门架编码'].astype(str).str.strip().tolist()
                single_stats = {}
                for gid in gids:
                    df_gid = df_etc[df_etc['GANTRYID'] == gid]
                    if not df_gid.empty:
                        if not pd.api.types.is_datetime64_any_dtype(df_gid['交易时间']):
                            df_gid = df_gid.copy()
                            df_gid['交易时间'] = pd.to_datetime(df_gid['交易时间'], errors='coerce')
                        gid_time = df_gid.set_index('交易时间')
                        hourly = gid_time.resample('1h')
                        single_stats[gid] = pd.DataFrame({
                            'Q': hourly.size(),
                            'Large_Q': hourly['is_large'].sum()
                        }).fillna(0)

                if single_stats:
                    row_t = df_templ[(df_templ['路段'] == road) & (df_templ['运行方向'] == direction)]
                    design_capacity = row_t.iloc[0].get('单向设计通行能力', 2300) if not row_t.empty else 2300

                    flow_metrics = self._compute_flow_metrics(single_stats, design_capacity)
                    traffic_metrics = {
                        **flow_metrics,
                        '交通流_纵向稳定': 0.0,
                        '交通流_纵向系数': 1.0
                    }
                else:
                    traffic_metrics = {
                        '交通流_大车比': 0.0,
                        '交通流_拥挤度': 0.0,
                        '交通流_纵向稳定': 0.0,
                        '交通流_大车系数': 1.0,
                        '交通流_拥挤度系数': 1.0,
                        '交通流_纵向系数': 1.0
                    }

                traffic_coeff = (
                    traffic_metrics['交通流_大车系数'] *
                    traffic_metrics['交通流_拥挤度系数'] *
                    traffic_metrics['交通流_纵向系数']
                )

                result = {
                    '路段': road,
                    '运行方向': direction,
                    **traffic_metrics,
                    '动态风险_交通流系数': traffic_coeff
                }
                traffic_results.append(result)
                continue

            # 获取设计通行能力
            row_t = df_templ[(df_templ['路段'] == road) & (df_templ['运行方向'] == direction)]
            design_capacity = row_t.iloc[0].get('单向设计通行能力', 2300) if not row_t.empty else 2300

            # 计算交通流指标
            traffic_metrics = self._calc_traffic_metrics(df_etc, chain, road, direction, design_capacity)

            # 计算交通流总系数
            traffic_coeff = (
                traffic_metrics['交通流_大车系数'] *
                traffic_metrics['交通流_拥挤度系数'] *
                traffic_metrics['交通流_纵向系数']
            )

            result = {
                '路段': road,
                '运行方向': direction,
                **traffic_metrics,
                '动态风险_交通流系数': traffic_coeff
            }
            traffic_results.append(result)

        df_traffic = pd.DataFrame(traffic_results)

        # 单门架路段兜底后处理：单方向无ETC数据时，从另一方向镜像大车比和拥挤度
        if not df_traffic.empty and '路段' in df_traffic.columns:
            flow_cols = ['交通流_大车比', '交通流_拥挤度']
            for road_name, grp in df_traffic.groupby('路段'):
                if len(grp) < 2:
                    continue
                rows = grp.index.tolist()
                a_idx, b_idx = rows[0], rows[1]
                for ft_col in flow_cols:
                    val_a = df_traffic.loc[a_idx, ft_col]
                    val_b = df_traffic.loc[b_idx, ft_col]
                    if (pd.isna(val_a) or val_a == 0.0) and not pd.isna(val_b) and val_b > 0:
                        df_traffic.loc[a_idx, ft_col] = val_b
                        df_traffic.loc[a_idx, '交通流_大车系数'] = df_traffic.loc[b_idx, '交通流_大车系数']
                        df_traffic.loc[a_idx, '交通流_拥挤度系数'] = df_traffic.loc[b_idx, '交通流_拥挤度系数']
                        df_traffic.loc[a_idx, '动态风险_交通流系数'] = (
                            df_traffic.loc[a_idx, '交通流_大车系数'] *
                            df_traffic.loc[a_idx, '交通流_拥挤度系数'] *
                            df_traffic.loc[a_idx, '交通流_纵向系数']
                        )
                    elif (pd.isna(val_b) or val_b == 0.0) and not pd.isna(val_a) and val_a > 0:
                        df_traffic.loc[b_idx, ft_col] = val_a
                        df_traffic.loc[b_idx, '交通流_大车系数'] = df_traffic.loc[a_idx, '交通流_大车系数']
                        df_traffic.loc[b_idx, '交通流_拥挤度系数'] = df_traffic.loc[a_idx, '交通流_拥挤度系数']
                        df_traffic.loc[b_idx, '动态风险_交通流系数'] = (
                            df_traffic.loc[b_idx, '交通流_大车系数'] *
                            df_traffic.loc[b_idx, '交通流_拥挤度系数'] *
                            df_traffic.loc[b_idx, '交通流_纵向系数']
                        )

        # ---------------------------
        # Step B: 计算气象风险
        # ---------------------------
        print(">>> [2/2] 开始计算气象风险...")
        df_weather = self._calc_weather_risk(weather_file, df_templ, start_date, end_date)

        # ---------------------------
        # Step C: 合并输出
        # ---------------------------
        # 以模板表为基准 Left Join
        df_final = df_templ[['路段', '运行方向', '路线']].copy()

        if not df_traffic.empty:
            df_final = pd.merge(df_final, df_traffic, on=['路段', '运行方向'], how='left')

        if not df_weather.empty:
            df_final = pd.merge(df_final, df_weather, on=['路段', '运行方向'], how='left')

        # 填充默认值
        weather_type_cols = [c for c in df_final.columns if c.startswith('气象预警_') and c.endswith('_次数')]
        fillna_cols = {
            '动态风险_交通流系数': 1.0,
            '交通流_大车系数': 1.0,
            '交通流_拥挤度系数': 1.0,
            '交通流_纵向系数': 1.0,
            '交通流_大车比': 0.0,
            '交通流_拥挤度': 0.0,
            '交通流_纵向稳定': 0.0,
            '气象预警_系数': 1.0,
            '气象预警_频次': 0
        }
        fillna_cols.update({c: 0 for c in weather_type_cols})

        for c, default_val in fillna_cols.items():
            if c not in df_final.columns:
                df_final[c] = default_val
            else:
                df_final[c] = df_final[c].fillna(default_val)

        for c in ['气象预警_频次'] + weather_type_cols:
            if c in df_final.columns:
                df_final[c] = pd.to_numeric(df_final[c], errors='coerce').fillna(0).astype(int)

        # 计算总动态风险
        df_final['动态风险_总系数'] = df_final['动态风险_交通流系数'] * df_final['气象预警_系数']

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


def test_dynamic_risk_processor():
    """测试动态风险处理器"""
    import tempfile
    import os

    # 创建测试数据
    df_gantry = pd.DataFrame({
        '路段名称': ['G65', 'G65', 'G75', 'G75'],
        '上下行': ['上行', '下行', '上行', '下行'],
        '门架编码': ['G001', 'G002', 'G003', 'G004'],
        '经度': [108.5, 108.6, 109.1, 109.2],
        '纬度': [30.5, 30.6, 31.1, 31.2]
    })

    df_template = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '路线': ['包茂高速', '包茂高速', '兰海高速', '兰海高速'],
        '途径区域': ['垫江', '垫江', '彭水', '彭水'],
        '单向设计通行能力': [2300, 2300, 2000, 2000]
    })

    # 使用临时配置文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config_content = """
[DATABASE]
enable = False

[PATHS]
input_dir = data/input

[DYNAMIC_RISK]
truck_types = 一型货车,二型货车,三型货车,四型货车,五型货车,六型货车
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
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建临时文件
        with tempfile.TemporaryDirectory() as tmpdir:
            # 保存测试文件
            gantry_file = os.path.join(tmpdir, 'gantry.xlsx')
            template_file = os.path.join(tmpdir, 'template.xlsx')
            weather_file = os.path.join(tmpdir, 'weather.xlsx')

            df_gantry.to_excel(gantry_file, index=False)
            df_template.to_excel(template_file, index=False)

            # 创建空的天气文件
            pd.DataFrame(columns=['标题', '发布单位', '发布时间']).to_excel(weather_file, index=False)

            # 创建ETC数据目录（空）
            etc_dir = os.path.join(tmpdir, 'etc_data')
            os.makedirs(etc_dir, exist_ok=True)

            # 创建处理器
            processor = DynamicRiskProcessor(config_path)

            # 测试动态风险计算
            result = processor.run(
                etc_dir, gantry_file, template_file, weather_file,
                start_date='2025-12-01', end_date='2026-01-31'
            )

            if result is not None and not result.empty:
                print("动态风险计算测试成功!")
                print(f"结果形状: {result.shape}")
                print(f"结果列名: {list(result.columns)}")
                return True
            else:
                print("动态风险计算测试失败!")
                return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_dynamic_risk_processor()
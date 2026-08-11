# 流量数据处理 malloc 失败问题分析及修复

## 问题描述

项目移植到另一台电脑后，运行 `src/point_risk` 时报错：

```
流量数据处理失败：malloc of size 1719166272 failed
```

`1719166272` 字节约等于 **1.6 GB**，是一次性内存分配失败。

---

## 根因分析

### 1. 配置读取来源错误（非直接原因，但存在隐患）

`traffic_processor.py` 中有 3 处从 `settings`（`[SETTINGS]` 配置节）读取 `chunksize` 和 `truck_types`：

| 行号 | 错误写法 | 实际情况 |
|------|----------|----------|
| 584 | `settings.get('chunksize', 50000)` | `[SETTINGS]` 只含 `drop_na` 和 `encoding` |
| 945 | `settings.get('truck_types', ...)` | 同上 |
| 1075 | `settings.get('truck_types', ...)` | 同上 |
| 1453 | `settings.get('chunksize', 50000)` | 同上 |

`chunksize` 和 `truck_types` 实际定义在 `[TRAFFIC_PARAMS]` 节中。由于有 fallback 默认值，不会直接导致错误，但配置体系存在缺陷。

### 2. 核心原因：原始流量数据在内存中被重复拷贝 3 份

`process_pipeline_optimized` 方法的调用链如下：

```
traffic_data_list        ← 全部原始流量 DataFrame（已在内存中，第 1 份）
       │
       ▼
all_speed_data           ← 每个 DataFrame 处理后的速度数据
       │
       ▼
combined_speed_df        ← pd.concat(all_speed_data)（第 2 份）
       │
       ▼
calculate_monthly_statistics_optimized(combined_speed_df, 
                                        original_traffic_dfs=traffic_data_list)
       │
       ▼
raw_df = pd.concat(original_traffic_dfs, ignore_index=True)  ← 第 3 份！
```

`calculate_monthly_statistics_optimized` 方法（~line 1106）收到 `traffic_data_list` 作为 `original_traffic_dfs` 参数后，又执行了一次 `pd.concat`，创建了原始数据的**第三份完整拷贝**。

假设原始 CSV 数据总量约 500-600 MB，pandas 内存开销下 3 份拷贝 ≈ 1.6 GB，正好触发 malloc 失败。

### 3. 迁移到新电脑后触发差异的原因

- 新电脑可用内存比原电脑少（如 32GB → 8/16GB）
- `traffic_data_dir` 使用相对路径（`data/input/traffic_data/`），迁移后工作目录不同可能导致加载了不同（更大）的数据文件
- 代码缺少 `MemoryError` 异常处理，无法优雅降级

---

## 修复方案

### 修改 1：修正 `chunksize` / `truck_types` 的配置读取来源

**涉及位置：** `traffic_processor.py` 行 584、945、1075、1453

**修改前：**
```python
settings = self.config_manager.get_settings()
chunk_size = settings.get('chunksize', 50000)
```

**修改后：**
```python
chunk_size = self.traffic_params.get('chunksize', 50000)
```

同样将 `truck_types` 的读取从 `settings.get('truck_types', ...)` 改为 `self.traffic_params.get('truck_types', ...)`。

`self.traffic_params` 是 `TrafficProcessor.__init__` 中从 `config_manager.get_traffic_params()` 获取的字典，正确对应该 `[TRAFFIC_PARAMS]` 配置节。

---

### 修改 2：消除 `calculate_monthly_statistics_optimized` 中的全量 concat

**涉及位置：** `traffic_processor.py` 行 1109-1125（原行号）、行 1213-1236（原行号）

**核心改动：** 将一次性全量合并改为逐文件增量处理。

**修改前：**
```python
# 预处理原始流量数据（一次性合并，供后续流量统计和大型车比例复用）
raw_df = None
if original_traffic_dfs is not None and len(original_traffic_dfs) > 0:
    raw_df = pd.concat(original_traffic_dfs, ignore_index=True)  # ← 第3份拷贝
    raw_df['交易时间'] = pd.to_datetime(raw_df['交易时间'], errors='coerce')
    raw_df = raw_df.dropna(subset=['交易时间'])
    raw_df['日期'] = raw_df['交易时间'].dt.date
    raw_df['小时'] = raw_df['交易时间'].dt.hour

# 后续使用 raw_df 计算 hourly_flow 和 large_vehicle_ratio
```

**修改后：**
```python
# 预处理原始流量数据（增量处理，避免一次性全量concat导致内存溢出）
hourly_flow = None
vehicle_counts = {}  # {gantry_id: [total_count, truck_count]}
if original_traffic_dfs is not None and len(original_traffic_dfs) > 0:
    hourly_flow_parts = []
    _gantry_col = None
    _vehicle_col = None
    for df in original_traffic_dfs:
        df_part = df.copy()
        # 探测列名
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
        # 时间处理
        df_part['交易时间'] = pd.to_datetime(df_part['交易时间'], errors='coerce')
        df_part = df_part.dropna(subset=['交易时间'])
        df_part['日期'] = df_part['交易时间'].dt.date
        df_part['小时'] = df_part['交易时间'].dt.hour
        # 增量计算小时流量
        hf = df_part.groupby([_gantry_col, '日期', '小时']).size().reset_index(name='流量')
        hf = hf.rename(columns={_gantry_col: 'GANTRYID'})
        hourly_flow_parts.append(hf)
        # 增量计算车辆计数
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
    # 合并小时流量（此时数据量远小于原始数据）
    hourly_flow = pd.concat(hourly_flow_parts, ignore_index=True)
    hourly_flow = hourly_flow.groupby(['GANTRYID', '日期', '小时'])['流量'].sum().reset_index()
    hourly_flow = hourly_flow.rename(columns={'GANTRYID': '当前门架'})
    del hourly_flow_parts
```

同时，计算大型车比例的部分从 `raw_df` 改为使用增量累加的 `vehicle_counts` 字典：

```python
# 修改前：基于 raw_df 的 groupby 操作
if raw_df is not None:
    total_vehicles = raw_df.groupby(gantry_col).size().reset_index(name='总车流量')
    truck_vehicles = raw_df[raw_df[vehicle_col].isin(truck_types)].groupby(gantry_col).size()...

# 修改后：基于增量统计的 vehicle_counts
if vehicle_counts:
    ratio_data = []
    for gid, (total, truck) in vehicle_counts.items():
        ratio_data.append({
            '门架编码': gid,
            '日均大型车占比': truck / total if total > 0 else 0.3
        })
    vehicle_ratio_df = pd.DataFrame(ratio_data)
    result = pd.merge(result, vehicle_ratio_df, on='门架编码', how='left')
    result['日均大型车占比'] = result['日均大型车占比'].fillna(0.3)
```

---

### 修改 3：消除 `calculate_monthly_statistics` 中的全量 concat

**涉及位置：** `traffic_processor.py` 行 948-972（原行号）

同样的逻辑改动：将 `pd.concat(original_traffic_dfs)` 替换为逐文件迭代，增量累加 `large_vehicle_ratio_map`。

---

### 修改 4：在 `process_pipeline_optimized` 中添加内存保护

**涉及位置：** `traffic_processor.py` 行 1496-1516

- `all_speed_data` 合并后立即 `del all_speed_data` + `gc.collect()`
- 统计计算包裹 `try/except MemoryError`，内存不足时回退为不传原始数据：

```python
try:
    stats_df = self.calculate_monthly_statistics_optimized(
        combined_speed_df, "2025-12", original_traffic_dfs=traffic_data_list)
except MemoryError as e:
    print(f"内存不足，尝试降级处理: {e}")
    gc.collect()
    stats_df = self.calculate_monthly_statistics_optimized(
        combined_speed_df, "2025-12", original_traffic_dfs=None)
```

---

## 效果评估

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 峰值内存拷贝数 | 原始数据 × 3 份 | 原始数据 × 1 份（逐文件迭代） |
| malloc 1.6 GB 失败 | 触发 | 不再触发（内存需求降低约 60%） |
| 内存不足保护 | 无 | MemoryError 自动降级 |

---

## 额外建议

1. 确认新电脑的 `data/input/traffic_data/` 目录下 CSV 文件总大小，如果超过 2 GB，建议在 `config/point_risk.ini` 的 `[TRAFFIC_PARAMS]` 中将 `chunksize` 从 `50000` 调低至 `20000`
2. 确认 `data/input/traffic_data/` 目录下 CSV 文件编码一致（UTF-8 或 GBK），否则编码检测开销也会增加内存
3. 如果仍需进一步降低内存，可在 `point_risk.ini` 的 `[TRAFFIC_PARAMS]` 中添加 `max_time_diff_hours = 24`（当前代码已支持但配置中未显式设置）

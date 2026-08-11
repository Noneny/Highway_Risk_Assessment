import pandas as pd
import os
import gc
import time
from datetime import datetime
from tqdm import tqdm
import python_calamine

from .config_manager import InputConfigManager, BASE_DIR


def calculate_file_suffixes(belong_date):
    try:
        date_obj = datetime.strptime(belong_date, '%Y-%m-%d')
        year = date_obj.year
        month = date_obj.month

        if month == 12:
            current_suffix = f"{str(year)[-2:]}_{month}"
            next_year = year + 1
            next_suffix = f"{str(next_year)[-2:]}_1"
        else:
            current_suffix = f"{str(year)[-2:]}_{month}"
            next_suffix = f"{str(year)[-2:]}_{month + 1}"

        return current_suffix, next_suffix

    except ValueError as e:
        print(f"日期格式错误: {e}")
        return None, None
    except Exception as e:
        print(f"计算文件后缀时出错: {e}")
        return None, None


def find_excel_files_by_date(input_dir, belong_date):
    current_suffix, next_suffix = calculate_file_suffixes(belong_date)
    if not current_suffix or not next_suffix:
        return [], False

    print(f"根据日期 {belong_date} 计算文件后缀:")
    print(f"  当前月: {current_suffix}")
    print(f"  下个月: {next_suffix}")

    excel_extensions = ['.xlsx', '.xls']
    found_files = []

    for filename in os.listdir(input_dir):
        if any(filename.lower().endswith(ext) for ext in excel_extensions):
            file_without_ext = os.path.splitext(filename)[0]
            if (current_suffix in file_without_ext or
                    next_suffix in file_without_ext):
                file_path = os.path.join(input_dir, filename)
                found_files.append(file_path)
                print(f"  找到匹配文件: {filename}")

    if found_files:
        found_files.sort()
        print(f"已找到 {len(found_files)} 个匹配文件")
        for i, file_path in enumerate(found_files, 1):
            file_name = os.path.basename(file_path)
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"  {i}. {file_name} ({file_size_mb:.1f} MB)")
    else:
        print("模糊匹配未找到文件，尝试原始精确匹配...")
        for suffix in [current_suffix, next_suffix]:
            for ext in excel_extensions:
                possible_patterns = [
                    f"traffic_etc_{suffix}{ext}",
                    f"{suffix}{ext}",
                    f"ETC_{suffix}{ext}",
                    f"etc_{suffix}{ext}"
                ]
                for pattern in possible_patterns:
                    possible_file = os.path.join(input_dir, pattern)
                    if os.path.exists(possible_file):
                        found_files.append(possible_file)
                        print(f"  找到文件: {os.path.basename(possible_file)}")
                        break

    return found_files, True


def merge_excel_to_csv(config_manager: InputConfigManager = None):
    if config_manager is None:
        config_manager = InputConfigManager()

    etc_config = config_manager.get_etc_traffic_config()
    export_config = config_manager.get_export_config()
    settings = config_manager.get_settings()

    input_dir = config_manager.resolve_path(etc_config.get('input_dir', '../ETC_Data'))
    output_csv = config_manager.resolve_path(etc_config.get('output_file', 'data/input/traffic_data/双月门架数据全量合并.csv'))
    belong_date = export_config.get('belong_date', '2025-12-01')
    encoding = settings.get('encoding', 'utf-8-sig')
    use_progress_bar = settings.get('use_progress_bar', True)
    remove_old_output = settings.get('remove_old_output', True)
    dtype_str = settings.get('dtype_str', True)
    clean_data = settings.get('clean_data', True)

    print("=" * 60)
    print("开始读取配置...")
    print(f"所属日期: {belong_date}")
    print(f"输入目录: {input_dir}")

    if not os.path.isdir(input_dir):
        print(f"输入目录不存在: {input_dir}")
        return

    print("根据所属日期自动查找文件...")
    file_list, auto_find = find_excel_files_by_date(str(input_dir), belong_date)

    print(f"源文件数量: {len(file_list)}")
    if len(file_list) == 0:
        print("未找到符合日期条件的Excel文件")
        return

    print(f"输出文件: {output_csv}")
    print("=" * 60)

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if remove_old_output and os.path.exists(output_csv):
        try:
            os.remove(output_csv)
            print(f"已清理旧输出文件: {output_csv}")
        except PermissionError:
            print(f"无法删除旧文件 {output_csv}，请检查文件是否被占用。")
            return

    missing_files = []
    for file_path in file_list:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    if missing_files:
        print("以下源文件不存在:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return

    has_written_header = False
    total_start_time = time.time()
    total_rows = 0
    total_sheets = 0

    for file_index, file_path in enumerate(file_list):
        if not os.path.exists(file_path):
            print(f"找不到文件 {file_path}，已跳过。")
            continue

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        print(f"\n[{file_index + 1}/{len(file_list)}] 正在处理文件: {file_name}")
        print(f"   文件大小: {file_size:.2f} MB")

        try:
            xls = pd.ExcelFile(file_path, engine='calamine')
            sheet_names = xls.sheet_names
            print(f"   发现 {len(sheet_names)} 个 Sheet")
            total_sheets += len(sheet_names)

            if use_progress_bar:
                sheet_iterator = tqdm(sheet_names, desc=f"   处理 {file_name}", unit="sheet")
            else:
                sheet_iterator = sheet_names

            for sheet_name in sheet_iterator:
                try:
                    read_kwargs = {'io': xls, 'sheet_name': sheet_name}
                    if dtype_str:
                        read_kwargs['dtype'] = str

                    df = pd.read_excel(**read_kwargs)

                    if df.empty:
                        if not use_progress_bar:
                            print(f"   跳过空 Sheet: {sheet_name}")
                        continue

                    rows_in_sheet = len(df)
                    total_rows += rows_in_sheet

                    if not use_progress_bar:
                        print(f"   读取 Sheet '{sheet_name}': {rows_in_sheet} 行")

                    if clean_data:
                        df.columns = df.columns.astype(str).str.strip()
                        for col in df.columns:
                            if df[col].dtype == 'object':
                                df[col] = df[col].astype(str).str.strip()

                    write_header_now = not has_written_header
                    df.to_csv(
                        output_csv,
                        mode='a',
                        header=write_header_now,
                        index=False,
                        encoding=encoding
                    )

                    if write_header_now:
                        has_written_header = True
                        if not use_progress_bar:
                            print(f"   已写入表头")

                except Exception as sheet_e:
                    print(f"\n   读取 Sheet '{sheet_name}' 失败: {sheet_e}")

                finally:
                    if 'df' in locals():
                        del df
                    gc.collect()

            xls.close()

        except Exception as e:
            print(f"\n处理文件 {file_name} 时发生严重错误: {e}")
            continue

    total_end_time = time.time()
    duration = total_end_time - total_start_time

    print("\n" + "=" * 60)
    print("全部处理完成！")

    if os.path.exists(output_csv):
        file_size_gb = os.path.getsize(output_csv) / (1024 * 1024 * 1024)
        file_size_mb = os.path.getsize(output_csv) / (1024 * 1024)
        print(f"输出文件位置: {output_csv}")
        print(f"输出文件大小: {file_size_gb:.2f} GB ({file_size_mb:.2f} MB)")
        print(f"总处理行数: {total_rows:,}")
        print(f"总处理 Sheet 数: {total_sheets}")
        print(f"总处理文件数: {len(file_list)}")
        print(f"总耗时: {duration:.2f} 秒 ({duration / 60:.2f} 分钟)")
        if duration > 0:
            rows_per_second = total_rows / duration
            print(f"处理速度: {rows_per_second:.1f} 行/秒")
        try:
            print(f"\n输出文件预览 (前3行):")
            result_df = pd.read_csv(str(output_csv), nrows=3, encoding=encoding)
            print(result_df)
            print(f"列数: {len(result_df.columns)}")
        except Exception as e:
            print(f"无法预览输出文件: {e}")
    else:
        print("输出文件未生成，请检查错误信息")

    print("=" * 60)

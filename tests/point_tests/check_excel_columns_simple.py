#!/usr/bin/env python3
import zipfile
import xml.etree.ElementTree as ET
import sys
import os

def get_xlsx_sheet_names(xlsx_path):
    """获取XLSX文件的工作表名称"""
    try:
        with zipfile.ZipFile(xlsx_path, 'r') as zf:
            # 读取workbook.xml获取工作表信息
            with zf.open('xl/workbook.xml') as f:
                content = f.read()
                root = ET.fromstring(content)

                # 获取命名空间
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

                # 获取所有工作表
                sheets = []
                for sheet in root.findall('.//main:sheet', ns):
                    name = sheet.get('name')
                    sheet_id = sheet.get('sheetId')
                    sheets.append((name, sheet_id))

                return sheets
    except Exception as e:
        print(f"读取工作表名称失败: {e}")
        return []

def get_xlsx_columns(xlsx_path, sheet_name=None):
    """获取XLSX文件的列名"""
    try:
        with zipfile.ZipFile(xlsx_path, 'r') as zf:
            # 获取工作表名称
            sheets = get_xlsx_sheet_names(xlsx_path)
            if not sheets:
                print("未找到工作表")
                return []

            # 如果未指定工作表，使用第一个
            if sheet_name is None:
                sheet_name = sheets[0][0]

            # 找到工作表对应的文件
            sheet_file = None
            for item in zf.namelist():
                if item.startswith('xl/worksheets/sheet') and item.endswith('.xml'):
                    # 需要关联工作表ID，简化处理：使用第一个工作表
                    sheet_file = item
                    break

            if not sheet_file:
                print("未找到工作表文件")
                return []

            # 读取共享字符串表
            shared_strings = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                with zf.open('xl/sharedStrings.xml') as f:
                    ss_content = f.read()
                    ss_root = ET.fromstring(ss_content)
                    ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    for si in ss_root.findall('.//main:si', ns):
                        t_elem = si.find('.//main:t', ns)
                        if t_elem is not None:
                            shared_strings.append(t_elem.text)

            # 读取工作表数据
            with zf.open(sheet_file) as f:
                content = f.read()
                root = ET.fromstring(content)

                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

                # 找到第一行（通常是标题行）
                rows = root.findall('.//main:row', ns)
                if not rows:
                    print("未找到行数据")
                    return []

                first_row = rows[0]
                cells = first_row.findall('.//main:c', ns)

                columns = []
                for cell in cells:
                    cell_type = cell.get('t')
                    cell_value_elem = cell.find('.//main:v', ns)
                    if cell_value_elem is not None:
                        cell_value = cell_value_elem.text
                        if cell_type == 's':  # 共享字符串
                            try:
                                value = shared_strings[int(cell_value)]
                            except:
                                value = f"[共享字符串索引错误: {cell_value}]"
                        else:
                            value = cell_value
                    else:
                        value = ""

                    columns.append(value)

                return columns
    except Exception as e:
        print(f"读取列名失败: {e}")
        return []

# 主程序
if __name__ == "__main__":
    ref_file = "new结构点预警天数统计_.xlsx"

    if not os.path.exists(ref_file):
        print(f"参考文件不存在: {ref_file}")
        sys.exit(1)

    print(f"分析参考文件: {ref_file}")
    sheets = get_xlsx_sheet_names(ref_file)
    print(f"工作表: {sheets}")

    if sheets:
        for sheet_name, sheet_id in sheets:
            print(f"\n工作表 '{sheet_name}' 的列名:")
            columns = get_xlsx_columns(ref_file, sheet_name)
            for i, col in enumerate(columns, 1):
                print(f"  {i}. {col}")

    # 检查当前输出文件
    current_file = "../data/temp/new结构点预警天数统计.xlsx"
    if os.path.exists(current_file):
        print(f"\n分析当前输出文件: {current_file}")
        sheets2 = get_xlsx_sheet_names(current_file)
        print(f"工作表: {sheets2}")

        if sheets2:
            for sheet_name, sheet_id in sheets2:
                print(f"\n工作表 '{sheet_name}' 的列名:")
                columns2 = get_xlsx_columns(current_file, sheet_name)
                for i, col in enumerate(columns2, 1):
                    print(f"  {i}. {col}")
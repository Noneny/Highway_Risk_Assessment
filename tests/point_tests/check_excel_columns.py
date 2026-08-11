import pandas as pd
import sys

# 读取参考Excel文件
ref_file = "new结构点预警天数统计_.xlsx"
try:
    df = pd.read_excel(ref_file)
    print(f"文件 '{ref_file}' 读取成功")
    print(f"数据形状: {df.shape}")
    print(f"列名: {list(df.columns)}")
    print("\n前几行数据:")
    print(df.head())
except Exception as e:
    print(f"读取文件失败: {e}")
    sys.exit(1)

# 检查当前输出的文件
current_file = "../data/temp/new结构点预警天数统计.xlsx"
try:
    current_df = pd.read_excel(current_file)
    print(f"\n当前输出文件 '{current_file}' 读取成功")
    print(f"数据形状: {current_df.shape}")
    print(f"列名: {list(current_df.columns)}")
    print("\n前几行数据:")
    print(current_df.head())
except Exception as e:
    print(f"读取当前文件失败: {e}")
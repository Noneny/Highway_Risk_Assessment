import pymysql
import pandas as pd
import os
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')


def get_month_year_string(date_str):
    """
    根据belong_date生成年月字符串
    格式: 25_6_25_7
    """
    try:
        # 解析日期
        current_date = datetime.strptime(date_str, '%Y-%m-%d')

        # 获取当前月份的年月
        current_year_short = str(current_date.year)[2:]  # 年份后两位
        current_month = str(current_date.month)  # 月份，不补零

        # 计算后一个月的日期
        if current_date.month == 12:
            next_month_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            next_month_date = current_date.replace(month=current_date.month + 1)

        # 获取下一个月的年月
        next_year_short = str(next_month_date.year)[2:]
        next_month = str(next_month_date.month)

        return f"{current_year_short}_{current_month}_{next_year_short}_{next_month}"
    except Exception as e:
        print(f"日期解析错误: {date_str}, 错误: {e}")
        return None


def read_database_config():
    """
    从统一 output_db.ini 读取数据库配置
    """
    from src.db_config import get_output_db_config
    db = get_output_db_config()

    db_config = {
        'host': db['host'],
        'port': db['port'],
        'user': db['user'],
        'password': db['password'],
        'database': db['database'],
        'point_table': db.get('point_risk_evaluation_table', 'point_risk_evaluation'),
        'line_table': db.get('line_risk_evaluation_table', 'line_risk_evaluation'),
        'net_table': db.get('net_risk_evaluation_table', 'net_risk_evaluation')
    }

    print("数据库配置读取成功")
    print(f"数据库: {db_config['database']}")
    print(f"结构点表: {db_config['point_table']}")
    print(f"路段表: {db_config['line_table']}")
    print(f"路网表: {db_config['net_table']}")

    return db_config


def create_directories():
    """
    创建必要的文件夹
    """
    directories = ['data/temp/compare/结构点', 'data/temp/compare/路段', 'data/temp/compare/路网']

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"创建文件夹: {directory}")
        else:
            print(f"文件夹已存在: {directory}")


def get_connection(db_config):
    """
    创建数据库连接
    """
    try:
        connection = pymysql.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        print("数据库连接成功")
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None


def get_distinct_belong_dates(connection, table_name):
    """
    获取表中所有不同的belong_date
    """
    try:
        with connection.cursor() as cursor:
            sql = f"SELECT DISTINCT belong_date FROM {table_name} ORDER BY belong_date"
            cursor.execute(sql)
            results = cursor.fetchall()

            dates = [result['belong_date'].strftime('%Y-%m-%d') for result in results]
            print(f"表 {table_name} 找到 {len(dates)} 个不同的belong_date")
            return dates
    except Exception as e:
        print(f"查询 {table_name} 的belong_date失败: {e}")
        return []


def export_table_data_by_date(connection, db_config, table_type):
    """
    导出指定类型表的数据，按belong_date拆分
    """
    # 根据表类型确定表名和文件夹
    if table_type == '结构点':
        table_name = db_config['point_table']
        folder = 'data/temp/compare/结构点'
        name_suffix = '结构点评估表'
    elif table_type == '路段':
        table_name = db_config['line_table']
        folder = 'data/temp/compare/路段'
        name_suffix = '路段评估表'
    elif table_type == '路网':
        table_name = db_config['net_table']
        folder = 'data/temp/compare/路网'
        name_suffix = '路网评估表'
    else:
        print(f"未知的表类型: {table_type}")
        return

    print(f"\n开始处理{table_type}表: {table_name}")

    # 获取所有不同的belong_date
    dates = get_distinct_belong_dates(connection, table_name)

    if not dates:
        print(f"表 {table_name} 中没有数据或belong_date字段不存在")
        return

    # 为每个belong_date生成Excel文件
    for date_str in dates:
        try:
            # 生成文件名
            date_code = get_month_year_string(date_str)
            if not date_code:
                continue

            filename = f"{date_code}{name_suffix}.xlsx"
            filepath = os.path.join(folder, filename)

            # 查询该日期的所有数据
            with connection.cursor() as cursor:
                sql = f"SELECT * FROM {table_name} WHERE belong_date = %s"
                cursor.execute(sql, (date_str,))
                results = cursor.fetchall()

                if results:
                    # 转换为DataFrame
                    df = pd.DataFrame(results)

                    # 保存为Excel
                    df.to_excel(filepath, index=False, engine='openpyxl')
                    print(f"  已生成: {filename} (共{len(df)}行数据)")
                else:
                    print(f"  {date_str} 没有数据")

        except Exception as e:
            print(f"处理 {date_str} 失败: {e}")


def main():
    """
    主函数
    """
    print("开始执行数据导出程序...")
    print("=" * 50)

    # 1. 创建文件夹
    create_directories()

    # 2. 读取配置文件
    db_config = read_database_config()
    if not db_config:
        return

    # 3. 连接数据库
    connection = get_connection(db_config)
    if not connection:
        return

    try:
        # 4. 处理三张表
        export_table_data_by_date(connection, db_config, '结构点')
        export_table_data_by_date(connection, db_config, '路段')
        export_table_data_by_date(connection, db_config, '路网')

        print("\n" + "=" * 50)
        print("数据导出完成!")
        print("文件保存在以下文件夹:")
        print("  data/temp/compare/结构点/  - 结构点评估表")
        print("  data/temp/compare/路段/    - 路段评估表")
        print("  data/temp/compare/路网/    - 路网评估表")

    except Exception as e:
        print(f"程序执行出错: {e}")
    finally:
        if connection:
            connection.close()
            print("数据库连接已关闭")


if __name__ == "__main__":
    main()
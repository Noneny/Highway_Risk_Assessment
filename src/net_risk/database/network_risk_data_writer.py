"""
网络风险数据写入器
将风险评估结果写入MySQL数据库
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import uuid
from .database_connector import DatabaseConnector


class NetworkRiskDataWriter:
    """网络风险数据写入器"""

    def __init__(self, database_connector: DatabaseConnector, period: str):
        """
        初始化数据写入器

        Args:
            database_connector: 数据库连接器实例
            period: 数据归属日期（格式：YYYY-MM-DD）
        """
        self.connector = database_connector
        self.period = period
        self.net_table = database_connector.net_table

        # Excel列名到数据库字段名的映射
        self.column_mapping = {
            '路网划分': 'net_comprehensive',
            '路段通行风险综合值': 'lines_risks',
            '路网密度通行风险值': 'net_density',
            '路网连通度通行风险值': 'net_conn',
            '路网基础风险值': 'F',
            '平均饱和度': 'average_satur',
            '交通流均衡性系数': 'traffic_balance',
            '动态调节系数': 'y',
            '30分钟到达率': 'arrival_rate',
            '1小时恢复通行率': 'recovery_rate',
            '附加风险修正系数': 'z',
            '路网通行风险值': 'net_risk',
            '风险等级': 'risk_level',
            '主要贡献部分': 'reason'
        }

        print(f"风险数据写入器初始化完成（归属日期: {self.period}）")

    def save_results(self, results_df: pd.DataFrame) -> bool:
        """
        保存评估结果到数据库

        Args:
            results_df: 包含评估结果的DataFrame

        Returns:
            bool: 保存是否成功
        """
        if not self.connector.enable_db or not self.connector.is_connected():
            print("⚠️  数据库功能未启用或连接失败，跳过数据库保存")
            return False

        if results_df.empty:
            print("⚠️  结果数据为空，无需保存")
            return False

        print(f"\n========== 保存评估结果到数据库 ==========")
        print(f"目标表: {self.net_table}")
        print(f"数据归属日期: {self.period}")
        print(f"待保存数据条数: {len(results_df)}")

        try:
            # 准备插入数据
            insert_data = self._prepare_insert_data(results_df)

            if not insert_data:
                print("⚠️  没有数据需要插入")
                return False

            # 检查是否已有相同归属日期的数据
            existing_count = self._check_existing_data()

            # 插入新数据
            success_count = self._insert_data(insert_data)

            print(f"\n✅ 数据库保存完成")
            print(f"  总记录数: {len(insert_data)}")
            print(f"  成功插入: {success_count}")
            print(f"  已有相同日期记录: {existing_count}")

            return success_count > 0

        except Exception as e:
            print(f"❌ 保存结果到数据库失败: {e}")
            return False

    def _prepare_insert_data(self, results_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        准备插入数据

        Args:
            results_df: 原始结果DataFrame

        Returns:
            List[Dict[str, Any]]: 准备好的插入数据列表
        """
        insert_data = []

        for _, row in results_df.iterrows():
            data = {
                'id': str(uuid.uuid4()),  # 生成唯一ID
                'belong_date': self.period,  # 添加归属日期
            }

            # 映射列名并添加数据
            for excel_col, db_col in self.column_mapping.items():
                if excel_col in row:
                    value = row[excel_col]

                    # 处理NaN值
                    if pd.isna(value):
                        if db_col in ['lines_risks', 'net_density', 'net_conn', 'average_satur',
                                      'traffic_balance', 'y', 'arrival_rate', 'recovery_rate',
                                      'z', 'net_risk']:
                            value = None  # 数值型字段设为NULL
                        else:
                            value = ''  # 字符串型字段设为空
                    elif isinstance(value, (np.int64, np.int32)):
                        value = int(value)
                    elif isinstance(value, (np.float64, np.float32)):
                        value = float(value)

                    data[db_col] = value
                else:
                    # 如果Excel中没有这个列，设置默认值
                    if db_col in ['lines_risks', 'net_density', 'net_conn', 'average_satur',
                                  'traffic_balance', 'y', 'arrival_rate', 'recovery_rate',
                                  'z', 'net_risk']:
                        data[db_col] = None  # 数值型字段设为NULL
                    else:
                        data[db_col] = ''  # 字符串型字段设为空

            insert_data.append(data)

        return insert_data

    def _check_existing_data(self) -> int:
        """
        检查是否已有相同归属日期的数据

        Returns:
            int: 已有记录数
        """
        try:
            with self.connector.connection.cursor() as cursor:
                check_sql = f"SELECT COUNT(*) as count FROM {self.net_table} WHERE belong_date = %s"
                cursor.execute(check_sql, (self.period,))
                result = cursor.fetchone()

                existing_count = result['count'] if result else 0

                if existing_count > 0:
                    print(f"⚠️  数据库中已存在归属日期为 {self.period} 的数据")
                    print(f"    当前有 {existing_count} 条记录，将替换为新数据")

                return existing_count

        except Exception as e:
            print(f"⚠️  检查已有数据失败: {e}")
            return 0

    def _insert_data(self, insert_data: List[Dict[str, Any]]) -> int:
        """
        插入数据到数据库

        Args:
            insert_data: 要插入的数据列表

        Returns:
            int: 成功插入的记录数
        """
        if not insert_data:
            return 0

        # 先删除相同belong_date的旧数据，实现替换而非追加
        all_columns = ['id', 'belong_date'] + list(self.column_mapping.values())
        columns = ', '.join([f"`{col}`" for col in all_columns])
        placeholders = ', '.join(['%s'] * len(all_columns))
        insert_sql = f"INSERT INTO {self.net_table} ({columns}) VALUES ({placeholders})"

        success_count = 0
        error_count = 0

        with self.connector.connection.cursor() as cursor:
            delete_sql = f"DELETE FROM {self.net_table} WHERE belong_date = %s"
            cursor.execute(delete_sql, (self.period,))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                print(f"  已删除 {deleted_count} 条相同归属日期的旧记录")
            for data in insert_data:
                try:
                    # 准备插入值
                    values = []
                    for col in all_columns:
                        value = data.get(col)

                        # 处理特殊值
                        if value is None:
                            values.append(None)
                        elif isinstance(value, str):
                            values.append(value)
                        elif isinstance(value, (int, float)):
                            values.append(value)
                        else:
                            values.append(str(value))

                    # 执行插入
                    cursor.execute(insert_sql, values)
                    success_count += 1

                except Exception as e:
                    error_count += 1
                    print(f"❌ 插入记录失败 (ID: {data.get('id')}): {e}")
                    # 继续处理其他记录

            # 提交事务
            self.connector.connection.commit()

        if error_count > 0:
            print(f"⚠️  插入失败记录数: {error_count}")

        return success_count

    def batch_save(self, results_df_list: List[pd.DataFrame]) -> Dict[str, int]:
        """
        批量保存多个结果DataFrame

        Args:
            results_df_list: 多个结果DataFrame列表

        Returns:
            Dict[str, int]: 保存统计信息
        """
        total_records = 0
        total_success = 0

        print(f"\n========== 批量保存评估结果 ==========")
        print(f"批量大小: {len(results_df_list)}")

        for i, results_df in enumerate(results_df_list, 1):
            print(f"\n处理第 {i} 个数据集...")
            print(f"  记录数: {len(results_df)}")

            if self.save_results(results_df):
                total_success += 1

            total_records += len(results_df)

        print(f"\n✅ 批量保存完成")
        print(f"  总数据集: {len(results_df_list)}")
        print(f"  总记录数: {total_records}")
        print(f"  成功保存数据集: {total_success}")

        return {
            'total_datasets': len(results_df_list),
            'total_records': total_records,
            'successful_datasets': total_success
        }
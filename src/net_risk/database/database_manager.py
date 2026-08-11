"""
数据库管理器
统一管理数据库操作，包括连接、表管理、数据操作等
"""

import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from .database_connector import DatabaseConnector
from .network_risk_data_writer import NetworkRiskDataWriter


class DatabaseManager:
    """数据库管理器类"""

    def __init__(self, config_manager, period: str):
        """
        初始化数据库管理器

        Args:
            config_manager: 配置管理器实例
            period: 数据归属日期（格式：YYYY-MM-DD）
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()
        self.period = period

        # 初始化组件
        self.connector = DatabaseConnector(config_manager)
        self.writer = NetworkRiskDataWriter(self.connector, period)

        # 获取数据库配置
        db_config = self.config.get('database', {})
        self.enable_db = db_config.get('enable', True)
        self.auto_create_db = db_config.get('auto_create_database', True)

        print("数据库管理器初始化完成")
        print(f"  数据库功能: {'启用' if self.enable_db else '禁用'}")
        print(f"  自动创建数据库: {'是' if self.auto_create_db else '否'}")
        print(f"  归属日期: {self.period}")

    def initialize_database(self) -> bool:
        """
        初始化数据库连接并确保表存在

        Returns:
            bool: 初始化是否成功
        """
        if not self.enable_db:
            print("数据库功能未启用，跳过初始化")
            return False

        print("\n========== 初始化数据库 ==========")

        # 1. 连接数据库
        if not self.connector.connect():
            print("❌ 数据库连接失败")
            return False

        # 2. 确保表存在
        if not self.connector.ensure_table_exists():
            print("❌ 表检查/创建失败")
            self.connector.disconnect()
            return False

        print("✅ 数据库初始化完成")
        return True

    def save_assessment_results(self, results_df: pd.DataFrame) -> bool:
        """
        保存风险评估结果到数据库

        Args:
            results_df: 评估结果DataFrame

        Returns:
            bool: 保存是否成功
        """
        if not self.enable_db:
            print("数据库功能未启用，跳过保存")
            return False

        if not self.connector.is_connected():
            print("数据库未连接，尝试重新连接...")
            if not self.initialize_database():
                print("❌ 数据库初始化失败，无法保存结果")
                return False

        return self.writer.save_results(results_df)

    def batch_save_results(self, results_df_list: List[pd.DataFrame]) -> Dict[str, int]:
        """
        批量保存多个评估结果到数据库

        Args:
            results_df_list: 多个结果DataFrame列表

        Returns:
            Dict[str, int]: 保存统计信息
        """
        if not self.enable_db:
            print("数据库功能未启用，跳过批量保存")
            return {'total_datasets': 0, 'total_records': 0, 'successful_datasets': 0}

        if not self.connector.is_connected():
            print("数据库未连接，尝试重新连接...")
            if not self.initialize_database():
                print("❌ 数据库初始化失败，无法保存结果")
                return {'total_datasets': 0, 'total_records': 0, 'successful_datasets': 0}

        return self.writer.batch_save(results_df_list)

    def query_results(self, filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        查询数据库中的评估结果

        Args:
            filters: 过滤条件，如 {'belong_date': '2025-12-01', 'net_comprehensive': 'XX路网'}

        Returns:
            pd.DataFrame: 查询结果
        """
        if not self.enable_db or not self.connector.is_connected():
            print("数据库功能未启用或未连接，无法查询")
            return pd.DataFrame()

        try:
            with self.connector.connection.cursor() as cursor:
                # 构建查询SQL
                sql = f"SELECT * FROM {self.connector.net_table}"
                params = []

                if filters:
                    conditions = []
                    for key, value in filters.items():
                        conditions.append(f"`{key}` = %s")
                        params.append(value)

                    if conditions:
                        sql += " WHERE " + " AND ".join(conditions)

                sql += " ORDER BY belong_date DESC, net_comprehensive ASC"

                cursor.execute(sql, params)
                results = cursor.fetchall()

                if results:
                    df = pd.DataFrame(results)
                    print(f"✅ 查询到 {len(df)} 条记录")
                    return df
                else:
                    print("⚠️  未查询到符合条件的记录")
                    return pd.DataFrame()

        except Exception as e:
            print(f"❌ 查询数据库失败: {e}")
            return pd.DataFrame()

    def get_recent_results(self, limit: int = 100) -> pd.DataFrame:
        """
        获取最近的评估结果

        Args:
            limit: 返回的最大记录数

        Returns:
            pd.DataFrame: 最近的评估结果
        """
        if not self.enable_db or not self.connector.is_connected():
            print("数据库功能未启用或未连接，无法查询")
            return pd.DataFrame()

        try:
            with self.connector.connection.cursor() as cursor:
                sql = f"SELECT * FROM {self.connector.net_table} ORDER BY create_time DESC LIMIT %s"
                cursor.execute(sql, (limit,))
                results = cursor.fetchall()

                if results:
                    df = pd.DataFrame(results)
                    print(f"✅ 获取到最近 {len(df)} 条记录")
                    return df
                else:
                    print("⚠️  数据库中暂无记录")
                    return pd.DataFrame()

        except Exception as e:
            print(f"❌ 查询最近记录失败: {e}")
            return pd.DataFrame()

    def delete_results(self, filters: Dict[str, Any]) -> int:
        """
        删除符合条件的记录（谨慎使用）

        Args:
            filters: 删除条件

        Returns:
            int: 删除的记录数
        """
        if not self.enable_db or not self.connector.is_connected():
            print("数据库功能未启用或未连接，无法删除")
            return 0

        try:
            # 先查询符合条件的记录数
            with self.connector.connection.cursor() as cursor:
                conditions = []
                params = []

                for key, value in filters.items():
                    conditions.append(f"`{key}` = %s")
                    params.append(value)

                count_sql = f"SELECT COUNT(*) as count FROM {self.connector.net_table} WHERE " + " AND ".join(conditions)
                cursor.execute(count_sql, params)
                result = cursor.fetchone()
                count = result['count'] if result else 0

                if count == 0:
                    print("⚠️  没有符合条件的记录需要删除")
                    return 0

                print(f"⚠️  将删除 {count} 条记录，过滤条件: {filters}")

                # 删除记录
                delete_sql = f"DELETE FROM {self.connector.net_table} WHERE " + " AND ".join(conditions)
                cursor.execute(delete_sql, params)
                self.connector.connection.commit()

                print(f"✅ 已删除 {cursor.rowcount} 条记录")
                return cursor.rowcount

        except Exception as e:
            print(f"❌ 删除记录失败: {e}")
            return 0

    def get_table_info(self) -> Dict[str, Any]:
        """
        获取数据表信息

        Returns:
            Dict[str, Any]: 表信息
        """
        if not self.enable_db or not self.connector.is_connected():
            print("数据库功能未启用或未连接，无法获取表信息")
            return {}

        try:
            with self.connector.connection.cursor() as cursor:
                # 获取表结构
                cursor.execute(f"DESCRIBE {self.connector.net_table}")
                columns = cursor.fetchall()

                # 获取记录数
                cursor.execute(f"SELECT COUNT(*) as count FROM {self.connector.net_table}")
                count_result = cursor.fetchone()
                total_records = count_result['count'] if count_result else 0

                # 获取不同归属日期的记录数
                cursor.execute(f"SELECT belong_date, COUNT(*) as count FROM {self.connector.net_table} GROUP BY belong_date ORDER BY belong_date DESC")
                date_stats = cursor.fetchall()

                # 获取不同路网的记录数
                cursor.execute(f"SELECT net_comprehensive, COUNT(*) as count FROM {self.connector.net_table} GROUP BY net_comprehensive ORDER BY count DESC")
                network_stats = cursor.fetchall()

                return {
                    'table_name': self.connector.net_table,
                    'database_name': self.connector.database,
                    'columns': columns,
                    'total_records': total_records,
                    'date_statistics': date_stats,
                    'network_statistics': network_stats
                }

        except Exception as e:
            print(f"❌ 获取表信息失败: {e}")
            return {}

    def cleanup(self):
        """清理资源"""
        print("清理数据库资源...")
        self.connector.disconnect()

    def __del__(self):
        """析构函数"""
        self.cleanup()
"""
数据库连接器 - 管理数据库连接和操作
基于原 main.py 中的数据库功能
"""

import configparser
import pymysql
from pymysql import Error
import pandas as pd
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from ..config.config_manager import get_config_manager


class DatabaseConnector:
    """数据库连接器类"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化数据库连接器

        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        self.config_manager = get_config_manager(config_path)
        self.config = self.config_manager.get_all_config()
        self.db_config = self.config.get('database', {})
        self.connection = None

    def is_enabled(self) -> bool:
        """
        检查数据库功能是否启用

        Returns:
            是否启用数据库功能
        """
        return self.db_config.get('enable', False)

    def connect(self) -> bool:
        """
        连接到数据库

        Returns:
            连接是否成功
        """
        if not self.is_enabled():
            print("⚠️  数据库功能未启用，跳过数据库连接")
            return False

        try:
            host = self.db_config.get('host', 'localhost')
            port = self.db_config.get('port', 3306)
            user = self.db_config.get('user', 'root')
            password = self.db_config.get('password', '')
            database = self.db_config.get('database', 'risk_assessment')

            print(f"正在连接数据库: {host}:{port}/{database}")
            print(f"用户名: {user}, 密码: {'*' * len(password) if password else '空'}")

            # 确保密码是字符串类型
            password_str = str(password) if password is not None else ''

            # 尝试连接到指定数据库
            self.connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password_str,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✅ 数据库连接成功: {host}:{port}/{database}")
            return True

        except pymysql.err.OperationalError as e:
            error_code = e.args[0]
            error_msg = e.args[1]

            if error_code == 1049:  # 数据库不存在错误
                print(f"⚠️ 数据库 '{database}' 不存在")

                if self.db_config.get('auto_create_database', True):
                    print(f"正在尝试自动创建数据库 '{database}'...")
                    if self._create_database_only():
                        # 重新尝试连接
                        print(f"正在重新连接到新创建的数据库 '{database}'...")
                        try:
                            self.connection = pymysql.connect(
                                host=host,
                                port=port,
                                user=user,
                                password=password_str,
                                database=database,
                                charset='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor
                            )
                            print(f"✅ 数据库连接成功: {host}:{port}/{database}")
                            return True
                        except Exception as e:
                            print(f"❌ 重新连接数据库失败: {e}")
                            return False
                    else:
                        print(f"❌ 自动创建数据库失败")
                        return False
                else:
                    print(f"❌ 数据库不存在，且未启用自动创建数据库功能")
                    print("请在数据库配置文件中设置 'auto_create_database: true' 或手动创建数据库")
                    return False
            else:
                print(f"❌ 数据库连接失败: {error_msg}")
                return False
        except Exception as e:
            print(f"❌ 数据库连接时发生未知错误: {e}")
            return False

    def _create_database_only(self) -> bool:
        """
        仅创建数据库（如果不存在）

        Returns:
            是否创建成功
        """
        try:
            host = self.db_config.get('host', 'localhost')
            port = self.db_config.get('port', 3306)
            user = self.db_config.get('user', 'root')
            password = self.db_config.get('password', '')
            database = self.db_config.get('database', 'risk_assessment')

            print(f"正在连接到MySQL服务器: {host}:{port}")
            password_str = str(password) if password is not None else ''

            temp_connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password_str,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )

            with temp_connection.cursor() as cursor:
                # 检查数据库是否存在
                check_db_sql = f"SHOW DATABASES LIKE '{database}';"
                cursor.execute(check_db_sql)
                db_exists = cursor.fetchone() is not None

                if not db_exists:
                    # 创建数据库
                    create_db_sql = f"CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                    cursor.execute(create_db_sql)
                    print(f"✅ 数据库 '{database}' 创建成功")
                else:
                    print(f"✅ 数据库 '{database}' 已存在")

            temp_connection.commit()
            temp_connection.close()
            return True

        except Exception as e:
            print(f"❌ 创建数据库失败: {e}")
            return False

    def create_table_if_not_exists(self, belong_date: str) -> bool:
        """
        创建数据表（如果不存在）

        Args:
            belong_date: 数据归属日期

        Returns:
            表创建/检查是否成功
        """
        if not self.connection:
            print("⚠️  数据库连接失败，无法创建表")
            return False

        try:
            table_name = self.db_config.get('table', 'line_risk_evaluation')

            with self.connection.cursor() as cursor:
                # 检查表是否存在
                check_table_sql = f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = '{self.db_config.get('database', 'risk_assessment')}'
                AND table_name = '{table_name}';
                """
                cursor.execute(check_table_sql)
                result = cursor.fetchone()
                table_exists = result['count'] > 0 if result else False

                if not table_exists:
                    # 根据图片中的字段结构创建表，添加id和belong_date字段
                    create_table_sql = f"""
                    CREATE TABLE {table_name} (
                        id VARCHAR(255) NOT NULL PRIMARY KEY COMMENT '主键',
                        belong_date DATE NOT NULL COMMENT '数据归属日期',
                        company VARCHAR(255) COMMENT '公司',
                        line VARCHAR(255) NOT NULL COMMENT '路段',
                        direction VARCHAR(255) NOT NULL COMMENT '运行方向',
                        level VARCHAR(255) COMMENT '等级',
                        length DOUBLE COMMENT '里程',
                        lane_num INT COMMENT '车道数',
                        F DOUBLE COMMENT '基础风险_F',
                        large_rate DOUBLE COMMENT '大车比例',
                        large_factor DOUBLE COMMENT '大车系数',
                        crowdedness DOUBLE COMMENT '拥挤度',
                        crowdedness_factor DOUBLE COMMENT '拥挤度系数',
                        longi_stability DOUBLE COMMENT '纵向稳定性',
                        stability_factor DOUBLE COMMENT '稳定性系数',
                        weather_alert INT COMMENT '气象预警频次',
                        alert_factor DOUBLE COMMENT '气象预警系数',
                        accident INT COMMENT '事故频数',
                        accident_per_km DOUBLE COMMENT '每公里频数',
                        accident_score INT COMMENT '事故分值',
                        accident_factor DOUBLE COMMENT '事故系数',
                        road_attribute DOUBLE COMMENT '道路属性系数',
                        line_risk DOUBLE COMMENT '风险值',
                        risk_level VARCHAR(255) COMMENT '风险等级',
                        reason VARCHAR(255) COMMENT '风险归因',
                        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_belong_date (belong_date),
                        INDEX idx_line_direction (line, direction),
                        INDEX idx_risk_level (risk_level),
                        INDEX idx_line_risk (line_risk)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='路段通行风险评价表';
                    """
                    cursor.execute(create_table_sql)
                    self.connection.commit()
                    print(f"✅ 数据表 '{table_name}' 创建成功")
                else:
                    print(f"✅ 数据表 '{table_name}' 已存在")

                    # 检查表结构，确保有id和belong_date字段
                    cursor.execute(f"DESCRIBE {table_name}")
                    columns = cursor.fetchall()
                    column_names = {col['Field'] for col in columns}

                    # 检查id字段
                    if 'id' not in column_names:
                        print("⚠️  检测到表缺少id字段，正在添加...")
                        # 添加id字段
                        alter_sql = f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN id VARCHAR(255) NOT NULL PRIMARY KEY COMMENT '主键' FIRST;
                        """
                        cursor.execute(alter_sql)
                        self.connection.commit()
                        print("✅ 已添加id字段并设置为主键")

                    # 检查belong_date字段
                    if 'belong_date' not in column_names:
                        print("⚠️  检测到表缺少belong_date字段，正在添加...")
                        # 添加belong_date字段
                        alter_sql = f"""
                        ALTER TABLE {table_name}
                        ADD COLUMN belong_date DATE NOT NULL DEFAULT '{belong_date}' COMMENT '数据归属日期' AFTER id;
                        """
                        cursor.execute(alter_sql)
                        self.connection.commit()
                        print("✅ 已添加belong_date字段")

                    # 检查是否已有相同belong_date的数据
                    check_date_sql = f"SELECT COUNT(*) as count FROM {table_name} WHERE belong_date = %s"
                    cursor.execute(check_date_sql, (belong_date,))
                    result = cursor.fetchone()
                    if result and result['count'] > 0:
                        print(f"⚠️  表中已存在belong_date为 {belong_date} 的数据")

            return True

        except Exception as e:
            print(f"❌ 创建/检查表失败: {e}")
            return False

    def save_results(self, result_df: pd.DataFrame, belong_date: str) -> bool:
        """
        保存结果到MySQL数据库（追加数据）

        Args:
            result_df: 结果DataFrame
            belong_date: 数据归属日期

        Returns:
            保存是否成功
        """
        if not self.connection:
            print("⚠️  数据库连接失败，跳过数据库保存")
            return False

        print(f"\n========== 保存结果到数据库 ==========")
        table_name = self.db_config.get('table', 'line_risk_evaluation')
        print(f"目标表: {self.db_config.get('database', 'risk_assessment')}.{table_name}")
        print(f"数据归属日期: {belong_date}")

        try:
            # 检查results_df是否为空
            if result_df is None or len(result_df) == 0:
                print("❌ 错误: 传入的结果DataFrame为空")
                return False

            print(f"传入的DataFrame形状: {result_df.shape}")

            # 准备数据映射（DataFrame列名 -> 数据库字段名）
            column_mapping = {
                '运营公司': 'company',
                '路段': 'line',
                '运行方向': 'direction',
                '等级': 'level',
                '里程': 'length',
                '基础风险_F总值': 'F',
                '车道数': 'lane_num',
                '交通流_大车比': 'large_rate',
                '交通流_大车系数': 'large_factor',
                '交通流_拥挤度': 'crowdedness',
                '交通流_拥挤度系数': 'crowdedness_factor',
                '交通流_纵向稳定': 'longi_stability',
                '交通流_纵向系数': 'stability_factor',
                '气象预警_频次': 'weather_alert',
                '气象预警_系数': 'alert_factor',
                '事故_频数': 'accident',
                '事故_每公里频数': 'accident_per_km',
                '事故_赋分': 'accident_score',
                '附加风险_事故系数': 'accident_factor',
                '附加风险_道路属性系数': 'road_attribute',
                '路段风险总评': 'line_risk',
                '风险等级': 'risk_level',
                '风险归因': 'reason'
            }

            # 检查哪些映射列在DataFrame中存在
            existing_columns = []
            missing_columns = []

            for excel_col in column_mapping.keys():
                if excel_col in result_df.columns:
                    existing_columns.append(excel_col)
                else:
                    missing_columns.append(excel_col)

            print(f"找到的映射列: {len(existing_columns)} 个")

            if missing_columns:
                print(f"缺失的映射列: {len(missing_columns)} 个")
                print("缺失的列名:")
                for col in missing_columns:
                    print(f"  - '{col}'")

            if not existing_columns:
                print("❌ 错误: 没有找到任何可用的列进行映射")
                return False

            # 构建插入数据
            insert_data = []
            for idx, row in result_df.iterrows():
                data = {
                    'id': str(uuid.uuid4()),  # 生成唯一ID
                    'belong_date': belong_date,  # 添加belong_date字段
                }

                for excel_col, db_col in column_mapping.items():
                    if excel_col in result_df.columns:
                        # 处理nan值，将其转换为None
                        value = row[excel_col]
                        if pd.isna(value):  # 检查是否为nan
                            data[db_col] = None
                        else:
                            data[db_col] = value

                insert_data.append(data)

            if not insert_data:
                print("❌ 错误: 没有可插入的数据")
                return False

            print(f"构建了 {len(insert_data)} 条插入记录")

            # 先删除相同belong_date的旧数据，实现替换而非追加
            all_columns = ['id', 'belong_date'] + list(column_mapping.values())
            columns = ', '.join([f"`{col}`" for col in all_columns])
            placeholders = ', '.join(['%s'] * len(all_columns))
            insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            with self.connection.cursor() as cursor:
                delete_sql = f"DELETE FROM {table_name} WHERE belong_date = %s"
                cursor.execute(delete_sql, (belong_date,))
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    print(f"  已删除 {deleted_count} 条相同归属日期的旧记录")

                # 插入新数据
                success_count = 0
                error_count = 0

                for i, data in enumerate(insert_data):
                    try:
                        # 准备插入值
                        values = []
                        for col in all_columns:
                            val = data.get(col)

                            # 处理特殊类型的值
                            if col == 'belong_date' and isinstance(val, str):
                                # 确保日期格式正确
                                try:
                                    # 尝试解析日期
                                    datetime.strptime(val, '%Y-%m-%d')
                                    values.append(val)
                                except ValueError:
                                    # 如果格式不正确，尝试其他格式
                                    print(f"警告: 日期格式不标准: {val}")
                                    values.append(None)
                            elif val is None or (isinstance(val, float) and pd.isna(val)):
                                values.append(None)
                            else:
                                values.append(val)

                        cursor.execute(insert_sql, values)
                        success_count += 1

                    except Exception as e:
                        line = data.get('line', '未知')
                        direction = data.get('direction', '未知')
                        print(f"    ❌ 插入记录失败 (记录 {i + 1}, 路段: {line}, 方向: {direction}): {e}")
                        error_count += 1

                self.connection.commit()

            print(f"✅ 数据库保存完成")
            print(f"   尝试插入: {len(insert_data)} 条记录")
            print(f"   成功: {success_count} 条记录")
            print(f"   失败: {error_count} 条记录")

            if success_count > 0:
                # 统计插入后的数据总量
                count_sql = f"SELECT COUNT(*) as total FROM {table_name}"
                with self.connection.cursor() as cursor:
                    cursor.execute(count_sql)
                    result = cursor.fetchone()
                    print(f"   当前表中共有: {result['total']} 条记录")

            return success_count > 0

        except Error as e:
            print(f"❌ 数据库插入失败: {e}")
            return False
        except Exception as e:
            print(f"❌ 保存到数据库时发生错误: {e}")
            return False

    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            print("✅ 数据库连接已关闭")

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
        self.db_config = self.config.get('database', {})
        print(f"配置已更新: {section}.{key} = {value}")


def test_database_connector():
    """测试数据库连接器"""
    import tempfile
    import os

    # 创建测试数据
    df_result = pd.DataFrame({
        '路段': ['G65', 'G65', 'G75', 'G75'],
        '运行方向': ['上行', '下行', '上行', '下行'],
        '基础风险_F总值': [85, 72, 90, 65],
        '路段风险总评': [92, 75, 88, 62],
        '风险等级': ['一级', '二级', '一级', '三级'],
        '风险归因': ['道路基础风险偏高', '运行指标正常', '道路基础风险偏高', '运行指标正常']
    })

    # 使用临时配置文件（禁用数据库）
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        config_content = """
[DATABASE]
enable = False
host = localhost
port = 3306
user = root
password =
database = risk_assessment
table = line_risk_evaluation
auto_create_database = True
"""
        f.write(config_content)
        config_path = f.name

    try:
        # 创建数据库连接器
        db_connector = DatabaseConnector(config_path)

        # 测试数据库功能启用状态
        enabled = db_connector.is_enabled()
        print(f"数据库功能启用状态: {enabled}")

        if enabled:
            # 测试连接
            connected = db_connector.connect()
            print(f"数据库连接状态: {connected}")

            if connected:
                # 测试表创建
                table_created = db_connector.create_table_if_not_exists('2025-12-01')
                print(f"表创建状态: {table_created}")

                if table_created:
                    # 测试数据保存
                    saved = db_connector.save_results(df_result, '2025-12-01')
                    print(f"数据保存状态: {saved}")

                # 断开连接
                db_connector.disconnect()

        print("数据库连接器测试完成")
        return True

    except Exception as e:
        print(f"数据库连接器测试失败: {e}")
        return False

    finally:
        # 清理临时文件
        os.unlink(config_path)


if __name__ == "__main__":
    test_database_connector()
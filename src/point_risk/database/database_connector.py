"""
数据库连接器
处理MySQL数据库的连接、创建表和写入操作
"""

import pymysql
from pymysql import Error
from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime
import uuid
import warnings

warnings.filterwarnings('ignore')


class DatabaseConnector:
    """数据库连接器类"""

    def __init__(self, db_config: Dict[str, Any]):
        """
        初始化数据库连接器

        Args:
            db_config: 数据库配置字典
        """
        self.db_config = db_config
        self.connection = None
        self._connect()

    def _connect(self):
        """连接到数据库"""
        if not self.db_config.get('enable', False):
            print("⚠️  数据库功能未启用，跳过数据库连接")
            return

        try:
            print(f"正在连接数据库: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
            print(f"用户名: {self.db_config['user']}, 密码: {'*' * len(str(self.db_config['password']))}")

            # 尝试连接到指定数据库
            self.connection = pymysql.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=str(self.db_config['password']) if self.db_config['password'] else '',
                database=self.db_config['database'],
                charset=self.db_config.get('charset', 'utf8mb4'),
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✅ 数据库连接成功: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")

        except pymysql.err.OperationalError as e:
            error_code = e.args[0]
            error_msg = e.args[1]

            if error_code == 1049:  # 数据库不存在错误
                print(f"⚠️ 数据库 '{self.db_config['database']}' 不存在")

                if self.db_config.get('auto_create_database', False):
                    print(f"正在尝试自动创建数据库 '{self.db_config['database']}'...")
                    if self._create_database():
                        # 重新尝试连接
                        print(f"正在重新连接到新创建的数据库 '{self.db_config['database']}'...")
                        try:
                            self.connection = pymysql.connect(
                                host=self.db_config['host'],
                                port=self.db_config['port'],
                                user=self.db_config['user'],
                                password=str(self.db_config['password']) if self.db_config['password'] else '',
                                database=self.db_config['database'],
                                charset=self.db_config.get('charset', 'utf8mb4'),
                                cursorclass=pymysql.cursors.DictCursor
                            )
                            print(f"✅ 数据库连接成功: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
                        except Exception as e:
                            print(f"❌ 重新连接数据库失败: {e}")
                            self.connection = None
                    else:
                        print(f"❌ 自动创建数据库失败")
                        self.connection = None
                else:
                    print(f"❌ 数据库不存在，且未启用自动创建数据库功能")
                    print("请在数据库配置文件中设置 'auto_create_database: true' 或手动创建数据库")
                    self.connection = None
            else:
                print(f"❌ 数据库连接失败: {error_msg}")
                self.connection = None
        except Exception as e:
            print(f"❌ 数据库连接时发生未知错误: {e}")
            self.connection = None

    def _create_database(self) -> bool:
        """创建数据库（如果不存在）"""
        try:
            # 先连接到MySQL服务器（不指定数据库）
            print(f"正在连接到MySQL服务器: {self.db_config['host']}:{self.db_config['port']}")
            password_str = str(self.db_config['password']) if self.db_config['password'] else ''

            temp_connection = pymysql.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=password_str,
                charset=self.db_config.get('charset', 'utf8mb4'),
                cursorclass=pymysql.cursors.DictCursor
            )

            with temp_connection.cursor() as cursor:
                # 检查数据库是否存在
                check_db_sql = f"SHOW DATABASES LIKE '{self.db_config['database']}';"
                cursor.execute(check_db_sql)
                db_exists = cursor.fetchone() is not None

                if not db_exists:
                    # 创建数据库
                    create_db_sql = f"CREATE DATABASE {self.db_config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                    cursor.execute(create_db_sql)
                    print(f"✅ 数据库 '{self.db_config['database']}' 创建成功")
                else:
                    print(f"✅ 数据库 '{self.db_config['database']}' 已存在")

            temp_connection.commit()
            temp_connection.close()
            return True

        except Exception as e:
            print(f"❌ 创建数据库失败: {e}")
            return False

    def create_point_alert_statistic_table(self, belong_date: str) -> bool:
        """
        创建气象预警统计表（对应原point_alert_statistic表）

        Args:
            belong_date: 数据归属日期

        Returns:
            是否成功
        """
        table_name = self.db_config.get('point_alert_statistic_table', 'point_alert_statistic')
        return self._create_table_if_not_exists(table_name, belong_date, self._get_alert_statistic_table_sql)

    def create_point_etc_traffic_evaluation_table(self, belong_date: str) -> bool:
        """
        创建门架流量评估表（对应原point_etc_traffic_evaluation表）

        Args:
            belong_date: 数据归属日期

        Returns:
            是否成功
        """
        table_name = self.db_config.get('point_etc_traffic_evaluation_table', 'point_etc_traffic_evaluation')
        return self._create_table_if_not_exists(table_name, belong_date, self._get_traffic_evaluation_table_sql)

    def create_point_risk_evaluation_table(self, belong_date: str) -> bool:
        """
        创建风险评价表（对应原point_risk_evaluation表）

        Args:
            belong_date: 数据归属日期

        Returns:
            是否成功
        """
        table_name = self.db_config.get('point_risk_evaluation_table', 'point_risk_evaluation')
        if not self._create_table_if_not_exists(table_name, belong_date, self._get_risk_evaluation_table_sql):
            return False

        # 迁移旧唯一键: uk_belong_date_point -> uk_belong_date_point_dir (包含direction)
        self._migrate_unique_key_for_risk_evaluation(table_name)
        return True

    def _migrate_unique_key_for_risk_evaluation(self, table_name: str):
        """将旧唯一键迁移为包含direction的新唯一键"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = 'uk_belong_date_point'")
                old_key_exists = cursor.fetchone() is not None

                if old_key_exists:
                    cursor.execute(f"SHOW INDEX FROM {table_name} WHERE Key_name = 'uk_belong_date_point_dir'")
                    new_key_exists = cursor.fetchone() is not None

                    if not new_key_exists:
                        print(f"检测到旧唯一键 uk_belong_date_point，正在迁移...")
                        cursor.execute(f"ALTER TABLE {table_name} DROP INDEX uk_belong_date_point")
                        cursor.execute(f"ALTER TABLE {table_name} ADD UNIQUE KEY uk_belong_date_point_dir (belong_date, point_name, direction)")
                        self.connection.commit()
                        print(f"唯一键已迁移: uk_belong_date_point -> uk_belong_date_point_dir (belong_date, point_name, direction)")
        except Exception as e:
            print(f"警告: 唯一键迁移失败（可能已迁移过）: {e}")

    def _create_table_if_not_exists(self, table_name: str, belong_date: str, get_table_sql_func) -> bool:
        """创建表（如果不存在）"""
        if not self.connection:
            print("⚠️  数据库连接失败，无法创建表")
            return False

        try:
            with self.connection.cursor() as cursor:
                # 检查表是否存在
                check_table_sql = f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = '{self.db_config['database']}'
                AND table_name = '{table_name}';
                """
                cursor.execute(check_table_sql)
                result = cursor.fetchone()
                table_exists = result['count'] > 0 if result else False

                if not table_exists:
                    # 创建新表
                    create_table_sql = get_table_sql_func(table_name)
                    cursor.execute(create_table_sql)
                    self.connection.commit()
                    print(f"✅ 表 '{table_name}' 创建成功")
                else:
                    print(f"✅ 表 '{table_name}' 已存在")

                    # 检查是否是新表结构（是否有id字段）
                    cursor.execute(f"DESCRIBE {table_name}")
                    columns = cursor.fetchall()
                    column_names = {col['Field'] for col in columns}

                    # 如果是旧表结构（没有id字段），需要重建表
                    if 'id' not in column_names and 'point_id' in column_names:
                        print(f"⚠️  检测到旧表结构，需要更新到新结构...")
                        # 备份旧表
                        backup_table_name = f"{table_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM {table_name}")
                        print(f"✅ 已备份旧表到 {backup_table_name}")

                        # 删除旧表
                        cursor.execute(f"DROP TABLE {table_name}")
                        print(f"✅ 已删除旧表 {table_name}")

                        # 创建新表
                        create_table_sql = get_table_sql_func(table_name)
                        cursor.execute(create_table_sql)
                        self.connection.commit()
                        print(f"✅ 已创建新表结构 {table_name}")

                        print(f"⚠️  注意：数据需要从 {backup_table_name} 手动迁移到新表 {table_name}")

                # 检查表结构，确保有belong_date字段
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                column_names = {col['Field'] for col in columns}

                if 'belong_date' not in column_names:
                    print(f"⚠️  检测到表 '{table_name}' 缺少belong_date字段，正在添加...")
                    # 添加belong_date字段
                    alter_sql = f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN belong_date DATE NOT NULL DEFAULT '{belong_date}' COMMENT '数据归属日期';
                    """
                    cursor.execute(alter_sql)
                    self.connection.commit()
                    print(f"✅ 表 '{table_name}' 已添加belong_date字段")

                # 检查是否已有相同belong_date的数据
                check_date_sql = f"SELECT COUNT(*) as count FROM {table_name} WHERE belong_date = %s"
                cursor.execute(check_date_sql, (belong_date,))
                result = cursor.fetchone()
                if result and result['count'] > 0:
                    print(f"⚠️  表 '{table_name}' 中已存在belong_date为 {belong_date} 的数据")

            return True

        except Exception as e:
            print(f"❌ 创建/检查表 '{table_name}' 失败: {e}")
            return False

    def _get_alert_statistic_table_sql(self, table_name: str) -> str:
        """获取气象预警统计表SQL"""
        return f"""
        CREATE TABLE {table_name} (
            point_name VARCHAR(255) NOT NULL COMMENT '点位描述',
            belong_date DATE NOT NULL COMMENT '数据归属日期',
            point_type VARCHAR(255) COMMENT '点位类型',
            stake_num VARCHAR(255) COMMENT '点位桩号',
            red_alert INT COMMENT '红色预警天数',
            orange_alert INT COMMENT '橙色预警天数',
            yellow_alert INT COMMENT '黄色预警天数',
            blue_alert INT COMMENT '蓝色预警天数',
            alert_days INT COMMENT '总预警天数',
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            PRIMARY KEY (belong_date, point_name),
            INDEX idx_point_name (point_name),
            INDEX idx_belong_date (belong_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='气象预警统计表';
        """

    def _get_traffic_evaluation_table_sql(self, table_name: str) -> str:
        """获取门架流量评估表SQL"""
        return f"""
        CREATE TABLE {table_name} (
            nearby_point VARCHAR(255) NOT NULL DEFAULT '' COMMENT '附近结构物点位描述',
            belong_date DATE NOT NULL COMMENT '数据归属日期',
            etc_id VARCHAR(100) NOT NULL COMMENT '门架编号',
            daily_busy_hour_traffic INT COMMENT '日均高峰小时流量',
            daily_largelrate DECIMAL(10,4) COMMENT '日均大型车占比',
            daily_busyhourdiscrete DECIMAL(10,4) COMMENT '日均高峰小时车速离散差',
            crowdedness DECIMAL(10,4) COMMENT '拥挤度',
            crowd_risk DECIMAL(10,4) COMMENT '拥挤度风险值',
            composition_risk DECIMAL(10,4) COMMENT '交通组成风险值',
            discrete_risk DECIMAL(10,4) COMMENT '离散差风险值',
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            PRIMARY KEY (belong_date, nearby_point),
            INDEX idx_etc_id (etc_id),
            INDEX idx_belong_date (belong_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门架流量评估表';
        """

    def _get_risk_evaluation_table_sql(self, table_name: str) -> str:
        """获取风险评价表SQL"""
        return f"""
        CREATE TABLE {table_name} (
            id CHAR(36) NOT NULL COMMENT '唯一标识（UUID）',
            belong_date DATE NOT NULL COMMENT '数据归属日期',
            point_type VARCHAR(100) COMMENT '点位类型',
            point_name VARCHAR(255) COMMENT '点位描述',
            asso_company VARCHAR(100) COMMENT '所属公司',
            district VARCHAR(100) COMMENT '所属区县',
            level VARCHAR(50) COMMENT '综合等级',
            associated_line VARCHAR(100) COMMENT '所属路段',
            line_num VARCHAR(50) COMMENT '路段编号',
            longitude DECIMAL(12,8) COMMENT '经度',
            latitude DECIMAL(12,8) COMMENT '纬度',
            stake_num VARCHAR(100) COMMENT '点位桩号',
            nearby_etc VARCHAR(100) COMMENT '附近门架名称',
            etc_id VARCHAR(100) COMMENT '门架编码',
            etc_lati DECIMAL(12,8) COMMENT '附近门架信息纬度',
            etc_longi DECIMAL(12,8) COMMENT '附近门架信息经度',
            direction VARCHAR(50) COMMENT '上下行',
            F DECIMAL(10,4) COMMENT '基础风险值',
            y DECIMAL(10,4) COMMENT '动态风险叠加',
            z DECIMAL(10,4) COMMENT '专项管控折减',
            point_risk DECIMAL(10,4) COMMENT '总风险值',
            F_reason VARCHAR(100) COMMENT '基础风险归因',
            y_reason VARCHAR(100) COMMENT '动态风险归因',
            risk_level VARCHAR(50) COMMENT '风险等级',
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            PRIMARY KEY (id),
            UNIQUE KEY uk_belong_date_point_dir (belong_date, point_name, direction),
            INDEX idx_belong_date (belong_date),
            INDEX idx_point_name (point_name),
            INDEX idx_risk_level (risk_level),
            INDEX idx_asso_company (asso_company),
            INDEX idx_associated_line (associated_line)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风险评价表';
        """

    def save_alert_statistics(self, df: pd.DataFrame, belong_date: str) -> bool:
        """
        保存气象预警统计数据到数据库

        Args:
            df: 预警统计数据DataFrame
            belong_date: 数据归属日期

        Returns:
            是否保存成功
        """
        table_name = self.db_config.get('point_alert_statistic_table', 'point_alert_statistic')
        return self._save_to_database(df, table_name, belong_date, self._prepare_alert_statistics_data)

    def save_traffic_evaluation(self, df: pd.DataFrame, belong_date: str,
                               etc_point_mapping: Dict = None) -> bool:
        """
        保存门架流量评估数据到数据库

        Args:
            df: 流量评估数据DataFrame
            belong_date: 数据归属日期
            etc_point_mapping: ETC门架与附近结构点的映射 {etc_id: [nearby_point, ...]}

        Returns:
            是否保存成功
        """
        table_name = self.db_config.get('point_etc_traffic_evaluation_table', 'point_etc_traffic_evaluation')
        return self._save_to_database(df, table_name, belong_date,
                                      lambda d, bd: self._prepare_traffic_evaluation_data(d, bd, etc_point_mapping))

    def save_risk_evaluation(self, df: pd.DataFrame, belong_date: str) -> bool:
        """
        保存风险评价数据到数据库

        Args:
            df: 风险评价数据DataFrame
            belong_date: 数据归属日期

        Returns:
            是否保存成功
        """
        table_name = self.db_config.get('point_risk_evaluation_table', 'point_risk_evaluation')
        return self._save_to_database(df, table_name, belong_date, self._prepare_risk_evaluation_data)

    def _save_to_database(self, df: pd.DataFrame, table_name: str, belong_date: str, prepare_data_func) -> bool:
        """通用数据库保存函数"""
        if not self.connection:
            print(f"⚠️  数据库连接失败，跳过保存到表 '{table_name}'")
            return False

        print(f"\n========== 保存结果到数据库 ==========")
        print(f"目标表: {self.db_config['database']}.{table_name}")
        print(f"数据归属日期: {belong_date}")

        try:
            # 检查df是否为空
            if df is None or len(df) == 0:
                print("❌ 错误: 传入的DataFrame为空")
                return False

            print(f"传入的DataFrame形状: {df.shape}")
            # 新增调试信息
            print(f"DataFrame列名: {list(df.columns)}")
            print(f"DataFrame前3行:\n{df.head(3)}")
            # 新增调试信息
            print(f"DataFrame列名: {list(df.columns)}")
            print(f"DataFrame前3行:\n{df.head(3)}")

            # 准备插入数据
            insert_data = prepare_data_func(df, belong_date)

            if not insert_data:
                print("❌ 错误: 没有可插入的数据")
                return False

            print(f"构建了 {len(insert_data)} 条插入记录")

            # 获取所有列名
            if insert_data:
                all_columns = list(insert_data[0].keys())
                columns = ', '.join([f"`{col}`" for col in all_columns])
                placeholders = ', '.join(['%s'] * len(all_columns))
                non_update_cols = {'id', 'create_time'}
                update_cols = [col for col in all_columns if col not in non_update_cols]
                update_clause = ', '.join([f"`{col}` = VALUES(`{col}`)" for col in update_cols])
                insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"

                with self.connection.cursor() as cursor:
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
                                        datetime.strptime(val, '%Y-%m-%d')
                                        values.append(val)
                                    except ValueError:
                                        print(f"警告: 日期格式不标准: {val}")
                                        values.append(None)
                                elif val is None or (isinstance(val, float) and pd.isna(val)):
                                    values.append(None)
                                else:
                                    values.append(val)

                            cursor.execute(insert_sql, values)
                            success_count += 1

                            # 每100条记录提交一次
                            if success_count % 100 == 0:
                                self.connection.commit()
                                print(f"已提交 {success_count} 条记录...")

                        except Exception as e:
                            error_count += 1
                            print(f"插入记录 {i} 失败: {e}")
                            # 继续处理其他记录

                    # 提交剩余记录
                    self.connection.commit()

                    print(f"\n数据库保存完成:")
                    print(f"  成功插入: {success_count} 条记录")
                    print(f"  失败插入: {error_count} 条记录")

                    if error_count == 0:
                        print("✅ 所有数据已成功保存到数据库")
                    else:
                        print(f"⚠️  有 {error_count} 条记录保存失败")

                    return success_count > 0

            else:
                print("❌ 错误: 插入数据为空")
                return False

        except Exception as e:
            print(f"❌ 保存到数据库失败: {e}")
            return False

    def _prepare_alert_statistics_data(self, df: pd.DataFrame, belong_date: str) -> List[Dict[str, Any]]:
        """准备气象预警统计数据"""
        insert_data = []

        # 映射列名
        column_mapping = {
            '点位类型': 'point_type',
            '点位描述': 'point_name',
            '点位桩号': 'stake_num',
            '红色预警天数': 'red_alert',
            '橙色预警天数': 'orange_alert',
            '黄色预警天数': 'yellow_alert',
            '蓝色预警天数': 'blue_alert',
            '总预警天数': 'alert_days'
        }

        for _, row in df.iterrows():
            data = {'belong_date': belong_date}

            for excel_col, db_col in column_mapping.items():
                if excel_col in df.columns:
                    value = row[excel_col]
                    if pd.isna(value):
                        data[db_col] = None
                    else:
                        data[db_col] = value

            # 检查必需字段
            if 'point_name' in data and data['point_name'] is not None:
                insert_data.append(data)

        return insert_data

    def _prepare_traffic_evaluation_data(self, df: pd.DataFrame, belong_date: str,
                                          etc_point_mapping: Dict = None) -> List[Dict[str, Any]]:
        """准备门架流量评估数据"""
        insert_data = []

        # 调试信息
        print(f"DEBUG - _prepare_traffic_evaluation_data: DataFrame列名: {list(df.columns)}")
        print(f"DEBUG - DataFrame形状: {df.shape}")
        if not df.empty:
            print(f"DEBUG - DataFrame前3行:")
            print(df.head(3))

        # 映射列名 - 扩展的映射，包含更多可能的列名变体
        column_mapping = {
            # 门架标识列
            '门架编码': 'etc_id',
            '门架编号': 'etc_id',
            'etc_id': 'etc_id',
            'ETC_ID': 'etc_id',
            'gantry_id': 'etc_id',
            '门架ID': 'etc_id',
            '当前门架': 'etc_id',

            # 流量统计列
            '日均高峰小时流量': 'daily_busy_hour_traffic',
            '高峰小时流量': 'daily_busy_hour_traffic',
            '日均流量': 'daily_busy_hour_traffic',
            '流量': 'daily_busy_hour_traffic',

            # 大型车比例列
            '日均大型车占比': 'daily_largelrate',
            '大型车占比': 'daily_largelrate',
            '大车比例': 'daily_largelrate',
            '货车比例': 'daily_largelrate',

            # 速度离散差列
            '日均高峰小时车速离散差': 'daily_busyhourdiscrete',
            '车速离散差': 'daily_busyhourdiscrete',
            '速度离散差': 'daily_busyhourdiscrete',
            '离散差': 'daily_busyhourdiscrete',

            # 拥挤度列
            '拥挤度': 'crowdedness',
            '拥堵度': 'crowdedness',
            '饱和度': 'crowdedness',

            # 风险值列
            '拥挤度风险值': 'crowd_risk',
            '拥堵风险值': 'crowd_risk',
            '交通组成风险值': 'composition_risk',
            '组成风险值': 'composition_risk',
            '离散差风险值': 'discrete_risk',
            '速度风险值': 'discrete_risk'
        }

        # 调试：显示所有列名和映射
        print(f"DEBUG - 可用列名: {list(df.columns)}")
        print(f"DEBUG - 映射列名: {list(set(column_mapping.keys()))}")

        # 检查哪些列在DataFrame中存在
        available_mapping = {}
        for excel_col, db_col in column_mapping.items():
            if excel_col in df.columns:
                available_mapping[excel_col] = db_col
                print(f"DEBUG - 找到列 '{excel_col}' -> '{db_col}'")

        # 如果没有找到任何映射，尝试模糊匹配
        if not available_mapping:
            print(f"DEBUG - 警告: 没有找到精确匹配的列!")
            print(f"DEBUG - 尝试模糊匹配...")

            for actual_col in df.columns:
                actual_col_lower = str(actual_col).lower()
                for excel_col, db_col in column_mapping.items():
                    excel_col_lower = str(excel_col).lower()
                    # 如果实际列名包含映射列名或反之
                    if excel_col_lower in actual_col_lower or actual_col_lower in excel_col_lower:
                        available_mapping[actual_col] = db_col
                        print(f"DEBUG - 模糊匹配: '{actual_col}' -> '{db_col}' (原映射: '{excel_col}')")
                        break

        # 如果还是没有映射，尝试使用第一列作为etc_id
        if not available_mapping and not df.empty and len(df.columns) > 0:
            first_col = df.columns[0]
            available_mapping[first_col] = 'etc_id'
            print(f"DEBUG - 使用第一列 '{first_col}' 作为etc_id")

        # 确保必需的列都有值
        required_fields = ['etc_id']
        for field in required_fields:
            if field not in available_mapping.values():
                print(f"DEBUG - 警告: 必需字段 '{field}' 没有映射到任何列")

        # 调试：显示所有列名和映射
        print(f"DEBUG - 可用列名: {list(df.columns)}")
        print(f"DEBUG - 映射列名: {list(column_mapping.keys())}")

        # 检查哪些列在DataFrame中存在
        available_mapping = {}
        for excel_col, db_col in column_mapping.items():
            if excel_col in df.columns:
                available_mapping[excel_col] = db_col
                print(f"DEBUG - 找到列 '{excel_col}' -> '{db_col}'")
            else:
                print(f"DEBUG - 警告: 列 '{excel_col}' 不存在于DataFrame中")

        if not available_mapping:
            print(f"DEBUG - 严重警告: 没有找到任何可映射的列!")
            # 如果连门架编码列都没有，尝试使用第一列作为etc_id
            if not df.empty and len(df.columns) > 0:
                first_col = df.columns[0]
                available_mapping[first_col] = 'etc_id'
                print(f"DEBUG - 使用第一列 '{first_col}' 作为etc_id")

        for idx, row in df.iterrows():
            data = {'belong_date': belong_date}

            # 使用available_mapping而不是column_mapping
            for excel_col, db_col in available_mapping.items():
                value = row[excel_col]
                if pd.isna(value):
                    data[db_col] = None
                else:
                    data[db_col] = value

            # 检查必需字段 - 更灵活的处理
            if 'etc_id' not in data or data['etc_id'] is None:
                # 尝试生成一个门架ID
                if '门架编码' in available_mapping:
                    print(f"DEBUG - 行 {idx}: etc_id为空")
                else:
                    # 如果没有门架编码列，使用索引或其他字段
                    if idx < len(df):
                        # 使用第一列作为门架ID
                        first_col = df.columns[0]
                        if first_col in row and pd.notna(row[first_col]):
                            data['etc_id'] = str(row[first_col])
                            print(f"DEBUG - 行 {idx}: 使用第一列 '{first_col}' 的值作为etc_id: {data['etc_id']}")
                        else:
                            # 使用索引作为门架ID
                            data['etc_id'] = f"gantry_{idx}"
                            print(f"DEBUG - 行 {idx}: 使用索引作为etc_id: {data['etc_id']}")

            # 确保所有必需的数据库字段都有值，即使是默认值
            required_db_fields = ['etc_id', 'daily_busy_hour_traffic', 'daily_largelrate', 'daily_busyhourdiscrete']
            for field in required_db_fields:
                if field not in data or data[field] is None:
                    if field == 'etc_id':
                        # etc_id应该已经有了
                        continue
                    else:
                        # 其他字段设置默认值
                        data[field] = 0
                        print(f"DEBUG - 行 {idx}: 字段 '{field}' 为空，设置默认值0")

            # 添加记录
            insert_data.append(data)

        print(f"DEBUG - 共准备了 {len(insert_data)} 条记录")
        if insert_data:
            print(f"DEBUG - 第一条记录示例: {insert_data[0]}")

        expanded_data = []
        etc_to_points = {}
        if etc_point_mapping:
            for point, eid in etc_point_mapping.items():
                etc_to_points.setdefault(eid, []).append(point)

        for record in insert_data:
            etc_id = record.get('etc_id', '')
            if etc_id in etc_to_points:
                for point in etc_to_points[etc_id]:
                    rec = dict(record)
                    rec['nearby_point'] = point
                    expanded_data.append(rec)
            else:
                record['nearby_point'] = ''
                expanded_data.append(record)

        print(f"DEBUG - 映射扩展后共 {len(expanded_data)} 条记录")

        return expanded_data

    def _prepare_risk_evaluation_data(self, df: pd.DataFrame, belong_date: str) -> List[Dict[str, Any]]:
        """准备风险评价数据"""
        insert_data = []

        # 映射列名 - 根据用户要求的新映射关系
        column_mapping = {
            '点位类型': 'point_type',
            '点位描述': 'point_name',
            '所属公司': 'asso_company',
            '所属区县': 'district',
            '综合等级': 'level',
            '所属路段': 'associated_line',
            '路段编号': 'line_num',
            '经度': 'longitude',
            '纬度': 'latitude',
            '点位桩号': 'stake_num',
            '附近门架名称': 'nearby_etc',
            '门架编码': 'etc_id',
            '附近门架信息纬度': 'etc_lati',
            '附近门架信息经度': 'etc_longi',
            '上下行': 'direction',
            '基础风险值': 'F',
            '动态风险叠加': 'y',
            '专项管控折减': 'z',
            '总风险值': 'point_risk',
            '基础风险归因': 'F_reason',
            '动态风险归因': 'y_reason',
            '风险等级': 'risk_level'
        }

        for _, row in df.iterrows():
            data = {
                'belong_date': belong_date,
                'id': str(uuid.uuid4())  # 生成UUID作为主键
            }

            for excel_col, db_col in column_mapping.items():
                if excel_col in df.columns:
                    value = row[excel_col]
                    if pd.isna(value):
                        data[db_col] = None
                    else:
                        data[db_col] = value

            # 检查必需字段
            if 'point_name' in data and data['point_name'] is not None:
                insert_data.append(data)

        return insert_data

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            try:
                self.connection.close()
                print("数据库连接已关闭")
            except Exception as e:
                print(f"关闭数据库连接时出错: {e}")

    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()


def create_database_connector_from_config(config_manager) -> Optional[DatabaseConnector]:
    """
    从配置管理器创建数据库连接器

    Args:
        config_manager: 配置管理器实例

    Returns:
        DatabaseConnector实例，如果数据库未启用则返回None
    """
    db_config = config_manager.get_database_config()

    if not db_config.get('enable', False):
        print("数据库功能未启用")
        return None

    return DatabaseConnector(db_config)

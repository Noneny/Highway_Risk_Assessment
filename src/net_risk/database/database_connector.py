"""
数据库连接器
管理MySQL数据库连接和基本操作
"""

import pymysql
from pymysql import Error
from typing import Dict, Any, Optional, Tuple
import uuid


class DatabaseConnector:
    """数据库连接器类"""

    def __init__(self, config_manager):
        """
        初始化数据库连接器

        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.get_all_config()

        # 获取数据库配置
        db_config = self.config.get('database', {})
        self.enable_db = db_config.get('enable', False)
        self.auto_create_db = db_config.get('auto_create_database', True)
        self.host = db_config.get('host', 'localhost')
        self.port = int(db_config.get('port', 3306))
        self.user = db_config.get('user', 'root')
        self.password = db_config.get('password', '')
        self.database = db_config.get('database', 'risk_assessment')
        self.net_table = db_config.get('net_table', 'net_risk_evaluation')
        self.charset = db_config.get('charset', 'utf8mb4')

        self.connection = None

        print("数据库连接器初始化完成")
        print(f"  数据库连接: {'启用' if self.enable_db else '禁用'}")
        print(f"  数据库: {self.database}")
        print(f"  数据表: {self.net_table}")

    def connect(self) -> bool:
        """
        连接到数据库

        Returns:
            bool: 连接是否成功
        """
        print(f"DEBUG: connect() called, enable_db={self.enable_db}, type={type(self.enable_db)}")
        if not self.enable_db:
            print("数据库功能未启用")
            return False

        try:
            # 尝试连接指定数据库
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✅ 成功连接到数据库 {self.database}")
            return True

        except pymysql.err.OperationalError as e:
            if e.args[0] == 1049:  # 数据库不存在
                print(f"❌ 数据库 {self.database} 不存在")
                if self.auto_create_db:
                    print(f"尝试自动创建数据库 {self.database}...")
                    if self.create_database():
                        # 重新连接
                        self.connection = pymysql.connect(
                            host=self.host,
                            port=self.port,
                            user=self.user,
                            password=self.password,
                            database=self.database,
                            charset=self.charset,
                            cursorclass=pymysql.cursors.DictCursor
                        )
                        print(f"✅ 成功创建并连接到数据库 {self.database}")
                        return True
                else:
                    print("请在配置文件中设置 'auto_create_database = True' 或手动创建数据库")
                    return False
            else:
                print(f"❌ 数据库连接失败: {e}")
                return False

        except Exception as e:
            print(f"❌ 数据库连接异常: {e}")
            return False

    def create_database(self) -> bool:
        """
        创建数据库（如果不存在）

        Returns:
            bool: 是否成功创建数据库
        """
        try:
            # 连接到MySQL服务器（不指定数据库）
            temp_connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor
            )

            with temp_connection.cursor() as cursor:
                # 创建数据库
                create_db_sql = f"CREATE DATABASE IF NOT EXISTS `{self.database}` CHARACTER SET {self.charset} COLLATE {self.charset}_unicode_ci;"
                cursor.execute(create_db_sql)
                temp_connection.commit()

                print(f"✅ 数据库 {self.database} 创建成功")

                # 切换到新创建的数据库
                cursor.execute(f"USE `{self.database}`;")

                # 创建表
                create_table_sql = f"""
                CREATE TABLE IF NOT EXISTS `{self.net_table}` (
                    id VARCHAR(255) NOT NULL PRIMARY KEY COMMENT '主键',
                    belong_date DATE NOT NULL COMMENT '数据归属日期',
                    net_comprehensive VARCHAR(255) NOT NULL COMMENT '路网划分',
                    lines_risks DOUBLE COMMENT '路段通行风险综合值',
                    net_density DOUBLE COMMENT '路网密度通行风险值',
                    net_conn DOUBLE COMMENT '路网连通度通行风险值',
                    F VARCHAR(255) COMMENT '路网基础风险值',
                    average_satur DOUBLE COMMENT '平均饱和度',
                    traffic_balance DOUBLE COMMENT '交通流均衡性系数',
                    y DOUBLE COMMENT '动态调节系数',
                    arrival_rate DOUBLE COMMENT '30分钟到达率',
                    recovery_rate DOUBLE COMMENT '1小时恢复通行率',
                    z DOUBLE COMMENT '附加风险修正系数',
                    net_risk DOUBLE COMMENT '路网风险值',
                    risk_level VARCHAR(255) COMMENT '路网风险分级',
                    reason VARCHAR(255) COMMENT '风险归因',
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_belong_date (belong_date),
                    INDEX idx_net_comprehensive (net_comprehensive),
                    INDEX idx_risk_level (risk_level)
                ) ENGINE=InnoDB DEFAULT CHARSET={self.charset} COLLATE={self.charset}_unicode_ci;
                """
                cursor.execute(create_table_sql)
                temp_connection.commit()

                print(f"✅ 数据表 {self.net_table} 创建成功")

                # 检查表结构是否需要更新（添加belong_date字段）
                cursor.execute(f"DESCRIBE {self.net_table}")
                columns = cursor.fetchall()
                column_names = {col['Field'] for col in columns}

                # 检查是否缺少belong_date字段
                if 'belong_date' not in column_names:
                    print(f"⚠️  检测到表 {self.net_table} 缺少 belong_date 字段，正在添加...")
                    alter_sql = f"ALTER TABLE {self.net_table} ADD COLUMN belong_date DATE NOT NULL COMMENT '数据归属日期' AFTER id;"
                    cursor.execute(alter_sql)
                    temp_connection.commit()
                    print(f"✅ 已添加 belong_date 字段")

            temp_connection.close()
            return True

        except Exception as e:
            print(f"❌ 创建数据库失败: {e}")
            return False

    def ensure_table_exists(self) -> bool:
        """
        确保数据表存在（如果连接已建立）

        Returns:
            bool: 表是否存在或创建成功
        """
        if not self.connection:
            print("数据库连接未建立")
            return False

        try:
            with self.connection.cursor() as cursor:
                # 检查表是否存在
                check_table_sql = f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = '{self.database}'
                AND table_name = '{self.net_table}';
                """
                cursor.execute(check_table_sql)
                result = cursor.fetchone()
                table_exists = result['count'] > 0 if result else False

                if not table_exists:
                    # 创建表
                    create_table_sql = f"""
                    CREATE TABLE `{self.net_table}` (
                        id VARCHAR(255) NOT NULL PRIMARY KEY COMMENT '主键',
                        belong_date DATE NOT NULL COMMENT '数据归属日期',
                        net_comprehensive VARCHAR(255) NOT NULL COMMENT '路网划分',
                        lines_risks DOUBLE COMMENT '路段通行风险综合值',
                        net_density DOUBLE COMMENT '路网密度通行风险值',
                        net_conn DOUBLE COMMENT '路网连通度通行风险值',
                        F VARCHAR(255) COMMENT '路网基础风险值',
                        average_satur DOUBLE COMMENT '平均饱和度',
                        traffic_balance DOUBLE COMMENT '交通流均衡性系数',
                        y DOUBLE COMMENT '动态调节系数',
                        arrival_rate DOUBLE COMMENT '30分钟到达率',
                        recovery_rate DOUBLE COMMENT '1小时恢复通行率',
                        z DOUBLE COMMENT '附加风险修正系数',
                        net_risk DOUBLE COMMENT '路网风险值',
                        risk_level VARCHAR(255) COMMENT '路网风险分级',
                        reason VARCHAR(255) COMMENT '风险归因',
                        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_belong_date (belong_date),
                        INDEX idx_net_comprehensive (net_comprehensive),
                        INDEX idx_risk_level (risk_level)
                    ) ENGINE=InnoDB DEFAULT CHARSET={self.charset} COLLATE={self.charset}_unicode_ci;
                    """
                    cursor.execute(create_table_sql)
                    self.connection.commit()
                    print(f"✅ 数据表 {self.net_table} 创建成功")
                else:
                    # 检查表结构是否需要更新
                    cursor.execute(f"DESCRIBE {self.net_table}")
                    columns = cursor.fetchall()
                    column_names = {col['Field'] for col in columns}

                    # 检查是否缺少belong_date字段
                    if 'belong_date' not in column_names:
                        print(f"⚠️  检测到表 {self.net_table} 缺少 belong_date 字段，正在添加...")
                        alter_sql = f"ALTER TABLE {self.net_table} ADD COLUMN belong_date DATE NOT NULL COMMENT '数据归属日期' AFTER id;"
                        cursor.execute(alter_sql)
                        self.connection.commit()
                        print(f"✅ 已添加 belong_date 字段")

                    print(f"✅ 数据表 {self.net_table} 已存在")

                return True

        except Exception as e:
            print(f"❌ 检查/创建表失败: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.connection:
            self.connection.close()
            print("数据库连接已关闭")
            self.connection = None

    def is_connected(self) -> bool:
        """检查是否已连接到数据库"""
        return self.connection is not None and self.connection.open

    def __del__(self):
        """析构函数，确保连接关闭"""
        self.disconnect()
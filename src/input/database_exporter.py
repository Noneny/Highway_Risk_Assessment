import pymysql
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import sys
import pandas as pd

from .config_manager import InputConfigManager, BASE_DIR


class DatabaseExporter:
    def __init__(self, config_manager: InputConfigManager = None):
        self.config_manager = config_manager or InputConfigManager()
        self.connection = None
        self.cursor = None

    def load_config(self) -> bool:
        db_config = self.config_manager.get_database_config()
        if not db_config:
            print("数据库配置为空")
            return False
        return True

    def connect_to_database(self) -> bool:
        try:
            db_config = self.config_manager.get_database_config()
            host = db_config['host']
            port = int(db_config['port'])
            user = db_config['user']
            password = db_config['password']
            database = db_config['database']
            charset = db_config.get('charset', 'utf8mb4')

            self.connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset=charset,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            print(f"成功连接到数据库: {database}")
            return True

        except pymysql.Error as e:
            print(f"数据库连接失败: {e}")
            return False
        except Exception as e:
            print(f"连接数据库时发生错误: {e}")
            return False

    def calculate_table_suffix(self, belong_date: str) -> str:
        try:
            date_obj = datetime.strptime(belong_date, '%Y-%m-%d')
            year = date_obj.year
            month = date_obj.month

            if month == 12:
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1

            current_suffix = f"{str(year)[-2:]}_{month}"
            next_suffix = f"{str(next_year)[-2:]}_{next_month}"
            return f"{current_suffix}_{next_suffix}"

        except ValueError as e:
            print(f"日期格式错误: {e}")
            return None
        except Exception as e:
            print(f"计算表格后缀时出错: {e}")
            return None

    def get_table_data(self, table_name: str) -> Optional[List[Dict]]:
        try:
            check_sql = f"SHOW TABLES LIKE '{table_name}'"
            self.cursor.execute(check_sql)
            if not self.cursor.fetchone():
                print(f"表格不存在: {table_name}")
                return None

            query_sql = f"SELECT * FROM {table_name}"
            self.cursor.execute(query_sql)
            data = self.cursor.fetchall()
            print(f"从表格 {table_name} 获取到 {len(data)} 条记录")

            for row in data:
                for key, value in row.items():
                    if isinstance(value, (datetime, timedelta)):
                        row[key] = str(value)

            return data

        except pymysql.Error as e:
            print(f"查询表格数据失败: {e}")
            return None
        except Exception as e:
            print(f"获取表格数据时出错: {e}")
            return None

    def save_to_json(self, data: List[Dict], output_path: str) -> bool:
        try:
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            print(f"数据已保存到: {output_path}")
            print(f"文件大小: {os.path.getsize(output_path) / 1024:.2f} KB")
            return True
        except Exception as e:
            print(f"保存JSON文件失败: {e}")
            return False

    def save_to_excel(self, data: List[Dict], output_path: str, sheet_name: str = "Sheet1") -> bool:
        try:
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            if not data:
                print(f"警告: 没有数据可保存到Excel文件: {output_path}")
                return False

            df = pd.DataFrame(data)
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"数据已保存到Excel文件: {output_path}")
            print(f"文件大小: {os.path.getsize(output_path) / 1024:.2f} KB")
            return True
        except ImportError:
            print("错误: 需要安装pandas和openpyxl库")
            return False
        except Exception as e:
            print(f"保存Excel文件失败: {e}")
            return False

    def _resolve_export_dir(self, config_key: str, fallback: str) -> str:
        export_config = self.config_manager.get_export_config()
        dir_path = export_config.get(config_key, fallback)
        resolved = self.config_manager.resolve_path(dir_path)
        os.makedirs(resolved, exist_ok=True)
        return str(resolved)

    def export_point_alert_to_json(self) -> bool:
        try:
            if not self.load_config():
                return False
            if not self.connect_to_database():
                return False

            export_config = self.config_manager.get_export_config()
            belong_date = export_config.get('belong_date', '2025-12-01')
            print(f"当前归属日期: {belong_date}")

            table_suffix = self.calculate_table_suffix(belong_date)
            if not table_suffix:
                return False

            table_name = f"point_alert_{table_suffix}"
            print(f"目标表格: {table_name}")

            export_dir = self._resolve_export_dir('point_alert_dir', 'data/input/weather_warnings')
            output_filename = f"{table_name}.json"
            output_path = os.path.join(export_dir, output_filename)
            print(f"导出路径: {output_path}")

            data = self.get_table_data(table_name)
            if data is None:
                return False
            if len(data) == 0:
                print(f"表格 {table_name} 为空，跳过导出")
                return True

            return self.save_to_json(data, output_path)

        except Exception as e:
            print(f"导出point_alert表格时出错: {e}")
            return False
        finally:
            self.close_resources()

    def export_district_alert_to_excel(self) -> bool:
        try:
            if not self.load_config():
                return False
            if not self.connect_to_database():
                return False

            export_config = self.config_manager.get_export_config()
            belong_date = export_config.get('belong_date', '2025-12-01')
            print(f"当前归属日期: {belong_date}")

            table_suffix = self.calculate_table_suffix(belong_date)
            if not table_suffix:
                return False

            table_name = f"district_alert_{table_suffix}"
            print(f"目标表格: {table_name}")

            export_dir = self._resolve_export_dir('other_dir', 'data/input')
            output_path = os.path.join(export_dir, "气象预警.xlsx")
            print(f"导出路径: {output_path}")

            data = self.get_table_data(table_name)
            if data is None:
                return False
            if len(data) == 0:
                print(f"表格 {table_name} 为空，跳过导出")
                return True

            return self.save_to_excel(data, output_path, sheet_name="气象预警")

        except Exception as e:
            print(f"导出district_alert表格时出错: {e}")
            return False
        finally:
            self.close_resources()

    def export_accident_to_excel(self) -> bool:
        try:
            if not self.load_config():
                return False
            if not self.connect_to_database():
                return False

            export_config = self.config_manager.get_export_config()
            belong_date = export_config.get('belong_date', '2025-12-01')
            print(f"当前归属日期: {belong_date}")

            table_suffix = self.calculate_table_suffix(belong_date)
            if not table_suffix:
                return False

            table_name = f"accident_{table_suffix}"
            print(f"目标表格: {table_name}")

            export_dir = self._resolve_export_dir('other_dir', 'data/input')
            output_path = os.path.join(export_dir, "交通事故.xlsx")
            print(f"导出路径: {output_path}")

            data = self.get_table_data(table_name)
            if data is None:
                return False
            if len(data) == 0:
                print(f"表格 {table_name} 为空，跳过导出")
                return True

            return self.save_to_excel(data, output_path, sheet_name="交通事故")

        except Exception as e:
            print(f"导出accident表格时出错: {e}")
            return False
        finally:
            self.close_resources()

    def export_all_tables(self) -> bool:
        try:
            if not self.load_config():
                return False
            if not self.connect_to_database():
                return False

            export_config = self.config_manager.get_export_config()
            belong_date = export_config.get('belong_date', '2025-12-01')
            print(f"当前归属日期: {belong_date}")
            print("=" * 50)

            table_suffix = self.calculate_table_suffix(belong_date)
            if not table_suffix:
                return False

            print("正在导出point_alert表格...")
            point_alert_table = f"point_alert_{table_suffix}"
            point_alert_data = self.get_table_data(point_alert_table)

            if point_alert_data is not None and len(point_alert_data) > 0:
                point_alert_dir = self._resolve_export_dir('point_alert_dir', 'data/input/weather_warnings')
                point_alert_path = os.path.join(point_alert_dir, f"{point_alert_table}.json")
                if self.save_to_json(point_alert_data, point_alert_path):
                    print(f"✓ point_alert表格导出成功: {point_alert_path}")
                else:
                    print("✗ point_alert表格导出失败")
            else:
                print(f"⚠ point_alert表格 {point_alert_table} 不存在或为空，跳过导出")
            print("-" * 30)

            print("正在导出district_alert表格...")
            district_alert_table = f"district_alert_{table_suffix}"
            district_alert_data = self.get_table_data(district_alert_table)

            if district_alert_data is not None and len(district_alert_data) > 0:
                other_dir = self._resolve_export_dir('other_dir', 'data/input')
                district_alert_path = os.path.join(other_dir, "气象预警.xlsx")
                if self.save_to_excel(district_alert_data, district_alert_path, sheet_name="气象预警"):
                    print(f"✓ district_alert表格导出成功: {district_alert_path}")
                else:
                    print("✗ district_alert表格导出失败")
            else:
                print(f"⚠ district_alert表格 {district_alert_table} 不存在或为空，跳过导出")
            print("-" * 30)

            print("正在导出accident表格...")
            accident_table = f"accident_{table_suffix}"
            accident_data = self.get_table_data(accident_table)

            if accident_data is not None and len(accident_data) > 0:
                other_dir = self._resolve_export_dir('other_dir', 'data/input')
                accident_path = os.path.join(other_dir, "交通事故.xlsx")
                if self.save_to_excel(accident_data, accident_path, sheet_name="交通事故"):
                    print(f"✓ accident表格导出成功: {accident_path}")
                else:
                    print("✗ accident表格导出失败")
            else:
                print(f"⚠ accident表格 {accident_table} 不存在或为空，跳过导出")
            print("=" * 50)

            return True

        except Exception as e:
            print(f"导出所有表格时出错: {e}")
            return False
        finally:
            self.close_resources()

    def close_resources(self) -> None:
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
        except Exception as e:
            print(f"关闭资源时出错: {e}")

    def list_available_tables(self) -> None:
        try:
            if not self.connect_to_database():
                return

            patterns = ['point_alert_%', 'district_alert_%', 'accident_%']
            all_tables = []

            for pattern in patterns:
                query = f"SHOW TABLES LIKE '{pattern}'"
                self.cursor.execute(query)
                tables = self.cursor.fetchall()
                all_tables.extend(tables)

            if all_tables:
                print("可用的表格列表:")
                print("-" * 50)
                table_types = {
                    'point_alert': '高速风险点气象预警数据',
                    'district_alert': '气象预警数据',
                    'accident': '交通事故数据'
                }
                for prefix, description in table_types.items():
                    print(f"\n{description}:")
                    found = False
                    for table in all_tables:
                        table_name = list(table.values())[0]
                        if table_name.startswith(prefix):
                            print(f"  {table_name}")
                            found = True
                    if not found:
                        print(f"  未找到{table_types[prefix]}表格")
            else:
                print("没有找到相关表格")

        except Exception as e:
            print(f"查询表格列表失败: {e}")
        finally:
            self.close_resources()

    def test_connection(self) -> bool:
        try:
            if not self.load_config():
                return False
            if not self.connect_to_database():
                return False
            print("数据库连接测试成功！")
            return True
        except Exception as e:
            print(f"数据库连接测试失败: {e}")
            return False
        finally:
            self.close_resources()

    def update_belong_date(self, new_date: str) -> bool:
        return self.config_manager.update_belong_date(new_date)

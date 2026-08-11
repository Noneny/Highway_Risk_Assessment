"""
配置更新模块
从 MySQL 数据库 freeway_risk_config 中读取各配置表，更新 config/ 下的 ini 文件
每个表对应一个 ini 文件，表结构为: section, config_key, config_value
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pymysql

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"

INI_FILES = ["compare", "input_db", "line_risk", "net_risk", "output_db", "point_risk"]
DB_CONFIG_DATABASE = "freeway_risk_config"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3306
DEFAULT_USER = "root"
DEFAULT_PASSWORD = ""
DEFAULT_CHARSET = "utf8mb4"


class ConfigUpdater:
    """从 MySQL 数据库 freeway_risk_config 同步配置到 config/ 下的 ini 文件"""

    def __init__(self, host: str = None, port: int = None,
                 user: str = None, password: str = None,
                 charset: str = None) -> None:
        self.connection = None
        self.cursor = None
        self._host = host or os.getenv("RISK_CONFIG_DB_HOST", DEFAULT_HOST)
        self._port = port or int(os.getenv("RISK_CONFIG_DB_PORT", str(DEFAULT_PORT)))
        self._user = user or os.getenv("RISK_CONFIG_DB_USER", DEFAULT_USER)
        self._password = password or os.getenv("RISK_CONFIG_DB_PASSWORD", DEFAULT_PASSWORD)
        self._charset = charset or os.getenv("RISK_CONFIG_DB_CHARSET", DEFAULT_CHARSET)

    def connect(self) -> bool:
        """连接到 freeway_risk_config 数据库"""
        try:
            self.connection = pymysql.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=DB_CONFIG_DATABASE,
                charset=self._charset,
                cursorclass=pymysql.cursors.DictCursor,
            )
            self.cursor = self.connection.cursor()
            return True
        except pymysql.Error as e:
            print(f"  ❌ 数据库 {DB_CONFIG_DATABASE} 连接失败: {e}")
            return False

    def close(self) -> None:
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

    def _table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        self.cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
        return self.cursor.fetchone() is not None

    def _fetch_config_data(self, table_name: str) -> Dict[Tuple[str, str], str]:
        """
        从数据库表中读取所有配置项
        返回 {(section, config_key): config_value}
        """
        data: Dict[Tuple[str, str], str] = {}
        try:
            if not self._table_exists(table_name):
                print(f"  ⚠ 表 {table_name} 不存在，跳过")
                return data

            self.cursor.execute(f"SELECT * FROM {table_name}")
            rows = self.cursor.fetchall()

            for row in rows:
                section = str(row.get("section", "")).strip()
                key = str(row.get("config_key", row.get("key", ""))).strip()
                value = str(row.get("config_value", row.get("value", "")))
                if section and key:
                    data[(section, key)] = value

            print(f"  从表 {table_name} 读取到 {len(data)} 项配置")
        except pymysql.Error as e:
            print(f"  ❌ 读取表 {table_name} 失败: {e}")
        return data

    def _generate_ini_file(
            self, ini_name: str, db_data: Dict[Tuple[str, str], str]
    ) -> None:
        """当 ini 文件缺失时，依据数据库配置表自动生成新的 ini 文件"""
        ini_path = CONFIG_DIR / f"{ini_name}.ini"
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        sections: Dict[str, Dict[str, str]] = {}
        for (section, key), value in db_data.items():
            sections.setdefault(section, {})[key] = value

        lines: List[str] = []
        for section, kv in sections.items():
            lines.append(f"[{section}]\n")
            for key, value in kv.items():
                lines.append(f"{key} = {value}\n")
            lines.append("\n")

        with open(ini_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"  ✅ {ini_name}.ini: 从数据库创建，包含 {len(db_data)} 项配置")

    def _update_ini_file(
            self, ini_name: str, db_data: Dict[Tuple[str, str], str]
    ) -> None:
        """
        用数据库中的值更新 ini 文件，保留注释和原有格式；
        若文件不存在则自动生成
        """
        ini_path = CONFIG_DIR / f"{ini_name}.ini"
        if not ini_path.exists():
            self._generate_ini_file(ini_name, db_data)
            return

        with open(ini_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_section = ""
        modified_count = 0

        for i, line in enumerate(lines):
            section_match = re.match(r"^\s*\[(.+)\]\s*(?:[#;].*)?$", line)
            if section_match:
                current_section = section_match.group(1).strip()
                continue

            kv_match = re.match(
                r"^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*=\s*)(.*?)(\s*(?:[#;].*)?)\s*$",
                line,
            )
            if kv_match and current_section:
                key = kv_match.group(2)
                if (current_section, key) in db_data:
                    new_value = db_data[(current_section, key)]
                    leading = kv_match.group(1)
                    eq_sp = kv_match.group(3)
                    trailing = kv_match.group(5)
                    if trailing:
                        trailing = " " + trailing.strip()
                    lines[i] = f"{leading}{key}{eq_sp}{new_value}{trailing}\n"
                    modified_count += 1

        if modified_count > 0:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"  ✅ {ini_name}.ini: 更新了 {modified_count} 项")
        else:
            print(f"  ⚪ {ini_name}.ini: 无需更新")

    def run(self) -> bool:
        """执行全部配置同步流程"""
        print("=" * 60)
        print("  配置更新: 从数据库同步 config/ 目录下的 ini 文件")
        print("=" * 60)

        if not self.connect():
            print(f"  数据库: {DB_CONFIG_DATABASE}")
            return False

        try:
            for ini_name in INI_FILES:
                print(f"\n  --- {ini_name}.ini ---")
                db_data = self._fetch_config_data(ini_name)
                if db_data:
                    self._update_ini_file(ini_name, db_data)
            print("\n" + "=" * 60)
            return True
        finally:
            self.close()


def run_config_update(host: str = None, port: int = None,
                      user: str = None, password: str = None,
                      charset: str = None) -> bool:
    """外部调用入口，返回是否执行成功"""
    updater = ConfigUpdater(host=host, port=port, user=user,
                            password=password, charset=charset)
    return updater.run()


if __name__ == '__main__':
    run_config_update()

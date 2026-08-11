"""
统一数据库配置读取模块
所有子模块通过此模块获取数据库连接配置
"""

import configparser
import os
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
DB_CONFIG_PATH = str(BASE_DIR / "config" / "output_db.ini")


def _env(name: str, fallback: str) -> str:
    """读取非空环境变量，便于容器部署时覆盖INI配置。"""
    value = os.getenv(name)
    return value if value not in (None, "") else fallback


def _env_bool(name: str, fallback: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return fallback
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_output_db_config() -> Dict[str, Any]:
    """读取统一的 output_db.ini 数据库配置"""
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH, encoding='utf-8')

    section = 'DATABASE'
    if not config.has_section(section):
        return {}

    return {
        'enable': _env_bool(
            'RISK_OUTPUT_DB_ENABLE', config.getboolean(section, 'enable', fallback=True)
        ),
        'auto_create_database': _env_bool(
            'RISK_OUTPUT_DB_AUTO_CREATE',
            config.getboolean(section, 'auto_create_database', fallback=True),
        ),
        'host': _env('RISK_OUTPUT_DB_HOST', config.get(section, 'host', fallback='localhost')),
        'port': int(_env('RISK_OUTPUT_DB_PORT', str(config.getint(section, 'port', fallback=3306)))),
        'user': _env('RISK_OUTPUT_DB_USER', config.get(section, 'user', fallback='root')),
        'password': _env('RISK_OUTPUT_DB_PASSWORD', config.get(section, 'password', fallback='')),
        'database': _env(
            'RISK_OUTPUT_DB_NAME', config.get(section, 'database', fallback='freeway_risk_test')
        ),
        'charset': _env('RISK_OUTPUT_DB_CHARSET', config.get(section, 'charset', fallback='utf8mb4')),
        # 各模块表名
        'point_alert_statistic_table': config.get(section, 'point_alert_statistic_table',
                                                  fallback='point_alert_statistic'),
        'point_etc_traffic_evaluation_table': config.get(section, 'point_etc_traffic_evaluation_table',
                                                        fallback='point_etc_traffic_evaluation'),
        'point_risk_evaluation_table': config.get(section, 'point_risk_evaluation_table',
                                                  fallback='point_risk_evaluation'),
        'line_risk_evaluation_table': config.get(section, 'line_risk_evaluation_table',
                                                 fallback='line_risk_evaluation'),
        'net_risk_evaluation_table': config.get(section, 'net_risk_evaluation_table',
                                                fallback='net_risk_evaluation'),
        'risk_contrast_table': config.get(section, 'risk_contrast_table', fallback='risk_contrast'),
    }


def get_belong_date() -> str:
    """从 output_db.ini [DATES] 读取全局归属日期"""
    config = configparser.ConfigParser()
    config.read(DB_CONFIG_PATH, encoding='utf-8')
    return _env(
        'RISK_BELONG_DATE',
        config.get('DATES', 'belong_date', fallback='2025-12-01'),
    )


def get_date_range(belong_date: str = None) -> Tuple[str, str]:
    """根据 belong_date 计算 start_date(=belong_date) 和 end_date(下一个月的最后一天)"""
    if belong_date is None:
        belong_date = get_belong_date()
    dt = datetime.strptime(belong_date, '%Y-%m-%d')
    year, month = dt.year, dt.month
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    last_day = monthrange(next_year, next_month)[1]
    end_date = f"{next_year}-{next_month:02d}-{last_day:02d}"
    return belong_date, end_date

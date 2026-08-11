"""
数据模型定义
定义高速公路路网风险评估系统中的核心数据模型
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import pandas as pd


@dataclass
class RoadSegment:
    """路段基础信息"""
    name: str  # 路段名称
    length: float  # 路段长度（km）
    design_flow: float  # 设计流量
    company: str  # 所属公司
    route_name: Optional[str] = None  # 路线名称

    def __str__(self):
        return f"{self.name} ({self.company}, {self.length}km)"

    @classmethod
    def from_config_dict(cls, name: str, config_dict: Dict[str, Any]) -> 'RoadSegment':
        """从配置字典创建路段对象"""
        return cls(
            name=name,
            length=config_dict.get('length', 0.0),
            design_flow=config_dict.get('design_flow', 0.0),
            company=config_dict.get('company', '')
        )


@dataclass
class TrafficFlowData:
    """门架流量数据"""
    road_name: str  # 路段名称（标准化后）
    peak_hour_flow: float  # 日均高峰小时流量
    data_source: str  # 数据来源
    calculation_date: Optional[datetime] = None  # 计算日期

    def __str__(self):
        return f"{self.road_name}: {self.peak_hour_flow} 辆/小时"


@dataclass
class RoadRiskData:
    """路段风险数据"""
    road_name: str  # 路段名称（标准化后）
    risk_value: float  # 风险值（压缩后）
    original_risk_value: Optional[float] = None  # 原始风险值
    risk_compression_ratio: float = 1.0  # 风险压缩比例

    def __str__(self):
        return f"{self.road_name}: {self.risk_value:.2f}"


@dataclass
class EventData:
    """交通事故事件数据"""
    road_name: str  # 原始路段名称
    normalized_road_name: str  # 标准化路段名称
    happen_time: datetime  # 发生时间
    release_time: datetime  # 恢复时间
    handling_time_minutes: float  # 处理时长（分钟）
    event_id: Optional[str] = None  # 事件ID

    def __str__(self):
        return f"{self.normalized_road_name}: {self.handling_time_minutes:.1f}分钟"


@dataclass
class NetworkTopology:
    """路网拓扑特征"""
    company: str  # 公司名称
    adjacent_roads: int  # 相邻路段数
    nodes: int  # 节点数
    total_length: float  # 总长度（km）
    area: float  # 管辖面积（km²）

    @property
    def density(self) -> float:
        """计算路网密度（km/百km²）"""
        return self.total_length / (self.area / 100) if self.area > 0 else 0.0

    @property
    def connectivity(self) -> float:
        """计算连通度指标 C'"""
        return self.adjacent_roads / self.nodes if self.nodes > 0 else 0.0

    def __str__(self):
        return f"{self.company}: 密度={self.density:.2f} km/百km², 连通度={self.connectivity:.3f}"


@dataclass
class RiskThresholds:
    """风险计算阈值参数"""
    reference_density: float  # 参考密度
    risk_compression_ratio: float  # 风险压缩比例

    # 饱和度调节系数阈值
    saturation_thresholds: List[Dict[str, float]]

    # 均衡性调节系数阈值
    equilibrium_thresholds: List[Dict[str, float]]

    # 事故响应阈值
    arrival_threshold: float  # 到达率阈值
    recovery_threshold: float  # 恢复率阈值
    arrival_coef_high: float  # 到达率高的系数
    arrival_coef_low: float  # 到达率低的系数
    recovery_coef_high: float  # 恢复率高的系数
    recovery_coef_low: float  # 恢复率低的系数

    # 风险等级阈值
    risk_levels: List[Dict[str, Any]]


@dataclass
class BasicRiskComponents:
    """基础风险各组成部分"""
    company: str  # 公司/路网
    R: float  # 路段通行风险综合值
    C: float  # 路网连通度通行风险值
    B: float  # 路网密度通行风险值
    F1: float  # 最大风险值
    F2: float  # 第二风险值
    F3: float  # 第三风险值
    basic_risk: float  # 基础风险值

    def __str__(self):
        return f"{self.company}: R={self.R:.2f}, C={self.C:.2f}, B={self.B:.2f}, 基础风险={self.basic_risk:.2f}"


@dataclass
class DynamicCoefficientData:
    """动态调节系数数据"""
    company: str  # 公司/路网
    avg_saturation: float  # 平均饱和度
    equilibrium_coefficient: float  # 交通流均衡性系数
    saturation_coefficient: float  # 饱和度调节系数
    equilibrium_adjust_coefficient: float  # 均衡性调节系数
    dynamic_coefficient: float  # 动态调节系数

    def __str__(self):
        return f"{self.company}: 饱和度={self.avg_saturation:.4f}, 动态系数={self.dynamic_coefficient:.4f}"


@dataclass
class AdditionalCoefficientData:
    """附加风险修正系数数据"""
    company: str  # 公司/路网
    total_events: int  # 总事件数
    J1_actual: int  # 实际30分钟到达数
    T1_actual: int  # 实际1小时恢复数
    J_rate_actual: float  # 实际到达率
    T_rate_actual: float  # 实际恢复率
    J_rate_adjusted: float  # 调整后到达率
    T_rate_adjusted: float  # 调整后恢复率
    J1_adjusted: int  # 调整后30分钟到达数
    T1_adjusted: int  # 调整后1小时恢复数
    arrival_coefficient: float  # 到达率系数
    recovery_coefficient: float  # 恢复率系数
    additional_coefficient: float  # 附加风险修正系数

    def __str__(self):
        return f"{self.company}: J={self.J_rate_adjusted:.4f}, T={self.T_rate_adjusted:.4f}, 附加系数={self.additional_coefficient:.4f}"


@dataclass
class NetworkRiskAssessment:
    """路网风险评估结果（按公司/路网）"""
    company: str  # 公司/路网名称
    basic_risk: float  # 基础风险值
    dynamic_coefficient: float  # 动态调节系数
    additional_coefficient: float  # 附加风险修正系数
    network_risk: float  # 路网通行风险值
    risk_level: str  # 风险等级
    calculation_date: datetime  # 计算日期

    def __str__(self):
        return f"{self.company}: {self.network_risk:.2f} ({self.risk_level})"


@dataclass
class RiskAttributionResult:
    """风险归因分析结果"""
    company: str  # 公司/路网
    basic_risk_contribution: float  # 基础风险贡献值
    dynamic_risk_contribution: float  # 动态调节贡献值
    additional_risk_contribution: float  # 附加风险贡献值
    basic_risk_percent: float  # 基础风险贡献度（%）
    dynamic_risk_percent: float  # 动态调节贡献度（%）
    additional_risk_percent: float  # 附加风险贡献度（%）
    main_contributor: str  # 主要贡献部分
    contribution_description: str  # 贡献度描述

    def __str__(self):
        return f"{self.company}: 基础{self.basic_risk_percent:.1f}%, 动态{self.dynamic_risk_percent:.1f}%, 附加{self.additional_risk_percent:.1f}%"


@dataclass
class RiskAssessmentResult:
    """风险评价最终结果（数据库输出格式）"""
    id: str  # 唯一标识（UUID）
    belong_date: str  # 数据归属日期
    net_comprehensive: str  # 路网划分
    lines_risks: Optional[float] = None  # 路段通行风险综合值
    net_density: Optional[float] = None  # 路网密度通行风险值
    net_conn: Optional[float] = None  # 路网连通度通行风险值
    F: Optional[float] = None  # 路网基础风险值
    average_satur: Optional[float] = None  # 平均饱和度
    traffic_balance: Optional[float] = None  # 交通流均衡性系数
    y: Optional[float] = None  # 动态调节系数
    arrival_rate: Optional[float] = None  # 30分钟到达率
    recovery_rate: Optional[float] = None  # 1小时恢复通行率
    z: Optional[float] = None  # 附加风险修正系数
    net_risk: Optional[float] = None  # 路网风险值
    risk_level: Optional[str] = None  # 路网风险分级
    reason: Optional[str] = None  # 风险归因

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库插入字典格式"""
        return {
            'id': self.id,
            'belong_date': self.belong_date,
            'net_comprehensive': self.net_comprehensive,
            'lines_risks': self.lines_risks,
            'net_density': self.net_density,
            'net_conn': self.net_conn,
            'F': self.F,
            'average_satur': self.average_satur,
            'traffic_balance': self.traffic_balance,
            'y': self.y,
            'arrival_rate': self.arrival_rate,
            'recovery_rate': self.recovery_rate,
            'z': self.z,
            'net_risk': self.net_risk,
            'risk_level': self.risk_level,
            'reason': self.reason
        }
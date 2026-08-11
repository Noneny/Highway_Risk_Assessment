"""
路段级风险评估系统数据模型
定义高速公路路段风险评估系统中的核心数据模型
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd


@dataclass
class RoadSection:
    """路段基础信息"""
    section_id: str  # 路段标识
    road_name: str  # 路段名称
    direction: str  # 运行方向
    company: str  # 所属公司
    level: str  # 等级
    length: float  # 里程(公里)
    lane_count: int  # 车道数
    design_capacity: float  # 设计通行能力
    route: str  # 路线
    area: str  # 途径区域

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'RoadSection':
        """从DataFrame行创建路段对象"""
        return cls(
            section_id=f"{row.get('路段', '')}_{row.get('运行方向', '')}",
            road_name=row.get('路段', ''),
            direction=row.get('运行方向', ''),
            company=row.get('公司', ''),
            level=row.get('等级', ''),
            length=float(row.get('里程', 0)),
            lane_count=int(row.get('车道数', 0)),
            design_capacity=float(row.get('单向设计通行能力', 2300)),
            route=row.get('路线', ''),
            area=row.get('途径区域', '')
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            '路段': self.road_name,
            '运行方向': self.direction,
            '公司': self.company,
            '等级': self.level,
            '里程': self.length,
            '车道数': self.lane_count,
            '单向设计通行能力': self.design_capacity,
            '路线': self.route,
            '途径区域': self.area
        }


@dataclass
class StructurePoint:
    """结构点风险信息（用于计算基础风险）"""
    point_id: str  # 点位标识
    road_name: str  # 所属路段
    direction: str  # 上下行
    total_risk_value: float  # 总风险值

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'StructurePoint':
        """从DataFrame行创建结构点对象"""
        return cls(
            point_id=f"{row.get('点位描述', '')}_{row.get('上下行', '')}",
            road_name=row.get('标准路段', ''),
            direction=row.get('标准方向', ''),
            total_risk_value=float(row.get('总风险值', 0))
        )


@dataclass
class TrafficFlowData:
    """交通流数据"""
    gantry_id: str  # 门架ID
    pass_id: str  # 通行ID
    vehicle_type: str  # 车型
    transaction_time: datetime  # 交易时间
    is_large: bool = False  # 是否是大车

    @classmethod
    def from_dataframe_row(cls, row: pd.Series, small_vehicle_types: List[str]) -> 'TrafficFlowData':
        """从DataFrame行创建流量数据对象"""
        # 解析时间字符串
        time_str = row.get('交易时间', '')
        try:
            transaction_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                transaction_time = datetime.strptime(time_str, '%Y/%m/%d %H:%M:%S')
            except ValueError:
                transaction_time = datetime.now()

        vehicle_type = str(row.get('车型', '')).strip()

        return cls(
            gantry_id=str(row.get('GANTRYID', '')).strip(),
            pass_id=str(row.get('PASSID', '')).strip(),
            vehicle_type=vehicle_type,
            transaction_time=transaction_time,
            is_large=vehicle_type not in small_vehicle_types
        )


@dataclass
class WeatherWarning:
    """气象预警数据"""
    warning_time: datetime  # 预警时间
    authority: str  # 发布单位
    warning_title: str  # 预警标题
    warning_type: str  # 预警类型
    area: str  # 影响区域

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'WeatherWarning':
        """从DataFrame行创建气象预警对象"""
        # 解析时间
        time_str = row.get('发布时间', '') or row.get('预警时间', '')
        try:
            warning_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                warning_time = datetime.strptime(time_str, '%Y-%m-%d')
            except ValueError:
                warning_time = datetime.now()

        return cls(
            warning_time=warning_time,
            authority=row.get('发布单位', ''),
            warning_title=row.get('预警标题', '') or row.get('标题', ''),
            warning_type='',  # 将在预处理中根据关键词识别
            area=row.get('影响区域', '') or row.get('区域', '')
        )


@dataclass
class AccidentRecord:
    """事故记录数据"""
    road_name: str  # 路段名称
    direction: str  # 方向
    accident_time: datetime  # 事故时间

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'AccidentRecord':
        """从DataFrame行创建事故记录对象"""
        # 解析时间
        time_str = row.get('事故时间', '') or row.get('发生时间', '')
        try:
            accident_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                accident_time = datetime.strptime(time_str, '%Y-%m-%d')
            except ValueError:
                accident_time = datetime.now()

        return cls(
            road_name=row.get('路段', '') or row.get('road_name', ''),
            direction=row.get('方向', '') or row.get('direction', ''),
            accident_time=accident_time
        )


@dataclass
class BaseRiskResult:
    """基础风险计算结果"""
    road_name: str  # 路段名称
    direction: str  # 运行方向
    base_risk_total: float  # 基础风险_F总值
    fi_components: List[float]  # Fi分量列表 [f1, f2, f3...]
    fi_detail: str  # Fi分量明细（字符串表示）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            '路段': self.road_name,
            '运行方向': self.direction,
            '基础风险_F总值': self.base_risk_total
        }

        # 添加分量列
        for i, fi in enumerate(self.fi_components, 1):
            result[f'Fi_分量_{i}'] = fi

        return result


@dataclass
class DynamicRiskResult:
    """动态风险计算结果"""
    road_name: str  # 路段名称
    direction: str  # 运行方向
    large_vehicle_ratio: float  # 大车比例
    large_vehicle_factor: float  # 大车系数
    congestion_level: float  # 拥挤度
    congestion_factor: float  # 拥挤度系数
    longitudinal_stability: float  # 纵向稳定性
    stability_factor: float  # 稳定性系数
    traffic_flow_factor: float  # 动态风险_交通流系数
    weather_warning_freq: int  # 气象预警频次
    weather_warning_factor: float  # 气象预警系数
    dynamic_total_factor: float  # 动态风险_总系数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            '路段': self.road_name,
            '运行方向': self.direction,
            '交通流_大车比': self.large_vehicle_ratio,
            '交通流_大车系数': self.large_vehicle_factor,
            '交通流_拥挤度': self.congestion_level,
            '交通流_拥挤度系数': self.congestion_factor,
            '交通流_纵向稳定': self.longitudinal_stability,
            '交通流_纵向系数': self.stability_factor,
            '动态风险_交通流系数': self.traffic_flow_factor,
            '气象预警_频次': self.weather_warning_freq,
            '气象预警_系数': self.weather_warning_factor,
            '动态风险_总系数': self.dynamic_total_factor
        }


@dataclass
class ExtraRiskResult:
    """附加风险计算结果"""
    road_name: str  # 路段名称
    direction: str  # 运行方向
    accident_freq: int  # 事故频数
    accident_per_km: float  # 每公里频数
    accident_score: int  # 事故分值
    accident_factor: float  # 事故系数
    road_attribute_factor: float  # 道路属性系数
    extra_total_factor: float  # 附加风险_总系数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            '路段': self.road_name,
            '运行方向': self.direction,
            '事故_频数': self.accident_freq,
            '事故_每公里频数': self.accident_per_km,
            '事故_赋分': self.accident_score,
            '附加风险_事故系数': self.accident_factor,
            '附加风险_道路属性系数': self.road_attribute_factor,
            '附加风险_总系数': self.extra_total_factor
        }


@dataclass
class LineRiskAssessment:
    """路段综合风险评估结果"""
    road_section: RoadSection  # 路段信息
    base_risk: BaseRiskResult  # 基础风险
    dynamic_risk: DynamicRiskResult  # 动态风险
    extra_risk: ExtraRiskResult  # 附加风险
    total_risk_score: float  # 路段风险总评
    risk_attribution: str  # 风险归因
    risk_level: str  # 风险等级
    calculation_date: datetime  # 计算日期

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于输出到Excel"""
        result = {}
        result.update(self.road_section.to_dict())
        result.update(self.base_risk.to_dict())
        result.update(self.dynamic_risk.to_dict())
        result.update(self.extra_risk.to_dict())
        result.update({
            '路段风险总评': self.total_risk_score,
            '风险归因': self.risk_attribution,
            '风险等级': self.risk_level,
            '计算日期': self.calculation_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        return result


@dataclass
class LineRiskEvaluationResult:
    """路段风险评价最终结果（数据库输出格式）"""
    id: str  # 唯一标识（UUID）
    belong_date: str  # 数据归属日期
    company: str  # 公司
    line: str  # 路段
    direction: str  # 运行方向
    level: str  # 等级
    length: float  # 里程
    lane_num: int  # 车道数
    F: float  # 基础风险_F
    large_rate: float  # 大车比例
    large_factor: float  # 大车系数
    crowdedness: float  # 拥挤度
    crowdedness_factor: float  # 拥挤度系数
    longi_stability: float  # 纵向稳定性
    stability_factor: float  # 稳定性系数
    weather_alert: int  # 气象预警频次
    alert_factor: float  # 气象预警系数
    accident: int  # 事故频数
    accident_per_km: float  # 每公里频数
    accident_score: int  # 事故分值
    accident_factor: float  # 事故系数
    road_attribute: float  # 道路属性系数
    line_risk: float  # 风险值
    risk_level: str  # 风险等级
    reason: str  # 风险归因

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库插入字典格式"""
        return {
            'id': self.id,
            'belong_date': self.belong_date,
            'company': self.company,
            'line': self.line,
            'direction': self.direction,
            'level': self.level,
            'length': self.length,
            'lane_num': self.lane_num,
            'F': self.F,
            'large_rate': self.large_rate,
            'large_factor': self.large_factor,
            'crowdedness': self.crowdedness,
            'crowdedness_factor': self.crowdedness_factor,
            'longi_stability': self.longi_stability,
            'stability_factor': self.stability_factor,
            'weather_alert': self.weather_alert,
            'alert_factor': self.alert_factor,
            'accident': self.accident,
            'accident_per_km': self.accident_per_km,
            'accident_score': self.accident_score,
            'accident_factor': self.accident_factor,
            'road_attribute': self.road_attribute,
            'line_risk': self.line_risk,
            'risk_level': self.risk_level,
            'reason': self.reason
        }
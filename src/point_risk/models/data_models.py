"""
数据模型定义
定义高速公路风险评价系统中的核心数据模型
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd


@dataclass
class StructurePoint:
    """结构点基础信息"""
    point_id: str  # 点位标识（可组合字段）
    point_type: str  # 点位类型
    point_description: str  # 点位描述
    company: str  # 所属公司
    county: str  # 所属区县
    comprehensive_level: str  # 综合等级
    road_section: str  # 所属路段
    road_number: str  # 路段编号
    longitude: float  # 经度
    latitude: float  # 纬度
    stake_number: str  # 点位桩号
    nearby_gantry_name: str  # 附近门架名称
    gantry_code: str  # 门架编码
    gantry_latitude: float  # 门架纬度
    gantry_longitude: float  # 门架经度
    direction: str  # 上下行
    technical_condition: str  # 技术状况
    point_level: str  # 点位等级
    base_risk_value: Optional[float] = None  # 基础风险值
    base_risk_attribution: Optional[str] = None  # 基础风险归因
    dynamic_risk_overlay: Optional[float] = None  # 动态风险叠加
    special_management_reduction: Optional[float] = None  # 专项管控折减
    total_risk_value: Optional[float] = None  # 总风险值

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'StructurePoint':
        """从DataFrame行创建结构点对象"""
        return cls(
            point_id=f"{row.get('点位类型', '')}_{row.get('点位描述', '')}_{row.get('所属路段', '')}",
            point_type=row.get('点位类型', ''),
            point_description=row.get('点位描述', ''),
            company=row.get('所属公司', ''),
            county=row.get('所属区县', ''),
            comprehensive_level=row.get('综合等级', ''),
            road_section=row.get('所属路段', ''),
            road_number=row.get('路段编号', ''),
            longitude=float(row.get('经度', 0)),
            latitude=float(row.get('纬度', 0)),
            stake_number=row.get('点位桩号', ''),
            nearby_gantry_name=row.get('附近门架名称', ''),
            gantry_code=row.get('门架编码', ''),
            gantry_latitude=float(row.get('附近门架信息纬度', 0)),
            gantry_longitude=float(row.get('附近门架信息经度', 0)),
            direction=row.get('上下行', ''),
            technical_condition=row.get('技术状况', ''),
            point_level=row.get('点位等级', '')
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            '点位类型': self.point_type,
            '点位描述': self.point_description,
            '所属公司': self.company,
            '所属区县': self.county,
            '综合等级': self.comprehensive_level,
            '所属路段': self.road_section,
            '路段编号': self.road_number,
            '经度': self.longitude,
            '纬度': self.latitude,
            '点位桩号': self.stake_number,
            '附近门架名称': self.nearby_gantry_name,
            '门架编码': self.gantry_code,
            '附近门架信息纬度': self.gantry_latitude,
            '附近门架信息经度': self.gantry_longitude,
            '上下行': self.direction,
            '技术状况': self.technical_condition,
            '点位等级': self.point_level,
            '基础风险值': self.base_risk_value,
            '基础风险归因': self.base_risk_attribution,
            '动态风险叠加': self.dynamic_risk_overlay,
            '专项管控折减': self.special_management_reduction,
            '总风险值': self.total_risk_value
        }


@dataclass
class WeatherWarning:
    """气象预警数据"""
    datetime: datetime  # 预警时间
    update_time: datetime  # 更新时间
    station_id: str  # 站点ID
    longitude: float  # 经度
    latitude: float  # 纬度
    warning_type: str  # 预警类型
    warning_level: str  # 预警级别
    effective_start: datetime  # 有效开始时间
    effective_end: datetime  # 有效结束时间
    valid_period: str  # 有效时段
    issuing_time: datetime  # 发布时间
    release_unit: str  # 发布单位
    route_name: str  # 路线名称
    start_stake_number: str  # 起始桩号
    end_stake_number: str  # 结束桩号
    bridge_tunnel_name: str  # 桥隧名称
    risk_level: str  # 风险等级
    hazard_description: str  # 灾害描述
    district: str  # 区县
    town: str  # 乡镇
    point_longitude: float  # 点位经度
    point_latitude: float  # 点位纬度

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> 'WeatherWarning':
        """从JSON字典创建气象预警对象"""
        def parse_datetime(dt_str: str) -> datetime:
            """解析日期时间字符串"""
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # 尝试其他格式
                try:
                    return datetime.strptime(dt_str, '%Y-%m-%d')
                except ValueError:
                    return datetime.now()

        return cls(
            datetime=parse_datetime(data.get('datetime', '')),
            update_time=parse_datetime(data.get('update_time', '')),
            station_id=data.get('sta_id', ''),
            longitude=float(data.get('lon', 0)),
            latitude=float(data.get('lat', 0)),
            warning_type=data.get('warning_type', ''),
            warning_level=data.get('warning_level', ''),
            effective_start=parse_datetime(data.get('effective_start', '')),
            effective_end=parse_datetime(data.get('effective_end', '')),
            valid_period=data.get('valid_period', ''),
            issuing_time=parse_datetime(data.get('issuing_time', '')),
            release_unit=data.get('release_unit', ''),
            route_name=data.get('route_name', ''),
            start_stake_number=data.get('start_stake_number', ''),
            end_stake_number=data.get('end_stake_number', ''),
            bridge_tunnel_name=data.get('bridge_tunnel_name', ''),
            risk_level=data.get('risk_level', ''),
            hazard_description=data.get('hazard_description', ''),
            district=data.get('district', ''),
            town=data.get('p_town', ''),
            point_longitude=float(data.get('p_lon', 0)),
            point_latitude=float(data.get('p_lat', 0))
        )


@dataclass
class TrafficFlow:
    """门架交易数据"""
    transaction_id: str  # 交易ID
    gantry_id: str  # 门架ID
    vehicle_id: str  # 车辆ID
    vehicle_type: str  # 车型
    transaction_time: datetime  # 交易时间
    speed: Optional[float] = None  # 速度
    direction: Optional[str] = None  # 方向

    @classmethod
    def from_csv_row(cls, row: pd.Series) -> 'TrafficFlow':
        """从CSV行创建流量数据对象"""
        # 解析时间字符串
        time_str = row.get('交易时间', '')
        try:
            transaction_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                transaction_time = datetime.strptime(time_str, '%Y/%m/%d %H:%M:%S')
            except ValueError:
                transaction_time = datetime.now()

        # 生成唯一交易ID
        transaction_id = f"{row.get('门架ID', '')}_{row.get('车辆ID', '')}_{time_str}"

        return cls(
            transaction_id=transaction_id,
            gantry_id=row.get('门架ID', ''),
            vehicle_id=row.get('车辆ID', ''),
            vehicle_type=row.get('车型', ''),
            transaction_time=transaction_time,
            speed=float(row.get('速度', 0)) if pd.notna(row.get('速度')) else None,
            direction=row.get('方向', '') if '方向' in row else None
        )


@dataclass
class GantryRiskAssessment:
    """门架风险评估结果"""
    gantry_code: str  # 门架编码
    gantry_name: str  # 门架名称
    company_name: str  # 公司名称
    road_section: str  # 路段名称
    date: str  # 日期（YYYY-MM格式）
    total_vehicles: int  # 总车辆数
    peak_hour_congestion: float  # 高峰小时拥挤度
    large_vehicle_ratio: float  # 大型车比例
    speed_discrete_coefficient: float  # 速度离散系数
    congestion_risk_value: float  # 拥挤度风险值
    composition_risk_value: float  # 交通组成风险值
    discrete_risk_value: float  # 离散差风险值
    risk_level: str  # 风险等级
    belong_date: str  # 数据归属日期

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> 'GantryRiskAssessment':
        """从DataFrame行创建门架风险评估对象"""
        return cls(
            gantry_code=row.get('门架编码', ''),
            gantry_name=row.get('门架名称', ''),
            company_name=row.get('公司名称', ''),
            road_section=row.get('路段名称', ''),
            date=row.get('日期', ''),
            total_vehicles=int(row.get('总车辆数', 0)),
            peak_hour_congestion=float(row.get('高峰小时拥挤度', 0)),
            large_vehicle_ratio=float(row.get('大型车比例', 0)),
            speed_discrete_coefficient=float(row.get('速度离散系数', 0)),
            congestion_risk_value=float(row.get('拥挤度风险值', 1.0)),
            composition_risk_value=float(row.get('交通组成风险值', 1.0)),
            discrete_risk_value=float(row.get('离散差风险值', 1.0)),
            risk_level=row.get('风险等级', ''),
            belong_date=row.get('belong_date', '')
        )


@dataclass
class ComprehensiveRiskAssessment:
    """综合风险评估结果"""
    structure_point: StructurePoint  # 结构点信息
    gantry_risk_assessments: List[GantryRiskAssessment]  # 关联的门架风险评估
    weather_warning_days: int  # 预警天数
    dynamic_risk_overlay: float  # 动态风险叠加
    special_management_reduction: float  # 专项管控折减
    total_risk_value: float  # 总风险值
    final_risk_level: str  # 最终风险等级
    risk_attribution: Dict[str, Any]  # 风险归因分析
    calculation_date: datetime  # 计算日期

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于输出到Excel"""
        base_dict = self.structure_point.to_dict()
        base_dict.update({
            '预警天数': self.weather_warning_days,
            '动态风险叠加': self.dynamic_risk_overlay,
            '专项管控折减': self.special_management_reduction,
            '总风险值': self.total_risk_value,
            '风险等级': self.final_risk_level,
            '计算日期': self.calculation_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        # 添加风险归因字段
        for key, value in self.risk_attribution.items():
            base_dict[f'风险归因_{key}'] = value

        return base_dict


@dataclass
class RiskEvaluationResult:
    """风险评价最终结果（数据库输出格式）"""
    id: str  # 唯一标识（UUID）
    point_type: str  # 点位类型
    point_name: str  # 点位描述
    asso_company: str  # 所属公司
    district: str  # 所属区县
    level: str  # 综合等级
    associated_line: str  # 所属路段
    line_num: str  # 路段编号
    longitude: float  # 经度
    latitude: float  # 纬度
    stake_num: str  # 点位桩号
    nearby_etc: str  # 附近门架名称
    etc_id: str  # 门架编码
    etc_lati: float  # 附近门架信息纬度
    etc_longi: float  # 附近门架信息经度
    direction: str  # 上下行
    F: float  # 基础风险值
    y: float  # 动态风险叠加
    z: float  # 专项管控折减
    point_risk: float  # 总风险值
    F_reason: str  # 基础风险归因
    y_reason: str  # 动态风险归因
    risk_level: str  # 风险等级
    belong_date: str  # 数据归属日期

    def to_db_dict(self) -> Dict[str, Any]:
        """转换为数据库插入字典格式"""
        return {
            'id': self.id,
            'point_type': self.point_type,
            'point_name': self.point_name,
            'asso_company': self.asso_company,
            'district': self.district,
            'level': self.level,
            'associated_line': self.associated_line,
            'line_num': self.line_num,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'stake_num': self.stake_num,
            'nearby_etc': self.nearby_etc,
            'etc_id': self.etc_id,
            'etc_lati': self.etc_lati,
            'etc_longi': self.etc_longi,
            'direction': self.direction,
            'F': self.F,
            'y': self.y,
            'z': self.z,
            'point_risk': self.point_risk,
            'F_reason': self.F_reason,
            'y_reason': self.y_reason,
            'risk_level': self.risk_level,
            'belong_date': self.belong_date
        }

# read_company.py
import pandas as pd
import os
import warnings

warnings.filterwarnings('ignore')


class CompanyReader:
    """公司信息读取器"""

    def __init__(self):
        # 定义文件路径 (相对于项目根目录)
        self.structure_file = "data/input/结构物监测基础信息表(1019)带门架方向.xlsx"
        self.road_file = "data/input/路段评价模板.xlsx"
        self.network_file = "data/input/路网及其对应公司.xlsx"

        # 缓存数据
        self.structure_data = None
        self.road_data = None
        self.network_data = None

        # 列名映射
        self.column_mapping = {
            '结构点': {
                'name_col': '点位描述',
                'company_col': '所属公司'
            },
            '路段': {
                'name_col': '路段',
                'company_col': '运营公司'
            },
            '路网': {
                'name_col': '路网划分',
                'company_col': '运营公司'
            }
        }

        # 尝试加载数据
        self._load_data()

    def _load_data(self):
        """加载数据到内存"""
        try:
            # 加载结构点数据
            if os.path.exists(self.structure_file):
                self.structure_data = pd.read_excel(self.structure_file)
                print(f"✅ 已加载结构点数据: {self.structure_file}")
            else:
                print(f"⚠️ 结构点文件不存在: {self.structure_file}")

            # 加载路段数据
            if os.path.exists(self.road_file):
                self.road_data = pd.read_excel(self.road_file)
                print(f"✅ 已加载路段数据: {self.road_file}")
            else:
                print(f"⚠️ 路段文件不存在: {self.road_file}")

            # 加载路网数据
            if os.path.exists(self.network_file):
                self.network_data = pd.read_excel(self.network_file)
                print(f"✅ 已加载路网数据: {self.network_file}")
            else:
                print(f"⚠️ 路网文件不存在: {self.network_file}")

        except Exception as e:
            print(f"❌ 加载数据失败: {e}")

    def _get_company_mapping(self, structure_type):
        """获取公司名称映射函数"""
        if not structure_type or structure_type not in self.column_mapping:
            return None

        mapping = {}

        if structure_type == '结构点':
            data = self.structure_data
        elif structure_type == '路段':
            data = self.road_data
        elif structure_type == '路网':
            data = self.network_data
        else:
            return None

        if data is None:
            return None

        name_col = self.column_mapping[structure_type]['name_col']
        company_col = self.column_mapping[structure_type]['company_col']

        # 检查列是否存在
        if name_col not in data.columns or company_col not in data.columns:
            print(f"⚠️  {structure_type}文件中缺少必要列: 名称列 '{name_col}' 或 公司列 '{company_col}'")
            return None

        # 构建映射字典
        for _, row in data.iterrows():
            name = row[name_col]
            company = row[company_col]

            if pd.isna(name) or pd.isna(company):
                continue

            # 转换为字符串并去除首尾空格
            name_str = str(name).strip()
            company_str = str(company).strip()

            if name_str and company_str:
                mapping[name_str] = company_str

        return mapping

    def _get_company_for_structure_point(self, structure_name):
        """获取结构点所属公司"""
        if self.structure_data is None:
            return None

        mapping = self._get_company_mapping('结构点')
        if not mapping:
            return None

        structure_name_str = str(structure_name).strip()

        # 精确匹配
        if structure_name_str in mapping:
            return mapping[structure_name_str]

        # 模糊匹配（如果精确匹配失败）
        for name, company in mapping.items():
            if structure_name_str in name or name in structure_name_str:
                return company

        return None

    def _get_company_for_road(self, road_name):
        """获取路段所属公司"""
        if self.road_data is None:
            return None

        mapping = self._get_company_mapping('路段')
        if not mapping:
            return None

        road_name_str = str(road_name).strip()

        # 精确匹配
        if road_name_str in mapping:
            return mapping[road_name_str]

        # 模糊匹配（如果精确匹配失败）
        for name, company in mapping.items():
            if road_name_str in name or name in road_name_str:
                return company

        return None

    def _get_company_for_network(self, network_name):
        """获取路网所属公司"""
        if self.network_data is None:
            return None

        mapping = self._get_company_mapping('路网')
        if not mapping:
            return None

        network_name_str = str(network_name).strip()

        # 精确匹配
        if network_name_str in mapping:
            return mapping[network_name_str]

        # 模糊匹配（如果精确匹配失败）
        for name, company in mapping.items():
            if network_name_str in name or name in network_name_str:
                return company

        return None

    def _map_company_name(self, company_name):
        """映射公司名称（如果需要简化）"""
        if not company_name or pd.isna(company_name):
            return None

        company_name = str(company_name).strip()

        # 公司名称映射规则（如果需要简化）
        company_mapping = {
            '重庆高速公路集团有限公司东北营运分公司': '东北公司',
            '重庆高速公路集团有限公司东南营运分公司': '东南公司',
            '重庆渝东高速公路有限公司': '渝东公司',
            '重庆万利万达高速公路有限公司': '万利万达公司',
            '东北营运分公司': '东北公司',
            '东南营运分公司': '东南公司',
            '渝东公司': '渝东公司',
            '万利万达公司': '万利万达公司',
            '东北公司': '东北公司',
            '东南公司': '东南公司',
        }

        # 精确匹配
        if company_name in company_mapping:
            return company_mapping[company_name]

        # 模糊匹配
        for original_name, mapped_name in company_mapping.items():
            if original_name in company_name:
                return mapped_name

        # 如果未匹配到，返回原值
        return company_name

    def read_company_with_name(self, structure_type, structure_name, simplify=True):
        """
        读取所属公司信息

        参数:
        - structure_type: 结构类型 ('结构点', '路段', '路网')
        - structure_name: 结构名称
        - simplify: 是否简化公司名称（默认True）

        返回:
        - 所属公司名称，如果未找到则返回None
        """
        if not structure_type or not structure_name:
            return None

        company = None

        if structure_type == '结构点':
            company = self._get_company_for_structure_point(structure_name)
        elif structure_type == '路段':
            company = self._get_company_for_road(structure_name)
        elif structure_type == '路网':
            company = self._get_company_for_network(structure_name)
        else:
            print(f"⚠️ 未知的结构类型: {structure_type}")
            return None

        if company and simplify:
            company = self._map_company_name(company)

        return company


# 创建全局实例
_company_reader = None


def get_company_reader():
    """获取公司读取器实例（单例模式）"""
    global _company_reader
    if _company_reader is None:
        _company_reader = CompanyReader()
    return _company_reader


def read_company_with_name(structure_type, structure_name, simplify=True):
    """
    读取所属公司信息（主函数）

    参数:
    - structure_type: 结构类型 ('结构点', '路段', '路网')
    - structure_name: 结构名称
    - simplify: 是否简化公司名称（默认True）

    返回:
    - 所属公司名称，如果未找到则返回None
    """
    reader = get_company_reader()
    return reader.read_company_with_name(structure_type, structure_name, simplify)


# 测试函数
def test_read_company():
    """测试函数"""
    print("=== 测试公司信息读取 ===")

    # 测试结构点
    test_cases = [
        ('结构点', '示例结构点1'),
        ('路段', '示例路段1'),
        ('路网', '示例路网1'),
    ]

    for structure_type, structure_name in test_cases:
        company = read_company_with_name(structure_type, structure_name)
        print(f"{structure_type} - {structure_name}: {company}")

    print("=== 测试完成 ===")


if __name__ == "__main__":
    test_read_company()
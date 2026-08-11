import unittest
from dataclasses import fields

import pandas as pd

from src.point_risk.database.database_connector import DatabaseConnector
from src.point_risk.models.data_models import RiskEvaluationResult


class PointRiskDatabaseContractTest(unittest.TestCase):

    def setUp(self):
        # 绕过构造函数，避免单元测试建立真实数据库连接。
        self.connector = object.__new__(DatabaseConnector)
        self.connector.connection = None

    def test_risk_table_schema_excludes_calculation_time(self):
        create_sql = self.connector._get_risk_evaluation_table_sql(
            "point_risk_evaluation"
        )

        self.assertNotIn("calculation_time", create_sql)

    def test_risk_insert_payload_excludes_calculation_time(self):
        frame = pd.DataFrame(
            [
                {
                    "点位描述": "测试结构点",
                    "风险等级": "低风险",
                    # 即使上游意外携带同名列，也不能写入数据库。
                    "calculation_time": "2026-08-11 12:00:00",
                }
            ]
        )

        records = self.connector._prepare_risk_evaluation_data(
            frame, "2026-08-01"
        )

        self.assertEqual(1, len(records))
        self.assertNotIn("calculation_time", records[0])

    def test_database_result_model_excludes_calculation_time(self):
        field_names = {field.name for field in fields(RiskEvaluationResult)}

        self.assertNotIn("calculation_time", field_names)


if __name__ == "__main__":
    unittest.main()

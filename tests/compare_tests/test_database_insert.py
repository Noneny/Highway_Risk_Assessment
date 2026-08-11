import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import pandas as pd
import pymysql

from src.compare.compare import insert_data_to_db


class FakeCursor:
    def __init__(self):
        self.rowcount = 0
        self.inserted = []
        self.unique_keys = set()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, sql, params=None):
        if sql.lstrip().upper().startswith("DELETE"):
            self.rowcount = 0
            return 0

        record = params
        unique_key = (record[3], record[4], record[1])
        if unique_key in self.unique_keys:
            raise pymysql.err.IntegrityError(
                1062,
                "Duplicate entry for key 'unique_structure'",
            )

        self.unique_keys.add(unique_key)
        self.inserted.append(record)
        self.rowcount = 1
        return 1

    def executemany(self, sql, records):
        for record in records:
            self.execute(sql, record)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class RiskContrastInsertTest(unittest.TestCase):

    @patch("src.compare.compare.read_company_with_name", return_value="测试公司")
    @patch("src.compare.compare.pymysql.connect")
    def test_duplicate_unique_structure_is_skipped_and_other_rows_are_committed(
        self, connect_mock, _company_mock
    ):
        connection = FakeConnection()
        connect_mock.return_value = connection
        frame = pd.DataFrame(
            [
                {
                    "评估单元类型": "结构点",
                    "结构名称": "郁江二号大桥",
                    "方向": "右线",
                    "当期风险值": 72,
                    "风险等级": "一般风险",
                    "往期风险值": 70,
                    "风险变化类型": "风险上行",
                },
                {
                    "评估单元类型": "结构点",
                    "结构名称": "郁江二号大桥",
                    "方向": "右线",
                    "当期风险值": 73,
                    "风险等级": "一般风险",
                    "往期风险值": 72,
                    "风险变化类型": "风险上行",
                },
                {
                    "评估单元类型": "结构点",
                    "结构名称": "测试隧道",
                    "方向": "左线",
                    "当期风险值": 65,
                    "风险等级": "一般风险",
                    "往期风险值": 64,
                    "风险变化类型": "风险上行",
                },
            ]
        )
        db_config = {
            "host": "localhost",
            "port": 3306,
            "user": "test",
            "password": "test",
            "database": "test",
            "table_name": "risk_contrast",
        }

        output = io.StringIO()
        with redirect_stdout(output):
            success = insert_data_to_db(frame, "26_4_26_5", db_config)

        self.assertTrue(success)
        self.assertEqual(2, len(connection.cursor_instance.inserted))
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertIn("跳过重复记录: 1 条", output.getvalue())


if __name__ == "__main__":
    unittest.main()

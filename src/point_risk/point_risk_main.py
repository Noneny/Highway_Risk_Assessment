#!/usr/bin/env python3
"""
高速公路风险结构点风险等级评价系统 - 主程序入口

基于面向对象编程重构，统一配置文件管理，标准项目结构
"""

import sys
import os

from src.point_risk.workflow.risk_assessment_workflow import main as workflow_main


if __name__ == "__main__":
    # 显示项目信息
    print("\n" + "="*80)
    print("高速公路风险结构点风险等级评价系统")
    print("版本: 1.0.0 (重构版)")
    print("="*80)
    print("")

    # 执行工作流
    workflow_main()
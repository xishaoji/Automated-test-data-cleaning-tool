# utils/data_profiler.py
import pandas as pd

def generate_profiling_report(df: pd.DataFrame) -> str:
    """生成测试日志的结构化体检报告"""
    total_rows = len(df)
    missing_stats = df.isnull().sum()
    missing_cols = missing_stats[missing_stats > 0].to_dict()
    
    report = f"### 📊 测试日志数据体检\n"
    report += f"- **总抓包记录**: {total_rows} 行\n"
    report += f"- **有效字段数**: {len(df.columns)} 列\n"
    
    if missing_cols:
        report += "- **⚠️ 数据空缺/掉线情况**:\n"
        for col, count in missing_cols.items():
            report += f"  - `{col}`: 缺失 {count} 条 ({count/total_rows:.1%})\n"
    else:
        report += "- **✅ 通信完整度**: 极佳，未发现字段缺失。\n"
        
    return report
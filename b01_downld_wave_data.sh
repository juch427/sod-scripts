#!/bin/bash
# nohup ./b02.sh &
set -e  # 遇到错误立即退出

# 清理旧文件（静默模式）
rm -rf "6c_day_sac" "SodDb" 2>/dev/null || true
rm -f "sod_hibernate.out" *.log 2>/dev/null || true

# 执行主命令
sod -f a01_6C_continuous_data.xml

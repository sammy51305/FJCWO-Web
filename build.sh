#!/usr/bin/env bash
# Render 的 Build Command。每次部署會跑一次。
# set -o errexit：任何一步失敗就中止部署，不要帶著半殘的狀態上線。
set -o errexit

pip install -r requirements.txt

# 收集 static 到 STATIC_ROOT，交給 WhiteNoise 供應
python manage.py collectstatic --no-input

# 套用遷移。migrate 本身是冪等的，重複部署不會重複執行同一個遷移。
python manage.py migrate

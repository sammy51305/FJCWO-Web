#!/usr/bin/env bash
# Render 的 Build Command。每次部署會跑一次。
# set -o errexit：任何一步失敗就中止部署，不要帶著半殘的狀態上線。
set -o errexit

# 敏感個資是加密存的（#13-1 決定二）。沒設金鑰時 settings 會退回 repo 裡那把開發用預設值，
# 等於沒加密——所以部署一律擋下，讓它在建置階段就失敗，而不是安靜地把真實個資明文存進去。
if [ -z "$DJANGO_FIELD_ENCRYPTION_KEY" ]; then
  echo "ERROR: DJANGO_FIELD_ENCRYPTION_KEY 未設定。"
  echo "       敏感個資（身分證字號／住址／生日）會退回使用 repo 內的開發預設金鑰，等於沒加密。"
  echo "       請在平台的環境變數設一組隨機字串後再部署（見 _notes/SETUP.md 情境 E）。"
  exit 1
fi

pip install -r requirements.txt

# 收集 static 到 STATIC_ROOT，交給 WhiteNoise 供應
python manage.py collectstatic --no-input

# 套用遷移。migrate 本身是冪等的，重複部署不會重複執行同一個遷移。
python manage.py migrate

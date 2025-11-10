
Tele Shop Bot (Railway Ready)
=============================

1) Tạo bot tại @BotFather -> lấy BOT_TOKEN
2) Upload thư mục này lên GitHub (repo mới)
3) Railway -> New Project -> Deploy from GitHub
4) Vào Variables, thêm:
   - BOT_TOKEN = <token của bạn>
   - ADMIN_IDS = 7241782528
   - DB_PATH   = /data/shop.db
5) Add-ons -> Storage (Volume) -> mount /data
6) Xem Logs: thấy "Bot polling started" là xong.

Lệnh admin để duyệt nạp (trong Telegram):
/approve <deposit_id> <amount>
/reject <deposit_id>

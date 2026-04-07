# 📚 Fast Education — Telegram Baho Bildirishnoma Bot

O'qituvchi Google Sheets ga baho qo'yadi → Ota-ona Telegram da xabar oladi.

```
O'qituvchi baho yozadi (Google Sheets)
        ↓
Apps Script avtomatik aniqlab, serverga yuboradi
        ↓
Bot telefon raqam bo'yicha ota-onani topadi
        ↓
Ota-ona Telegram da xabar oladi:
  📝 Yangi baho!
  🧑‍🎓 Quvonchbek Quvondiqov
  📊 Baho: 5
  📅 Sana: 04.03.2026
```

---

## 📦 Fayllar

| Fayl | Vazifasi |
|------|----------|
| `bot.py` | Telegram bot + webhook server |
| `google_apps_script.js` | Google Sheets trigger |
| `.env` | Sozlamalar |
| `requirements.txt` | Python kutubxonalari |
| `grade-bot.service` | Systemd (avtomatik ishga tushirish) |

---

## 🚀 TO'LIQ O'RNATISH (Qadam-baqadam)

### 1-QADAM: Telegram Bot yaratish

```
1. Telegram da @BotFather ni oching
2. /newbot yozing
3. Nom bering: Fast Education Grades
4. Username bering: fast_edu_grades_bot (yoki boshqa)
5. Token ni nusxalang (7123456789:AAH-xxxxx)
```

### 2-QADAM: VPS ga o'rnatish

```bash
# VPS ga ulaning
ssh root@YOUR_SERVER_IP

# Python o'rnating (agar yo'q bo'lsa)
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# Papka yarating
mkdir fast_edu_bot
cd fast_edu_bot

# Fayllarni VPS ga ko'chiring (kompyuterdan):
# scp bot.py google_apps_script.js .env requirements.txt grade-bot.service root@YOUR_IP:/root/fast_edu_bot/

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Kutubxonalarni o'rnating
pip install -r requirements.txt
```

### 3-QADAM: .env sozlash

```bash
nano .env
```

O'zgartiring:
```
BOT_TOKEN=7123456789:AAH-sizning-tokeningiz
WEBHOOK_SECRET=MySecretKey2024
FLASK_PORT=5000
ADMIN_IDS=sizning_telegram_id
```

> 💡 Telegram ID ni bilish uchun @userinfobot ga yozing

### 4-QADAM: Test qilish

```bash
source venv/bin/activate
export $(cat .env | xargs)
python bot.py
```

Bot ishlayotganini tekshiring — Telegram da `/start` yozing.
`Ctrl+C` bilan to'xtating.

### 5-QADAM: Avtomatik ishga tushirish (systemd)

```bash
# Service faylni ko'chiring
sudo cp grade-bot.service /etc/systemd/system/

# Agar user ubuntu bo'lmasa, faylni tahrirlang:
sudo nano /etc/systemd/system/grade-bot.service
# User= va WorkingDirectory= ni o'zgartiring

# Ishga tushiring
sudo systemctl daemon-reload
sudo systemctl enable grade-bot
sudo systemctl start grade-bot

# Holatni tekshiring
sudo systemctl status grade-bot

# Loglarni ko'ring
sudo journalctl -u grade-bot -f
```

### 6-QADAM: Firewall

```bash
# Port 5000 ni oching
sudo ufw allow 5000
```

### 7-QADAM: Google Apps Script o'rnatish

```
1. Google Sheets jurnalni oching
2. Extensions → Apps Script
3. Barcha eski kodni o'chiring
4. google_apps_script.js dagi kodni paste qiling
5. Yuqoridagi 2 qatorni o'zgartiring:
   
   var WEBHOOK_URL    = "http://SIZNING_VPS_IP:5000/webhook/grade";
   var WEBHOOK_SECRET = "MySecretKey2024";  // .env dagi bilan BIR XIL!

6. Saqlang (Ctrl+S)
```

### 8-QADAM: Trigger o'rnatish

```
1. Apps Script da chapda ⏰ (Triggers) bosing
2. "+ Add Trigger" bosing
3. Sozlamalar:
   - Function: onEditGrade
   - Event source: From spreadsheet
   - Event type: On edit
4. Save bosing
5. Google ruxsat so'raydi — "Allow" bosing

6. YANA BIR trigger qo'shing:
   - Function: retryFailed
   - Event source: Time-driven
   - Event type: Every 5 minutes
7. Save
```

### 9-QADAM: Test

```
1. Apps Script da: Run → testWebhook
2. VPS da logni tekshiring: sudo journalctl -u grade-bot -f
3. Telegram bot da /register qiling, jurnaldagi raqamni kiriting
4. Google Sheets da biror o'quvchiga baho yozing
5. Telegram da xabar kelishi kerak! ✅
```

---

## ⚠️ MUHIM ESLATMALAR

### Telefon raqam moslanishi
Ota-ona kiritan raqam = Google Sheets Column E dagi raqam bo'lishi **SHART**.

```
Sheets da: 974555503    → Bot avtomatik: 998974555503
Ota-ona:   +998974555503 → Bot avtomatik: 998974555503
                                          ✅ MOS KELADI
```

Bot barcha formatlarni avtomatik moslashtiradi:
- `+998901234567` → `998901234567`
- `998901234567`  → `998901234567`
- `901234567`     → `998901234567`
- `8901234567`    → `998901234567`

### Bir raqam — bir nechta farzand
Agar bitta telefon raqam Google Sheets da bir nechta o'quvchi uchun
yozilgan bo'lsa (masalan, aka-uka), har biriga baho qo'yilganda
xabar keladi. Hech narsa qo'shimcha qilish kerak emas.

### Bir nechta fan
O'quvchi bir nechta fanda o'qisa (ATTENDANCE, Progress, BR10...),
HAR BIR tab dagi baho uchun xabar keladi. Tab nomi farq qilmaydi —
telefon raqam orqali topiladi.

### Bir nechta Google Sheets fayl
Agar sizda bir nechta Google Sheets fayl bo'lsa:
- Har bir faylga Apps Script ni alohida o'rnating
- WEBHOOK_URL va SECRET bir xil bo'lishi kerak
- Bot hammasi uchun ishlaydi

---

## 📱 Bot Buyruqlari

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Salomlashish |
| `/register` | Ro'yxatdan o'tish (telefon raqam) |
| `/status` | Holat tekshirish |
| `/unregister` | Bildirishnomalarni to'xtatish |
| `/help` | Yordam |
| `/admin_list` | Barcha ro'yxat (faqat admin) |
| `/admin_stats` | Statistika (faqat admin) |

---

## 🐛 Xatoliklar

| Muammo | Yechim |
|--------|--------|
| Xabar kelmayapti | Raqam bir xilmi tekshiring |
| 429 quota error | Eski polling skriptni o'chiring! |
| Webhook fail | VPS firewall, port 5000 ochiqmi? |
| Bot javob bermayapti | `systemctl status grade-bot` |
| Apps Script xato | Execution log ni tekshiring |

---

## 🔐 SSL (Production uchun tavsiya)

```bash
# Nginx o'rnating
sudo apt install nginx certbot python3-certbot-nginx -y

# SSL sertifikat (domen kerak)
sudo certbot --nginx -d bot.yourdomain.com

# Nginx config
sudo nano /etc/nginx/sites-available/grade-bot

# Ichiga:
server {
    listen 443 ssl;
    server_name bot.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.yourdomain.com/privkey.pem;
    
    location /webhook/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable
sudo ln -s /etc/nginx/sites-available/grade-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Google Apps Script da URL ni o'zgartiring:
```
var WEBHOOK_URL = "https://bot.yourdomain.com/webhook/grade";
```

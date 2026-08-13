# ⏱️ ZKTeco ADMS Attendance Receiver & Dashboard

A lightweight Python (Flask) ADMS push receiver and web dashboard for **ZKTeco Face ID terminals** (e.g., EFace10, SpeedFace, uFace, SilkBio). 

It automatically captures real-time biometric attendance logs pushed by ZKTeco hardware via the ADMS HTTP protocol, records them into an SQLite database, calculates daily presence/absence statistics, and provides 1-click Excel (CSV) exports for daily and full-month reports.

---

## ✨ Key Features

- **📡 Native ZKTeco ADMS Receiver**: Listens for device push logs at `/iclock/cdata` (Push Communication Protocol).
- **📊 Real-Time Web Dashboard**: Clean Tailwind CSS interface displaying total staff, present count, absent count, and clock-in/out timestamps with 10-second auto-refresh.
- **📥 1-Click Excel / CSV Exports**: Export daily attendance sheets or full-month matrix reports formatted for Microsoft Excel (`delimiter=';'`, UTF-8 BOM).
- **💾 Embedded SQLite Persistence**: Automated table creation and attendance timestamp tracking.
- **🐧 24/7 Production Deployment Ready**: Complete Systemd service configuration for Debian/Ubuntu headless Linux servers.

---

## 🛠️ System Requirements

- Python 3.10+
- Flask 3.0+
- SQLite3
- ZKTeco ADMS-enabled biometric terminal (connected over LAN/WAN)

---

## 🚀 Quick Start Guide

### 1. Installation & Local Setup

```bash
# Clone the repository
git clone https://github.com/Seterneus/zkteco-adms-attendance-dashboard.git
cd zkteco-adms-attendance-dashboard

# Create virtual environment
python -m venv venv
# Activate virtual environment:
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the sample configuration file:

```bash
cp .env.example .env
```

Edit `.env` as needed:
```env
HOST=0.0.0.0
PORT=8000
DATABASE_PATH=attendance.db
```

### 3. Run the Receiver & Dashboard

```bash
python app.py
```

Access the dashboard at `http://localhost:8000` (or `http://YOUR_SERVER_IP:8000`).

---

## ⚙️ Configuring Your ZKTeco Terminal (ADMS Setup)

On your ZKTeco Terminal (e.g. EFace10):
1. Navigate to **Menu** $\rightarrow$ **Comm. Settings** $\rightarrow$ **Cloud Server Settings** (or **ADMS** / **Server Settings**).
2. Enable **Enable Domain Name** (or select **IP Address**).
3. Set **Server Address**: `http://YOUR_SERVER_IP` (e.g. `192.168.1.100` or public domain).
4. Set **Server Port**: `8000` (or your configured port).
5. Save settings. The terminal will establish a heartbeat and begin pushing attendance logs automatically upon face scan.

---

## 🐧 24/7 Production Deployment (Linux Systemd)

To run the ADMS receiver continuously on a Debian/Ubuntu Linux server:

1. Create a systemd service unit file:
```bash
sudo nano /etc/systemd/system/adms-attendance.service
```

2. Add the following configuration (adjust paths and user):
```ini
[Unit]
Description=ZKTeco ADMS Attendance Receiver & Flask Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/opt/zkteco-adms-attendance-dashboard
ExecStart=/opt/zkteco-adms-attendance-dashboard/venv/bin/gunicorn --bind 0.0.0.0:8000 --workers 2 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable adms-attendance
sudo systemctl start adms-attendance
sudo systemctl status adms-attendance
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.

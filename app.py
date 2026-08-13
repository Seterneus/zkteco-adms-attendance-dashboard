import sqlite3
import csv
import calendar
import os
from io import StringIO
from flask import Flask, request, jsonify, render_template_string, Response
from datetime import datetime, date

app = Flask(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "attendance.db")

# --- DATABASE SETUP & INITIALIZATION ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_pin TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            verify_type INTEGER,
            device_sn TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            pin TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT DEFAULT 'General'
        )
    ''')
    
    # Generic sample employee data for open-source publication
    employees = [
        ('1', 'John Doe', 'Engineering'),
        ('2', 'Jane Smith', 'Human Resources'),
        ('3', 'Alex Johnson', 'IT & Security'),
        ('4', 'Michael Brown', 'Operations'),
        ('5', 'Emily Davis', 'Finance'),
        ('6', 'David Wilson', 'Logistics'),
        ('7', 'Sarah Miller', 'Marketing'),
        ('8', 'James Taylor', 'Sales'),
        ('9', 'Robert Anderson', 'Management'),
        ('10', 'William Thomas', 'Quality Control')
    ]
    cursor.executemany("INSERT OR REPLACE INTO employees (pin, name, department) VALUES (?, ?, ?)", employees)
    conn.commit()
    conn.close()

init_db()

def safe_extract_time(ts_str):
    if not ts_str:
        return "--:--"
    parts = str(ts_str).strip().split()
    if len(parts) >= 2:
        return parts[1]
    return parts[0]

# --- ADMS PUSH RECEIVER (ZKTeco Protocol Endpoint) ---
@app.route('/iclock/cdata', methods=['GET', 'POST'])
def receive_cdata():
    """Receiver endpoint for ZKTeco ADMS terminals (Push Communication protocol)."""
    sn = request.args.get('SN', 'ZKTeco_Device')
    table = request.args.get('table', '')
    if request.method == 'GET':
        return "OK"

    if table == 'ATTLOG':
        try:
            raw_data = request.get_data(as_text=True)
            lines = raw_data.strip().split('\n')
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for line in lines:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    user_pin = parts[0]
                    timestamp_str = parts[1]
                    verify_type = 0
                    if len(parts) > 3:
                        try:
                            verify_type = int(parts[3])
                        except ValueError:
                            verify_type = 0
                    cursor.execute('''
                        INSERT INTO attendance_logs (user_pin, timestamp, verify_type, device_sn)
                        VALUES (?, ?, ?, ?)
                    ''', (user_pin, timestamp_str, verify_type, sn))
            conn.commit()
            conn.close()
        except Exception as e:
            print("Error processing ATTLOG:", e)
    return "OK"

@app.route('/iclock/getrequest', methods=['GET', 'POST'])
def get_request():
    """Device heartbeat check-in endpoint for ZKTeco terminals."""
    return "OK"

# --- API FOR REPORTS & DATA RETRIEVAL ---
@app.route('/api/report')
def api_report():
    try:
        target_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT pin, name, department FROM employees ORDER BY CAST(pin AS INTEGER) ASC")
        all_employees = cursor.fetchall()
        
        report_data = []
        present_count = 0
        
        for emp in all_employees:
            pin, name, dept = emp
            cursor.execute('''
                SELECT MIN(timestamp), MAX(timestamp) 
                FROM attendance_logs 
                WHERE user_pin = ? AND DATE(timestamp) = ?
            ''', (pin, target_date))
            scans = cursor.fetchone()
            
            min_ts = scans[0] if scans else None
            max_ts = scans[1] if scans else None
            
            time_in = safe_extract_time(min_ts)
            time_out = safe_extract_time(max_ts) if max_ts and min_ts != max_ts else "--:--"
            
            status = "Present" if time_in != "--:--" else "Absent"
            if status == "Present":
                present_count += 1
                
            report_data.append({
                "pin": pin,
                "name": name,
                "dept": dept,
                "time_in": time_in,
                "time_out": time_out,
                "status": status
            })
        conn.close()
        
        return jsonify({
            "date": target_date,
            "total_employees": len(all_employees),
            "present": present_count,
            "absent": len(all_employees) - present_count,
            "records": report_data
        })
    except Exception as e:
        print("Error in api_report:", e)
        return jsonify({"error": str(e)}), 500

# --- EXPORT TO EXCEL / CSV: SINGLE DAY ---
@app.route('/api/export')
def api_export():
    try:
        target_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT pin, name, department FROM employees ORDER BY CAST(pin AS INTEGER) ASC")
        all_employees = cursor.fetchall()
        
        si = StringIO()
        si.write('\ufeff') # UTF-8 BOM for Excel compatibility
        cw = csv.writer(si, delimiter=';')
        cw.writerow(['ID', 'Employee Name', 'Department', 'Clock In', 'Clock Out', 'Status'])
        
        for emp in all_employees:
            pin, name, dept = emp
            cursor.execute('''
                SELECT MIN(timestamp), MAX(timestamp) 
                FROM attendance_logs 
                WHERE user_pin = ? AND DATE(timestamp) = ?
            ''', (pin, target_date))
            scans = cursor.fetchone()
            
            min_ts = scans[0] if scans else None
            max_ts = scans[1] if scans else None
            
            time_in = safe_extract_time(min_ts)
            time_out = safe_extract_time(max_ts) if max_ts and min_ts != max_ts else "--:--"
            status = "Present" if time_in != "--:--" else "Absent"
            cw.writerow([pin, name, dept, time_in, time_out, status])
            
        conn.close()
        
        output = Response(si.getvalue(), mimetype='text/csv')
        output.headers["Content-Disposition"] = f"attachment; filename=Attendance_Report_{target_date}.csv"
        return output
    except Exception as e:
        print("Error in api_export:", e)
        return str(e), 500

# --- EXPORT TO EXCEL / CSV: FULL MONTH ---
@app.route('/api/export_month')
def api_export_month():
    try:
        target_month = request.args.get('month', date.today().strftime('%Y-%m'))
        year, m = map(int, target_month.split('-'))
        num_days = calendar.monthrange(year, m)[1]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT pin, name, department FROM employees ORDER BY CAST(pin AS INTEGER) ASC")
        all_employees = cursor.fetchall()

        si = StringIO()
        si.write('\ufeff')
        cw = csv.writer(si, delimiter=';')
        cw.writerow(['Date', 'ID', 'Employee Name', 'Department', 'Clock In', 'Clock Out', 'Status'])

        for day in range(1, num_days + 1):
            day_str = f"{target_month}-{day:02d}"
            for emp in all_employees:
                pin, name, dept = emp
                cursor.execute('''
                    SELECT MIN(timestamp), MAX(timestamp) 
                    FROM attendance_logs 
                    WHERE user_pin = ? AND DATE(timestamp) = ?
                ''', (pin, day_str))
                scans = cursor.fetchone()

                min_ts = scans[0] if scans else None
                max_ts = scans[1] if scans else None

                time_in = safe_extract_time(min_ts)
                time_out = safe_extract_time(max_ts) if max_ts and min_ts != max_ts else "--:--"
                status = "Present" if time_in != "--:--" else "Absent"
                cw.writerow([day_str, pin, name, dept, time_in, time_out, status])

        conn.close()

        output = Response(si.getvalue(), mimetype='text/csv')
        output.headers["Content-Disposition"] = f"attachment; filename=Attendance_Report_Month_{target_month}.csv"
        return output
    except Exception as e:
        print("Error in api_export_month:", e)
        return str(e), 500

# --- DASHBOARD HTML TEMPLATE ---
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZKTeco ADMS | Attendance Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #f8fafc; }
        .card-shadow { box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05); }
    </style>
</head>
<body class="text-slate-800 antialiased p-4 md:p-8">

    <div class="max-w-7xl mx-auto space-y-6">
        
        <header class="bg-white p-6 rounded-2xl border border-slate-200/80 card-shadow flex flex-col lg:flex-row justify-between lg:items-center gap-6">
            <div>
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-slate-900 text-white font-extrabold flex items-center justify-center text-lg">Z</div>
                    <div>
                        <h1 class="text-xl font-bold text-slate-900 tracking-tight">ZKTeco ADMS Attendance System</h1>
                        <p class="text-xs font-semibold text-slate-400">Biometric Face ID Real-Time Tracking</p>
                    </div>
                </div>
            </div>
            
            <div class="flex flex-wrap items-center gap-3">
                <div class="flex items-center gap-2 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
                    <label class="text-xs font-bold text-slate-500 pl-2">Daily:</label>
                    <input type="date" id="date-picker" class="border border-slate-200 rounded-lg p-1.5 text-xs font-bold bg-white text-slate-800 shadow-sm focus:outline-none" onchange="fetchReport()">
                    <button onclick="exportCSV('day')" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-sm transition">
                        📥 Daily Excel
                    </button>
                </div>

                <div class="flex items-center gap-2 bg-slate-50 p-1.5 rounded-xl border border-slate-200">
                    <label class="text-xs font-bold text-slate-500 pl-2">Monthly:</label>
                    <input type="month" id="month-picker" class="border border-slate-200 rounded-lg p-1.5 text-xs font-bold bg-white text-slate-800 shadow-sm focus:outline-none">
                    <button onclick="exportCSV('month')" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold py-1.5 px-3 rounded-lg shadow-sm transition">
                        📊 Full Month Excel
                    </button>
                </div>
            </div>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div class="bg-white p-6 rounded-2xl border border-slate-200/80 card-shadow">
                <div class="flex items-center justify-between">
                    <p class="text-xs text-slate-400 font-bold uppercase tracking-wider">Total Staff</p>
                    <span class="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 font-bold text-xs">👥</span>
                </div>
                <p id="kpi-total" class="text-3xl font-extrabold text-slate-900 mt-2">0</p>
            </div>
            
            <div class="bg-white p-6 rounded-2xl border border-slate-200/80 card-shadow border-l-4 border-l-emerald-500">
                <div class="flex items-center justify-between">
                    <p class="text-xs text-emerald-600 font-bold uppercase tracking-wider">Present Today</p>
                    <span class="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600 font-bold text-xs">✅</span>
                </div>
                <p id="kpi-present" class="text-3xl font-extrabold text-emerald-600 mt-2">0</p>
            </div>
            
            <div class="bg-white p-6 rounded-2xl border border-slate-200/80 card-shadow border-l-4 border-l-rose-500">
                <div class="flex items-center justify-between">
                    <p class="text-xs text-rose-600 font-bold uppercase tracking-wider">Absent Today</p>
                    <span class="w-8 h-8 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600 font-bold text-xs">⚠️</span>
                </div>
                <p id="kpi-absent" class="text-3xl font-extrabold text-rose-600 mt-2">0</p>
            </div>
        </div>

        <div class="bg-white rounded-2xl border border-slate-200/80 card-shadow overflow-hidden">
            <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                <h2 class="text-sm font-bold text-slate-800 uppercase tracking-wide">Attendance Timesheet</h2>
                <span class="text-xs font-semibold text-slate-400 bg-white border border-slate-200 px-2.5 py-1 rounded-full shadow-sm">Auto-refresh (10s)</span>
            </div>
            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="text-[11px] font-extrabold uppercase text-slate-400 bg-slate-50 border-b border-slate-200/80">
                            <th class="py-3.5 px-6">Employee</th>
                            <th class="py-3.5 px-4">Department</th>
                            <th class="py-3.5 px-4 text-center">Clock In</th>
                            <th class="py-3.5 px-4 text-center">Clock Out</th>
                            <th class="py-3.5 px-6 text-right">Status</th>
                        </tr>
                    </thead>
                    <tbody id="report-body" class="divide-y divide-slate-100 text-sm bg-white">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        const today = new Date();
        document.getElementById('date-picker').valueAsDate = today;
        document.getElementById('month-picker').value = today.toISOString().slice(0,7);

        function getInitials(name) {
            if (!name) return "??";
            const parts = name.trim().split(" ");
            if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
            return name.substring(0, 2).toUpperCase();
        }

        async function fetchReport() {
            const date = document.getElementById('date-picker').value;
            try {
                const res = await fetch(`/api/report?date=${date}`);
                const data = await res.json();

                document.getElementById('kpi-total').innerText = data.total_employees || 0;
                document.getElementById('kpi-present').innerText = data.present || 0;
                document.getElementById('kpi-absent').innerText = data.absent || 0;

                const tbody = document.getElementById('report-body');
                tbody.innerHTML = '';

                if (!data.records || data.records.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-slate-400 font-medium">No records found for the selected date.</td></tr>';
                    return;
                }

                data.records.forEach(emp => {
                    const isPresent = emp.status === "Present";
                    const initials = getInitials(emp.name);
                    
                    const statusBadge = isPresent 
                        ? `<span class="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200/60 px-3 py-1 rounded-full text-xs font-bold">
                             <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Present
                           </span>`
                        : `<span class="inline-flex items-center gap-1.5 bg-rose-50 text-rose-700 border border-rose-200/60 px-3 py-1 rounded-full text-xs font-bold">
                             <span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Absent
                           </span>`;

                    const row = `
                        <tr class="hover:bg-slate-50/80 transition-colors">
                            <td class="py-4 px-6">
                                <div class="flex items-center gap-3">
                                    <div class="w-9 h-9 rounded-full bg-slate-100 border border-slate-200 text-slate-700 font-extrabold text-xs flex items-center justify-center shrink-0">
                                        ${initials}
                                    </div>
                                    <div>
                                        <p class="font-bold text-slate-900">${emp.name}</p>
                                        <p class="text-[11px] font-mono text-slate-400">ID #${emp.pin}</p>
                                    </div>
                                </div>
                            </td>
                            <td class="py-4 px-4 font-medium text-slate-500 text-xs">${emp.dept}</td>
                            <td class="py-4 px-4 text-center font-mono ${emp.time_in !== '--:--' ? 'text-emerald-600 font-bold text-sm' : 'text-slate-300'}">${emp.time_in}</td>
                            <td class="py-4 px-4 text-center font-mono ${emp.time_out !== '--:--' ? 'text-amber-600 font-bold text-sm' : 'text-slate-300'}">${emp.time_out}</td>
                            <td class="py-4 px-6 text-right">${statusBadge}</td>
                        </tr>
                    `;
                    tbody.innerHTML += row;
                });
            } catch (e) {
                console.error("Fetch error:", e);
            }
        }

        function exportCSV(type) {
            if (type === 'day') {
                const date = document.getElementById('date-picker').value;
                window.location.href = `/api/export?date=${date}`;
            } else if (type === 'month') {
                const month = document.getElementById('month-picker').value;
                window.location.href = `/api/export_month?month=${month}`;
            }
        }

        fetchReport();
        setInterval(() => {
            const datePicker = document.getElementById('date-picker');
            const todayStr = new Date().toISOString().split('T')[0];
            if (datePicker.value === todayStr) { fetchReport(); }
        }, 10000);
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

if __name__ == '__main__':
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    app.run(host=host, port=port)

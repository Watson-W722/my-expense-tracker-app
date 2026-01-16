import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta, timezone
import time
import os

# --- 頁面設定 ---
st.set_page_config(page_title="我的記帳本", layout="wide", page_icon="💰")

# ==========================================
# 0. UI 美化樣式
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
        background-color: #f8f9fa;
        color: #2c3e50;
    }
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
    }
    #MainMenu {visibility: hidden;}
    .metric-container {
        display: flex;
        flex-wrap: wrap;
        gap: 15px;
        margin: 10px 0 20px 0;
    }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 15px 20px;
        flex: 1;
        min-width: 140px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #eef0f2;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }
    .metric-label { font-size: 0.85rem; color: #888; font-weight: 500; margin-bottom: 5px; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #2c3e50; }
    .val-green { color: #2ecc71; }
    .val-red { color: #e74c3c; }
    /* 按鈕樣式 */          
    div.stButton > button { border-radius: 8px; font-weight: 600; }

    /* Tab 樣式微調 */        
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: white;
        border-radius: 8px 8px 0 0;
        gap: 1px;
        padding: 10px 20px;
        font-size: 1.1rem;
        font-weight: 600;
        color: #6c757d;
        border: 1px solid #dee2e6;
        border-bottom: none;
    }
    .stTabs [aria-selected="true"] {
        border-top: 3px solid #0d6efd;
        color: #0d6efd !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 核心連線模組 (支援動態檔名)
# ==========================================
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = None
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except Exception:
        pass
    if creds is None:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
        except FileNotFoundError:
            st.error("❌ 找不到金鑰！請檢查 service_account.json 或 Secrets。")
            return None
    return gspread.authorize(creds)

# [關鍵] 取得設定檔中的試算表名稱，若無則用預設值
def get_sheet_name():
    return st.secrets.get("spreadsheet_name", "My_Expense_Tracker")

@st.cache_data
def get_data(worksheet_name):
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try:
        # [關鍵修正] 使用動態名稱
        sheet = client.open(get_sheet_name())
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if worksheet_name == "Settings":
            required_cols = ["Main_Category", "Sub_Category", "Payment_Method", "Currency"]
            for col in required_cols:
                if col not in df.columns: df[col] = ""
        
        if worksheet_name == "Recurring":
            required_cols = ["Day", "Type", "Main_Category", "Sub_Category", "Payment_Method", "Currency", "Amount_Original", "Note", "Last_Run_Month"]
            for col in required_cols:
                if col not in df.columns: df[col] = ""
                
        return df
    except Exception:
        return pd.DataFrame()

def append_data(worksheet_name, row_data):
    client = get_gspread_client()
    try:
        # [關鍵修正] 使用動態名稱
        sheet = client.open(get_sheet_name())
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"寫入錯誤: {e}")
        return False

def save_settings_data(new_settings_df):
    client = get_gspread_client()
    try:
        # [關鍵修正] 使用動態名稱
        sheet = client.open(get_sheet_name())
        worksheet = sheet.worksheet("Settings")
        worksheet.clear()
        new_settings_df = new_settings_df.fillna("")
        data_to_write = [new_settings_df.columns.values.tolist()] + new_settings_df.values.tolist()
        worksheet.update(values=data_to_write)
        return True
    except Exception as e:
        st.error(f"儲存設定失敗: {e}")
        return False

def update_recurring_last_run(row_index, month_str):
    client = get_gspread_client()
    try:
        # [關鍵修正] 使用動態名稱
        sheet = client.open(get_sheet_name())
        worksheet = sheet.worksheet("Recurring")
        worksheet.update_cell(row_index + 2, 9, month_str)
        return True
    except Exception as e:
        return False

def delete_recurring_rule(row_index):
    client = get_gspread_client()
    try:
        # [關鍵修正] 使用動態名稱
        sheet = client.open(get_sheet_name())
        worksheet = sheet.worksheet("Recurring")
        worksheet.delete_rows(row_index + 2)
        return True
    except Exception:
        return False

# --- 取得使用者指定時區的日期 ---
def get_user_date(offset_hours):
    tz = timezone(timedelta(hours=offset_hours))
    return datetime.now(tz).date()

# ==========================================
# 2. 匯率處理模組
# ==========================================
@st.cache_data(ttl=3600)
def get_exchange_rates():
    url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
    try:
        dfs = pd.read_html(url)
        df = dfs[0]
        df = df.iloc[:, 0:5]
        df.columns = ["Currency_Name", "Cash_Buy", "Cash_Sell", "Spot_Buy", "Spot_Sell"]
        df["Currency"] = df["Currency_Name"].str.extract(r'\(([A-Z]+)\)')
        rates = df.dropna(subset=['Currency']).copy()
        rates["Spot_Sell"] = pd.to_numeric(rates["Spot_Sell"], errors='coerce')
        rate_dict = rates.set_index("Currency")["Spot_Sell"].to_dict()
        rate_dict["TWD"] = 1.0
        return rate_dict
    except:
        return {}

def calculate_sgd(amount, currency, rates):
    if currency == "SGD": return amount, 1.0
    try:
        sgd_rate = rates.get("SGD")
        target_rate = rates.get(currency)
        if not sgd_rate or not target_rate: return amount, 0
        conversion_factor = target_rate / sgd_rate
        sgd_amount = amount * conversion_factor
        return round(sgd_amount, 2), conversion_factor
    except:
        return amount, 0

# ==========================================
# 3. 主程式 UI 邏輯
# ==========================================

# --- 側邊欄時區設定 ---
with st.sidebar:
    st.header("🌍 地區設定")
    # [新增] 顯示目前連線的試算表名稱，方便除錯
    st.caption(f"目前連線帳本：{get_sheet_name()}")
    
    tz_options = {
        "台灣/新加坡 (UTC+8)": 8,
        "日本/韓國 (UTC+9)": 9,
        "泰國/越南 (UTC+7)": 7,
        "美東 (UTC-4)": -4,
        "美西 (UTC-7)": -7,
        "歐洲中部 (UTC+1)": 1,
        "英國 (UTC+0)": 0
    }
    selected_tz_label = st.selectbox("當前位置時區", list(tz_options.keys()), index=0)
    user_offset = tz_options[selected_tz_label]
    st.info(f"目前日期：{get_user_date(user_offset)}")

rates = get_exchange_rates()

# 檢查固定收支
def check_and_run_recurring():
    if 'recurring_checked' in st.session_state:
        return 

    rec_df = get_data("Recurring")
    if rec_df.empty: return

    sys_tz = timezone(timedelta(hours=8))
    today = datetime.now(sys_tz)
    current_month_str = today.strftime("%Y-%m")
    current_day = today.day
    
    executed_count = 0
    
    for idx, row in rec_df.iterrows():
        try:
            last_run = str(row['Last_Run_Month']).strip()
            scheduled_day = int(row['Day'])
            
            if last_run != current_month_str and current_day >= scheduled_day:
                amt_org = float(row['Amount_Original'])
                curr = row['Currency']
                amt_sgd, _ = calculate_sgd(amt_org, curr, rates)
                
                tx_date = today.strftime("%Y-%m-%d")
                tx_row = [
                    tx_date, 
                    row['Type'], 
                    row['Main_Category'], 
                    row['Sub_Category'], 
                    row['Payment_Method'], 
                    curr, 
                    amt_org, 
                    amt_sgd, 
                    f"(自動) {row['Note']}", 
                    str(datetime.now(sys_tz))
                ]
                
                if append_data("Transactions", tx_row):
                    update_recurring_last_run(idx, current_month_str)
                    executed_count += 1
        except Exception:
            continue

    if executed_count > 0:
        st.toast(f"🤖 自動補登了 {executed_count} 筆固定收支！", icon="✅")
        st.cache_data.clear()
        time.sleep(1)
        st.rerun()
    
    st.session_state['recurring_checked'] = True

check_and_run_recurring()

# --- Header ---
c_logo, c_title = st.columns([1, 15]) 
with c_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=60) 
    else: st.write("💰")
with c_title:
    st.markdown("<h2 style='margin-bottom: 0; padding-top: 10px;'>我的記帳本</h2>", unsafe_allow_html=True)

# --- 讀取設定 ---
settings_df = get_data("Settings")
cat_mapping = {}     
payment_list = []
currency_list_custom = []

if not settings_df.empty:
    if "Main_Category" in settings_df.columns and "Sub_Category" in settings_df.columns:
        valid_cats = settings_df[["Main_Category", "Sub_Category"]].astype(str)
        valid_cats = valid_cats[valid_cats["Main_Category"] != ""]
        for _, row in valid_cats.iterrows():
            main = row["Main_Category"]
            sub = row["Sub_Category"]
            if main not in cat_mapping: cat_mapping[main] = []
            if sub and sub != "" and sub not in cat_mapping[main]: cat_mapping[main].append(sub)
    if "Payment_Method" in settings_df.columns:
        payment_list = settings_df[settings_df["Payment_Method"] != ""]["Payment_Method"].unique().tolist()
    if "Currency" in settings_df.columns:
        currency_list_custom = settings_df[settings_df["Currency"] != ""]["Currency"].unique().tolist()
    else: currency_list_custom = ["SGD", "TWD", "USD"]

if not cat_mapping: 
    cat_mapping = {"收入": ["薪資", "獎金"], "食": ["早餐"], "行": ["捷運"]}
elif "收入" not in cat_mapping:
    cat_mapping["收入"] = ["薪資", "獎金"]

if not payment_list: payment_list = ["現金"]
if not currency_list_custom: currency_list_custom = ["SGD", "TWD"]
main_cat_list = list(cat_mapping.keys())

# --- 頁籤 ---
tab1, tab2, tab3 = st.tabs(["📝 每日記帳", "📊 收支分析", "⚙️ 系統設定"])

# ================= Tab 1: 每日記帳 =================
with tab1:
    if st.session_state.get('should_clear_input'):
        st.session_state.form_amount_org = 0.0
        st.session_state.form_amount_sgd = 0.0
        st.session_state.form_note = ""
        st.session_state.should_clear_input = False

    if 'form_currency' not in st.session_state: st.session_state.form_currency = 'SGD'
    if 'form_amount_org' not in st.session_state: st.session_state.form_amount_org = 0.0
    if 'form_amount_sgd' not in st.session_state: st.session_state.form_amount_sgd = 0.0
    if 'form_note' not in st.session_state: st.session_state.form_note = ""

    def on_input_change():
        c = st.session_state.form_currency
        a = st.session_state.form_amount_org
        val, _ = calculate_sgd(a, c, rates)
        st.session_state.form_amount_sgd = val

    # --- 計算數據 ---
    user_today = get_user_date(user_offset)
    current_month_str = user_today.strftime("%Y-%m")
    
    tx_df = get_data("Transactions")

    total_income = 0
    total_expense = 0
    
    if not tx_df.empty and 'Date' in tx_df.columns:
        tx_df['Date'] = pd.to_datetime(tx_df['Date'], errors='coerce')
        mask = (tx_df['Date'].dt.strftime('%Y-%m') == current_month_str)
        month_tx = tx_df[mask]
        month_tx['Amount_SGD'] = pd.to_numeric(month_tx['Amount_SGD'], errors='coerce').fillna(0)
        
        if 'Type' in month_tx.columns:
            total_income = month_tx[month_tx['Type'] == '收入']['Amount_SGD'].sum()
            total_expense = month_tx[month_tx['Type'] != '收入']['Amount_SGD'].sum()
    
    balance = total_income - total_expense
    balance_class = "val-green" if balance >= 0 else "val-red"

    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-card">
            <span class="metric-label">本月總收入</span>
            <span class="metric-value">${total_income:,.0f}</span>
        </div>
        <div class="metric-card">
            <span class="metric-label">已支出</span>
            <span class="metric-value">${total_expense:,.0f}</span>
        </div>
        <div class="metric-card">
            <span class="metric-label">剩餘可用</span>
            <span class="metric-value {balance_class}">${balance:,.0f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("##### ✍️ 新增交易")
        c1, c2 = st.columns([1, 1])
        with c1: 
            date_input = st.date_input("日期", user_today)
        with c2: payment = st.selectbox("付款方式", payment_list)
        c3, c4 = st.columns([1, 1])
        with c3: main_cat = st.selectbox("大類別", main_cat_list, key="input_main_cat")
        with c4: sub_cat = st.selectbox("次類別", cat_mapping.get(main_cat, []))

        with st.container(border=True): 
            st.caption("💰 金額設定")
            c5, c6, c7 = st.columns([1.5, 2, 2])
            with c5: currency = st.selectbox("幣別", currency_list_custom, key="form_currency", on_change=on_input_change)
            with c6: amount_org = st.number_input(f"金額 ({currency})", step=1.0, key="form_amount_org", on_change=on_input_change)
            with c7: 
                amount_sgd = st.number_input("折合新幣 (SGD)", step=0.1, key="form_amount_sgd")
                if currency != "SGD" and amount_org != 0:
                     _, rate_used = calculate_sgd(100, currency, rates)
                     if rate_used > 0: st.caption(f"匯率: {rate_used:.4f}")

        note = st.text_input("備註", max_chars=20, placeholder="輸入消費內容 (限20字)...", key="form_note")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("確認送出記帳", type="primary", use_container_width=True):
            if amount_sgd == 0:
                st.error("金額不能為 0")
            else:
                with st.spinner('📡 資料寫入 Google Sheet 中...'):
                    tx_type = "收入" if main_cat == "收入" else "支出"
                    sys_now = datetime.now()
                    row = [str(date_input), tx_type, main_cat, sub_cat, payment, currency, amount_org, amount_sgd, note, str(sys_now)]
                    if append_data("Transactions", row):
                        st.success(f"✅ {tx_type}已記錄 ${amount_sgd}，更新中...")
                        st.session_state['should_clear_input'] = True
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 寫入失敗")

# ================= Tab 2: 收支分析 =================
with tab2:
    st.markdown("##### 📊 收支狀況")
    df_tx = get_data("Transactions")

    if df_tx.empty:
        st.info("尚無交易資料")
    else:
        df_tx['Date'] = pd.to_datetime(df_tx['Date'], errors='coerce')
        df_tx['Amount_SGD'] = pd.to_numeric(df_tx['Amount_SGD'], errors='coerce').fillna(0)
        df_tx['Month'] = df_tx['Date'].dt.strftime('%Y-%m')
        
        all_months = sorted(df_tx['Month'].unique())
        
        with st.expander("📅 篩選區間", expanded=True):
            if len(all_months) > 0:
                c_sel1, c_sel2 = st.columns(2)
                with c_sel1: start_month = st.selectbox("開始月份", all_months, index=0)
                with c_sel2: end_month = st.selectbox("結束月份", all_months, index=len(all_months)-1)
                selected_months = [m for m in all_months if start_month <= m <= end_month]
                
                expense_trend = df_tx[(df_tx['Month'].isin(selected_months)) & (df_tx['Type'] != '收入')].groupby('Month')['Amount_SGD'].sum().reset_index()
                expense_trend.rename(columns={'Amount_SGD': 'Amount'}, inplace=True)
                expense_trend['Type'] = '支出'
                
                income_trend = df_tx[(df_tx['Month'].isin(selected_months)) & (df_tx['Type'] == '收入')].groupby('Month')['Amount_SGD'].sum().reset_index()
                income_trend.rename(columns={'Amount_SGD': 'Amount'}, inplace=True)
                income_trend['Type'] = '收入'
                
                trend_data = pd.concat([expense_trend, income_trend], ignore_index=True)
                
                if not trend_data.empty:
                    import plotly.express as px
                    fig_trend = px.bar(trend_data, x="Month", y="Amount", color="Type", barmode="group", 
                                     color_discrete_map={"收入": "#2ecc71", "支出": "#ff6b6b"})
                    fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, l=10, r=10, b=10))
                    st.plotly_chart(fig_trend, use_container_width=True)

        st.markdown("---")
        target_month = st.selectbox("🗓️ 查看詳細月份", sorted(all_months, reverse=True))
        
        month_data = df_tx[df_tx['Month'] == target_month]
        monthly_income = month_data[month_data['Type'] == '收入']['Amount_SGD'].sum()
        monthly_expense = month_data[month_data['Type'] != '收入']['Amount_SGD'].sum()
        
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card" style="border-left: 5px solid #2ecc71;">
                <span class="metric-label">總收入</span>
                <span class="metric-value">${monthly_income:,.0f}</span>
            </div>
            <div class="metric-card" style="border-left: 5px solid #ff6b6b;">
                <span class="metric-label">總支出</span>
                <span class="metric-value">${monthly_expense:,.0f}</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">結餘</span>
                <span class="metric-value">${monthly_income - monthly_expense:,.0f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        expense_only_data = month_data[month_data['Type'] != '收入']
        if not expense_only_data.empty:
            pie_data = expense_only_data.groupby("Main_Category")["Amount_SGD"].sum().reset_index()
            pie_data = pie_data[pie_data["Amount_SGD"] > 0]
            
            if not pie_data.empty:
                fig_pie = px.pie(pie_data, values="Amount_SGD", names="Main_Category", hole=0.5,
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("本月支出相抵後無正向金額，無法顯示圓餅圖。")

# ================= Tab 3: 設定管理 =================
with tab3:
    st.markdown("##### ⚙️ 系統資料庫")
    
    if 'temp_cat_map' not in st.session_state: st.session_state.temp_cat_map = cat_mapping
    if 'temp_pay_list' not in st.session_state: st.session_state.temp_pay_list = payment_list
    if 'temp_curr_list' not in st.session_state: st.session_state.temp_curr_list = currency_list_custom

    # 1. 固定收支
    with st.expander("🔄 每月固定收支 (薪資、房租...)", expanded=True):
        with st.popover("➕ 新增固定規則", use_container_width=True):
            st.markdown("###### 設定每月自動執行的項目")
            if 'rec_currency' not in st.session_state: st.session_state.rec_currency = 'SGD'
            if 'rec_amount_org' not in st.session_state: st.session_state.rec_amount_org = 0.0
            
            def on_rec_change():
                c = st.session_state.rec_currency
                a = st.session_state.rec_amount_org
                val, _ = calculate_sgd(a, c, rates)
                st.session_state.rec_amount_sgd = val

            rec_day = st.number_input("每月幾號執行?", min_value=1, max_value=31, value=5)
            c_rec1, c_rec2 = st.columns(2)
            with c_rec1: rec_main = st.selectbox("大類別", main_cat_list, key="rec_main")
            with c_rec2: rec_sub = st.selectbox("次類別", cat_mapping.get(rec_main, []), key="rec_sub")
            rec_pay = st.selectbox("付款方式", payment_list, key="rec_pay")
            c_r1, c_r2, c_r3 = st.columns([1.5, 2, 2])
            with c_r1: rec_curr = st.selectbox("幣別", currency_list_custom, key="rec_currency", on_change=on_rec_change)
            with c_r2: rec_amt_org = st.number_input("原幣金額", step=1.0, key="rec_amount_org", on_change=on_rec_change)
            with c_r3: rec_amt_sgd = st.number_input("折合新幣", step=0.1, key="rec_amount_sgd")
            rec_note = st.text_input("備註 (例如: 房租)", key="rec_note")
            
            if st.button("儲存規則", type="primary", use_container_width=True):
                rec_type = "收入" if rec_main == "收入" else "支出"
                new_rule = [rec_day, rec_type, rec_main, rec_sub, rec_pay, rec_curr, rec_amt_org, rec_note, "New", "Active"]
                if append_data("Recurring", new_rule):
                    st.success("✅ 規則已新增！")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")
        rec_df = get_data("Recurring")
        if not rec_df.empty:
            for idx, row in rec_df.iterrows():
                # [關鍵修正] 顯示格式調整
                header_txt = f"📅 每月 {row['Day']} 號 - {row['Main_Category']} > {row['Sub_Category']} > {row['Amount_Original']} {row['Currency']}"
                with st.expander(header_txt):
                    c_list1, c_list2 = st.columns([4, 1])
                    with c_list1:
                        st.write(f"📝 {row['Note']} | {row['Amount_Original']} {row['Currency']} ({row['Payment_Method']})")
                    with c_list2:
                        if st.button("🗑️ 刪除", key=f"del_rec_{idx}", type="primary"):
                            if delete_recurring_rule(idx):
                                st.toast("規則已刪除")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("目前沒有設定固定收支規則")

    # 2. 類別管理
    with st.expander("📂 類別與子類別管理"):
        with st.popover("➕ 新增大類", use_container_width=True):
            new_main = st.text_input("類別名稱", placeholder="例如: 醫療", label_visibility="collapsed")
            if st.button("確認新增", type="primary", use_container_width=True):
                if new_main and new_main not in st.session_state.temp_cat_map:
                    st.session_state.temp_cat_map[new_main] = []
                    st.rerun()
        for idx, main in enumerate(st.session_state.temp_cat_map.keys()):
            with st.container():
                with st.expander(f"📁 {main}", expanded=False):
                    new_main_name = st.text_input("名稱", value=main, key=f"ren_{idx}", label_visibility="collapsed")
                    if new_main_name != main:
                        st.session_state.temp_cat_map[new_main_name] = st.session_state.temp_cat_map.pop(main)
                        st.rerun()
                    current_subs = st.session_state.temp_cat_map[new_main_name]
                    updated_subs = st.multiselect("子類", current_subs, default=current_subs, key=f"ms_{idx}", label_visibility="collapsed")
                    if len(updated_subs) < len(current_subs):
                        st.session_state.temp_cat_map[new_main_name] = updated_subs
                        st.rerun()
                    cs1, cs2 = st.columns([3, 1])
                    with cs1: new_s = st.text_input("add", key=f"ns_{idx}", label_visibility="collapsed", placeholder="新增子類別...")
                    with cs2: 
                        if st.button("加入", key=f"bns_{idx}"):
                            if new_s and new_s not in st.session_state.temp_cat_map[new_main_name]:
                                st.session_state.temp_cat_map[new_main_name].append(new_s)
                                st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"🗑️ 刪除 {new_main_name}", key=f"dm_{idx}", type="secondary", use_container_width=True):
                        del st.session_state.temp_cat_map[new_main_name]
                        st.rerun()

    # 3. 其他設定
    with st.expander("💳 付款與幣別"):
        st.subheader("付款方式")
        pays = st.session_state.temp_pay_list
        u_pays = st.multiselect("付款", pays, default=pays, key="mp_pay", label_visibility="collapsed")
        if len(u_pays) < len(pays):
            st.session_state.temp_pay_list = u_pays
            st.rerun()
        c_p1, c_p2 = st.columns([3,1])
        with c_p1: np = st.text_input("np", label_visibility="collapsed", placeholder="新增付款方式")
        with c_p2: 
            if st.button("加入", key="bp"):
                if np and np not in st.session_state.temp_pay_list:
                    st.session_state.temp_pay_list.append(np)
                    st.rerun()
        st.divider()
        st.subheader("常用幣別")
        curs = st.session_state.temp_curr_list
        u_curs = st.multiselect("幣別", curs, default=curs, key="mp_cur", label_visibility="collapsed")
        if len(u_curs) < len(curs):
            st.session_state.temp_curr_list = u_curs
            st.rerun()
        c_c1, c_c2 = st.columns([3,1])
        with c_c1: nc = st.text_input("nc", label_visibility="collapsed", placeholder="新增幣別")
        with c_c2:
            if st.button("加入", key="bc"):
                if nc and nc not in st.session_state.temp_curr_list:
                    st.session_state.temp_curr_list.append(nc)
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 儲存所有設定", type="primary", use_container_width=True):
        rows = []
        for m, subs in st.session_state.temp_cat_map.items():
            if not subs: rows.append({"Main_Category": m, "Sub_Category": ""})
            else:
                for s in subs: rows.append({"Main_Category": m, "Sub_Category": s})
        df_cat_new = pd.DataFrame(rows)
        list_pay = st.session_state.temp_pay_list
        list_curr = st.session_state.temp_curr_list
        max_len = max(len(df_cat_new), len(list_pay), len(list_curr))
        final_df = pd.DataFrame()
        if not df_cat_new.empty:
            final_df["Main_Category"] = df_cat_new["Main_Category"].reindex(range(max_len)).fillna("")
            final_df["Sub_Category"] = df_cat_new["Sub_Category"].reindex(range(max_len)).fillna("")
        else:
            final_df["Main_Category"] = [""] * max_len
            final_df["Sub_Category"] = [""] * max_len
        final_df["Payment_Method"] = pd.Series(list_pay).reindex(range(max_len)).fillna("")
        final_df["Currency"] = pd.Series(list_curr).reindex(range(max_len)).fillna("")
        
        if save_settings_data(final_df):
            st.toast("設定已儲存！", icon="💾")
            st.cache_data.clear()
            del st.session_state.temp_cat_map
            time.sleep(1)
            st.rerun()
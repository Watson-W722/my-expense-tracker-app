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
# [設定區] 範本連結
# ==========================================
TEMPLATE_URL = "https://docs.google.com/spreadsheets/d/1j7WM4A6bgRr1S-0BvHYPw9Xp5oXs0Ikp969-Ys65JL0/copy" 

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
    
    div.stButton > button { border-radius: 8px; font-weight: 600; }
    
    .stTabs {
        position: sticky;
        top: 0;
        background-color: #f8f9fa;
        z-index: 999;
        padding-top: 10px;
        margin-top: -20px;
    }
    . /* Tab 樣式微調 */
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
        background-color: #ffffff;
        color: #0d6efd !important;
        border-top: 3px solid #0d6efd;
    }
   
    .login-container {
        max-width: 600px;
        margin: 50px auto;
        padding: 40px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
    }
    .step-text { text-align: left; margin-bottom: 10px; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 核心連線模組
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
            return None
    return gspread.authorize(creds)

def open_spreadsheet(client, source_str):
    if source_str.startswith("http"):
        return client.open_by_url(source_str)
    else:
        return client.open(source_str)

def check_connection():
    url_sheet_name = st.query_params.get("sheet", None)
    
    # 這裡使用 current_sheet_name 作為主要判斷依據
    if "current_sheet_name" not in st.session_state:
        st.session_state.current_sheet_name = url_sheet_name

    if not st.session_state.current_sheet_name:
        show_login_screen()
        st.stop()

    client = get_gspread_client()
    if not client:
        st.error("❌ 系統錯誤：無法讀取機器人金鑰。")
        st.stop()

    try:
        sheet = open_spreadsheet(client, st.session_state.current_sheet_name)
        st.query_params["sheet"] = st.session_state.current_sheet_name
        return st.session_state.current_sheet_name, sheet.title
    except Exception as e:
        st.error(f"❌ 連線失敗")
        st.warning("請確認網址或名稱正確，且已分享給機器人。")
        if "gcp_service_account" in st.secrets:
            st.code(st.secrets["gcp_service_account"]["client_email"], language="text")
        if st.button("⬅️ 返回"):
            # 清除 Session 確保跳回登入頁
            if "current_sheet_name" in st.session_state:
                del st.session_state["current_sheet_name"]
            st.query_params.clear()
            st.rerun()
        st.stop()

def show_login_screen():
    bot_email = "尚未設定 Secrets"
    if "gcp_service_account" in st.secrets:
        bot_email = st.secrets["gcp_service_account"]["client_email"]

    st.markdown("""
    <div class="login-container">
        <h2 style="margin-bottom: 20px;">👋 歡迎使用記帳本</h2>
    """, unsafe_allow_html=True)

    col_L, col_R = st.columns([1, 1])
    with col_L:
        st.info("我是新使用者")
        st.markdown("<div class='step-text'>1. 下載專屬範本</div>", unsafe_allow_html=True)
        if "http" in TEMPLATE_URL:
            st.link_button("📄 建立副本", TEMPLATE_URL, type="primary", use_container_width=True)
        else:
            st.warning("⚠️ 未設定範本連結")
        st.markdown("<div class='step-text'>2. 共用給機器人：</div>", unsafe_allow_html=True)
        st.code(bot_email, language="text")

    with col_R:
        st.success("我已經準備好了")
        st.markdown("<div class='step-text'>3. 輸入 <b>Google Sheet 網址</b></div>", unsafe_allow_html=True)
        sheet_input = st.text_input("連結或名稱", placeholder="https://docs.google.com/...")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 連接帳本", type="primary", use_container_width=True):
            if sheet_input:
                st.session_state.current_sheet_name = sheet_input.strip()
                st.rerun()
            else:
                st.warning("請輸入內容")
    st.markdown("</div>", unsafe_allow_html=True)

CURRENT_SHEET_SOURCE, DISPLAY_TITLE = check_connection()

# ==========================================
# 資料讀寫函式
# ==========================================
@st.cache_data
def get_data(worksheet_name, source_str):
    client = get_gspread_client()
    try:
        sheet = open_spreadsheet(client, source_str)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        if worksheet_name == "Settings":
            required_cols = ["Main_Category", "Sub_Category", "Payment_Method", "Currency", "Default_Currency"]
            for col in required_cols:
                if col not in df.columns: df[col] = ""
        
        if worksheet_name == "Recurring":
            required_cols = ["Day", "Type", "Main_Category", "Sub_Category", "Payment_Method", "Currency", "Amount_Original", "Note", "Last_Run_Month"]
            for col in required_cols:
                if col not in df.columns: df[col] = ""
                
        return df
    except Exception:
        return pd.DataFrame()

def append_data(worksheet_name, row_data, source_str):
    client = get_gspread_client()
    try:
        sheet = open_spreadsheet(client, source_str)
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"寫入錯誤: {e}")
        return False

def save_settings_data(new_settings_df, source_str):
    client = get_gspread_client()
    try:
        sheet = open_spreadsheet(client, source_str)
        worksheet = sheet.worksheet("Settings")
        worksheet.clear()
        new_settings_df = new_settings_df.fillna("")
        data_to_write = [new_settings_df.columns.values.tolist()] + new_settings_df.values.tolist()
        worksheet.update(values=data_to_write)
        return True
    except Exception as e:
        st.error(f"儲存設定失敗: {e}")
        return False

def update_recurring_last_run(row_index, month_str, source_str):
    client = get_gspread_client()
    try:
        sheet = open_spreadsheet(client, source_str)
        worksheet = sheet.worksheet("Recurring")
        worksheet.update_cell(row_index + 2, 9, month_str)
        return True
    except Exception as e:
        return False

def delete_recurring_rule(row_index, source_str):
    client = get_gspread_client()
    try:
        sheet = open_spreadsheet(client, source_str)
        worksheet = sheet.worksheet("Recurring")
        worksheet.delete_rows(row_index + 2)
        return True
    except Exception:
        return False

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

def calculate_exchange(amount, input_currency, target_currency, rates):
    if input_currency == target_currency: return amount, 1.0
    try:
        rate_in = rates.get(input_currency)
        rate_target = rates.get(target_currency)
        if not rate_in or not rate_target: return amount, 0
        conversion_factor = rate_in / rate_target
        exchanged_amount = amount * conversion_factor
        return round(exchanged_amount, 2), conversion_factor
    except:
        return amount, 0

# ==========================================
# [關鍵修復] 定義 Callback 與 存檔函式
# ==========================================
def save_all_to_sheet():
    """收集所有暫存 Session State 並寫入 Google Sheet"""
    rows = []
    # 1. 類別
    if 'temp_cat_map' in st.session_state:
        for m, subs in st.session_state.temp_cat_map.items():
            if not subs: 
                rows.append({"Main_Category": m, "Sub_Category": ""})
            else:
                for s in subs:
                    rows.append({"Main_Category": m, "Sub_Category": s})
    
    df_cat_new = pd.DataFrame(rows)
    
    # 2. 付款與幣別 (使用 get 以防萬一)
    # 若 session_state 中沒有這些 key，回退使用全域變數 payment_list / currency_list_custom
    list_pay = st.session_state.get('temp_pay_list', payment_list)
    list_curr = st.session_state.get('temp_curr_list', currency_list_custom)
    
    # 3. 合併 DataFrame
    max_len = max(len(df_cat_new), len(list_pay), len(list_curr)) if len(df_cat_new) > 0 or len(list_pay) > 0 or len(list_curr) > 0 else 1
    final_df = pd.DataFrame()
    
    if not df_cat_new.empty:
        final_df["Main_Category"] = df_cat_new["Main_Category"].reindex(range(max_len)).fillna("")
        final_df["Sub_Category"] = df_cat_new["Sub_Category"].reindex(range(max_len)).fillna("")
    else:
        final_df["Main_Category"] = [""] * max_len
        final_df["Sub_Category"] = [""] * max_len
        
    final_df["Payment_Method"] = pd.Series(list_pay).reindex(range(max_len)).fillna("")
    final_df["Currency"] = pd.Series(list_curr).reindex(range(max_len)).fillna("")
    
    # 4. 預設幣別
    final_df["Default_Currency"] = ""
    if len(final_df) > 0:
        final_df.at[0, "Default_Currency"] = st.session_state.get('temp_default_curr', default_currency_setting)
    
    # 5. 寫入
    if save_settings_data(final_df, CURRENT_SHEET_SOURCE):
        st.toast("✅ 設定已儲存！", icon="💾")
        st.cache_data.clear()

def add_sub_callback(main_cat, key):
    new_val = st.session_state[key]
    if new_val:
        if new_val not in st.session_state.temp_cat_map[main_cat]:
            st.session_state.temp_cat_map[main_cat].append(new_val)
        st.session_state[key] = "" # 這裡執行清空輸入框

def add_pay_callback(key):
    new_val = st.session_state[key]
    if new_val:
        if new_val not in st.session_state.temp_pay_list:
            st.session_state.temp_pay_list.append(new_val)
        st.session_state[key] = ""

def add_curr_callback(key):
    new_val = st.session_state[key]
    if new_val:
        if new_val not in st.session_state.temp_curr_list:
            st.session_state.temp_curr_list.append(new_val)
        st.session_state[key] = ""

# ==========================================
# 3. 主程式 UI 邏輯
# ==========================================

# --- 側邊欄 ---
with st.sidebar:
    st.header("🌍 地區設定")
    st.success(f"📘 帳本：{DISPLAY_TITLE}")
    
    # [修正] 登出按鈕：徹底清除相關 Session State
    if st.button("🚪 切換帳本 (登出)"):
        keys_to_clear = ["current_sheet_name", "current_sheet_source", "current_sheet_title"]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        st.query_params.clear()
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    tz_options = {"台灣/新加坡 (UTC+8)": 8, "日本/韓國 (UTC+9)": 9, "泰國 (UTC+7)": 7, "美東 (UTC-4)": -4, "歐洲 (UTC+1)": 1}
    selected_tz_label = st.selectbox("當前位置時區", list(tz_options.keys()), index=0)
    user_offset = tz_options[selected_tz_label]
    st.info(f"日期：{get_user_date(user_offset)}")

rates = get_exchange_rates()

# 檢查固定收支
def check_and_run_recurring():
    if 'recurring_checked' in st.session_state:
        return 

    rec_df = get_data("Recurring", CURRENT_SHEET_SOURCE)
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
                # 假設預設幣別為 TWD，若要更精準可讀取 Settings
                amt_target, _ = calculate_exchange(amt_org, curr, "TWD", rates)
                
                tx_date = today.strftime("%Y-%m-%d")
                tx_row = [tx_date, row['Type'], row['Main_Category'], row['Sub_Category'], row['Payment_Method'], curr, amt_org, amt_target, f"(自動) {row['Note']}", str(datetime.now(sys_tz))]
                
                if append_data("Transactions", tx_row, CURRENT_SHEET_SOURCE):
                    update_recurring_last_run(idx, current_month_str, CURRENT_SHEET_SOURCE)
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
settings_df = get_data("Settings", CURRENT_SHEET_SOURCE)
cat_mapping = {}     
payment_list = []
currency_list_custom = []
default_currency_setting = "TWD" 

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
    
    if "Default_Currency" in settings_df.columns:
        saved_defaults = settings_df[settings_df["Default_Currency"] != ""]["Default_Currency"].unique().tolist()
        if saved_defaults:
            default_currency_setting = saved_defaults[0]

if not cat_mapping: 
    cat_mapping = {"收入": ["薪資"], "食": ["早餐"]}
elif "收入" not in cat_mapping:
    cat_mapping["收入"] = ["薪資"]

if not payment_list: payment_list = ["現金"]

if not currency_list_custom: 
    currency_list_custom = ["TWD"]

if default_currency_setting not in currency_list_custom:
    default_currency_setting = currency_list_custom[0]

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

    if 'form_currency' not in st.session_state: st.session_state.form_currency = default_currency_setting
    if 'form_amount_org' not in st.session_state: st.session_state.form_amount_org = 0.0
    if 'form_amount_sgd' not in st.session_state: st.session_state.form_amount_sgd = 0.0
    if 'form_note' not in st.session_state: st.session_state.form_note = ""

    def on_input_change():
        c = st.session_state.form_currency
        a = st.session_state.form_amount_org
        val, _ = calculate_exchange(a, c, default_currency_setting, rates)
        st.session_state.form_amount_sgd = val

    user_today = get_user_date(user_offset)
    current_month_str = user_today.strftime("%Y-%m")
    
    tx_df = get_data("Transactions", CURRENT_SHEET_SOURCE)

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
            
            try:
                curr_index = currency_list_custom.index(default_currency_setting)
            except ValueError:
                curr_index = 0
            
            with c5: currency = st.selectbox("幣別", currency_list_custom, index=curr_index, key="form_currency", on_change=on_input_change)
            with c6: amount_org = st.number_input(f"金額 ({currency})", step=1.0, key="form_amount_org", on_change=on_input_change)
            with c7: 
                amount_sgd = st.number_input(f"折合 {default_currency_setting}", step=0.1, key="form_amount_sgd")
                if currency != default_currency_setting and amount_org != 0:
                     _, rate_used = calculate_exchange(100, currency, default_currency_setting, rates)
                     if rate_used > 0: st.caption(f"匯率: {rate_used:.4f}")

        note = st.text_input("備註", max_chars=20, placeholder="輸入消費內容 (限20字)...", key="form_note")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("確認送出記帳", type="primary", use_container_width=True):
            if amount_sgd == 0:
                st.error("金額不能為 0")
            else:
                with st.spinner('📡 資料寫入中...'):
                    tx_type = "收入" if main_cat == "收入" else "支出"
                    sys_now = datetime.now()
                    row = [str(date_input), tx_type, main_cat, sub_cat, payment, currency, amount_org, amount_sgd, note, str(sys_now)]
                    
                    if append_data("Transactions", row, CURRENT_SHEET_SOURCE):
                        st.success(f"✅ {tx_type}已記錄 ${amount_sgd}！")
                        st.session_state['should_clear_input'] = True
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 寫入失敗")

# ================= Tab 2: 收支分析 =================
with tab2:
    st.markdown("##### 📊 收支狀況")
    df_tx = get_data("Transactions", CURRENT_SHEET_SOURCE)

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
    
    # 初始化暫存變數 (如果還沒有)
    if 'temp_cat_map' not in st.session_state: st.session_state.temp_cat_map = cat_mapping
    if 'temp_pay_list' not in st.session_state: st.session_state.temp_pay_list = payment_list
    if 'temp_curr_list' not in st.session_state: st.session_state.temp_curr_list = currency_list_custom
    if 'temp_default_curr' not in st.session_state: st.session_state.temp_default_curr = default_currency_setting

    # 1. 固定收支 (保持即時寫入)
    with st.expander("🔄 每月固定收支 (薪資、房租...)", expanded=True):
        with st.popover("➕ 新增固定規則", use_container_width=True):
            st.markdown("###### 設定每月自動執行的項目")
            if 'rec_currency' not in st.session_state: st.session_state.rec_currency = default_currency_setting
            if 'rec_amount_org' not in st.session_state: st.session_state.rec_amount_org = 0.0
            
            def on_rec_change():
                c = st.session_state.rec_currency
                a = st.session_state.rec_amount_org
                val, _ = calculate_exchange(a, c, default_currency_setting, rates)
                st.session_state.rec_amount_sgd = val

            rec_day = st.number_input("每月幾號執行?", min_value=1, max_value=31, value=5)
            c_rec1, c_rec2 = st.columns(2)
            with c_rec1: rec_main = st.selectbox("大類別", main_cat_list, key="rec_main")
            with c_rec2: rec_sub = st.selectbox("次類別", cat_mapping.get(rec_main, []), key="rec_sub")
            rec_pay = st.selectbox("付款方式", payment_list, key="rec_pay")
            c_r1, c_r2, c_r3 = st.columns([1.5, 2, 2])
            with c_r1: rec_curr = st.selectbox("幣別", currency_list_custom, index=curr_index if 'curr_index' in locals() else 0, key="rec_currency", on_change=on_rec_change)
            with c_r2: rec_amt_org = st.number_input("原幣金額", step=1.0, key="rec_amount_org", on_change=on_rec_change)
            with c_r3: rec_amt_sgd = st.number_input(f"折合 {default_currency_setting}", step=0.1, key="rec_amount_sgd")
            rec_note = st.text_input("備註 (例如: 房租)", key="rec_note")
            
            if st.button("儲存規則", type="primary", use_container_width=True):
                rec_type = "收入" if rec_main == "收入" else "支出"
                new_rule = [rec_day, rec_type, rec_main, rec_sub, rec_pay, rec_curr, rec_amt_org, rec_note, "New", "Active"]
                if append_data("Recurring", new_rule, CURRENT_SHEET_SOURCE):
                    st.success("✅ 規則已新增！")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")
        rec_df = get_data("Recurring", CURRENT_SHEET_SOURCE)
        if not rec_df.empty:
            for idx, row in rec_df.iterrows():
                header_txt = f"📅 每月 {row['Day']} 號 - {row['Main_Category']} > {row['Sub_Category']} > {row['Amount_Original']} {row['Currency']}"
                with st.expander(header_txt):
                    c_list1, c_list2 = st.columns([4, 1])
                    with c_list1:
                        st.write(f"📝 {row['Note']} | {row['Amount_Original']} {row['Currency']} ({row['Payment_Method']})")
                    with c_list2:
                        if st.button("🗑️ 刪除", key=f"del_rec_{idx}", type="primary"):
                            if delete_recurring_rule(idx, CURRENT_SHEET_SOURCE):
                                st.toast("規則已刪除")
                                st.cache_data.clear()
                                time.sleep(1)
                                st.rerun()
        else:
            st.info("目前沒有設定固定收支規則")

    # 2. 類別管理 (V15 批次修改模式 + Callback)
    st.info("💡 修改下方設定後，請務必點擊最底部的「儲存所有設定」按鈕")
    
    with st.expander("📂 類別與子類別管理"):
        with st.popover("➕ 新增大類", use_container_width=True):
            new_main = st.text_input("類別名稱", placeholder="例如: 醫療", label_visibility="collapsed")
            if st.button("確認新增", type="primary", use_container_width=True):
                if new_main and new_main not in st.session_state.temp_cat_map:
                    st.session_state.temp_cat_map[new_main] = []
                    # 這裡只更新 session state，不寫入 DB，不 rerun
                    st.toast(f"已暫存類別：{new_main}")
                    
        for idx, main in enumerate(st.session_state.temp_cat_map.keys()):
            with st.container():
                with st.expander(f"📁 {main}", expanded=False):
                    # 顯示子類別 (Multiselect 移除)
                    current_subs = st.session_state.temp_cat_map[main]
                    updated_subs = st.multiselect("子類", current_subs, default=current_subs, key=f"ms_{main}", on_change=lambda m=main, k=f"ms_{main}": st.session_state.temp_cat_map.update({m: st.session_state[k]}))
                    
                    cs1, cs2 = st.columns([3, 1])
                    sub_key = f"new_sub_val_{main}" # [修正] 使用類別名稱當 Key
                    if sub_key not in st.session_state: st.session_state[sub_key] = ""
                    
                    with cs1: 
                        st.text_input("add", key=sub_key, label_visibility="collapsed", placeholder="新增子類別...")
                    with cs2: 
                        # [關鍵修改] 使用 on_click Callback
                        st.button("加入", key=f"bns_{main}", on_click=add_sub_callback, args=(main, sub_key))
                            
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"🗑️ 刪除 {main}", key=f"dm_{main}", type="secondary", use_container_width=True):
                        del st.session_state.temp_cat_map[main]
                        st.rerun() # 刪除大類比較重大，直接 rerun 刷新畫面比較好

    # 3. 其他設定 (V15 批次修改模式 + Callback)
    with st.expander("💳 付款與幣別"):
        st.subheader("付款方式")
        pays = st.session_state.temp_pay_list
        # Multiselect 綁定 callback
        u_pays = st.multiselect("付款", pays, default=pays, key="mp_pay", on_change=lambda: st.session_state.update(temp_pay_list=st.session_state.mp_pay))
        
        c_p1, c_p2 = st.columns([3,1])
        with c_p1: 
            st.text_input("np", key="new_pay_val", label_visibility="collapsed", placeholder="新增付款方式")
        with c_p2: 
            # [關鍵修改] 使用 on_click Callback
            st.button("加入", key="bp", on_click=add_pay_callback, args=("new_pay_val",))
        
        st.divider()
        st.subheader("常用幣別")
        curs = st.session_state.temp_curr_list
        u_curs = st.multiselect("幣別", curs, default=curs, key="mp_cur", on_change=lambda: st.session_state.update(temp_curr_list=st.session_state.mp_cur))
        
        c_c1, c_c2 = st.columns([3,1])
        with c_c1: 
            st.text_input("nc", key="new_curr_val", label_visibility="collapsed", placeholder="新增幣別")
        with c_c2:
            # [關鍵修改] 使用 on_click Callback
            st.button("加入", key="bc", on_click=add_curr_callback, args=("new_curr_val",))
                    
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("✨ 設定每日記帳的預設幣別：")
        
        try:
            def_idx = st.session_state.temp_curr_list.index(st.session_state.temp_default_curr)
        except ValueError:
            def_idx = 0
            
        new_def_curr = st.selectbox(
            "選擇預設幣別", 
            st.session_state.temp_curr_list, 
            index=def_idx, 
            key="sel_def_curr",
            label_visibility="collapsed"
        )
        if new_def_curr != st.session_state.temp_default_curr:
            st.session_state.temp_default_curr = new_def_curr

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 儲存所有設定", type="primary", use_container_width=True):
        save_all_to_sheet()
        st.rerun()
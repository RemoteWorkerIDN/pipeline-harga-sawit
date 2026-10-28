import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def get_investing_price(commodity_type):
    """
    Mengambil harga komoditas terkini menggunakan HTTP Request (Scraping Ringan)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        if commodity_type == "OIL":
            # Data Minyak WTI
            url = "https://api.investing.com/api/financialdata/assets/equities/8849/historical-data" 
            # Alternatif parsing langsung dari endpoint open API komoditas
            res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/CL=F", headers=headers, timeout=10)
            data = res.json()
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return round(float(price), 2)
            
        elif commodity_type == "CPO":
            # Ambil data CPO dari Bursa Malaysia / Trading Economics API public
            res = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/FCPO=F", headers=headers, timeout=10)
            data = res.json()
            price = data['chart']['result'][0]['meta']['regularMarketPrice']
            return round(float(price), 2)
            
    except Exception as e:
        print(f"Gagal mengambil {commodity_type}: {e}")
    return "N/A"

def fetch_historical_backup():
    """Generasi data historis langsung menggunakan endpoint chart JSON"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # Ambil data riwayat WTI Oil 1 Tahun
    url_oil = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F?range=1y&interval=1d"
    res_oil = requests.get(url_oil, headers=headers).json()
    timestamps = res_oil['chart']['result'][0]['timestamp']
    prices_oil = res_oil['chart']['result'][0]['indicators']['quote'][0]['close']
    
    dates = [datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') for ts in timestamps]
    
    df_oil = pd.DataFrame({'Tanggal': dates, 'Crude Oil': prices_oil})
    df_oil = df_oil.dropna()
    
    # Ambil data riwayat CPO 1 Tahun
    url_cpo = "https://query1.finance.yahoo.com/v8/finance/chart/FCPO=F?range=1y&interval=1d"
    res_cpo = requests.get(url_cpo, headers=headers).json()
    
    try:
        ts_cpo = res_cpo['chart']['result'][0]['timestamp']
        prices_cpo = res_cpo['chart']['result'][0]['indicators']['quote'][0]['close']
        dates_cpo = [datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d') for ts in ts_cpo]
        df_cpo = pd.DataFrame({'Tanggal': dates_cpo, 'CPO': prices_cpo}).dropna()
    except:
        df_cpo = pd.DataFrame(columns=['Tanggal', 'CPO'])

    # Gabungkan Data
    combined = pd.merge(df_oil, df_cpo, on='Tanggal', how='left').ffill().bfill()
    return combined

def run_pipeline():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_json = os.environ.get("GCP_SA_KEY")
    if not creds_json:
        raise ValueError("GCP_SA_KEY tidak ditemukan!")
        
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    try:
        spreadsheet = client.open("Data_Komoditas")
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheets = client.openall()
        spreadsheet = [s for s in spreadsheets if s.title == "Data_Komoditas"][0]

    sheet = spreadsheet.sheet1
    all_values = sheet.get_all_values()
    valid_rows = [r for r in all_values if len(r) > 0 and r[0].strip() != ""]

    # Jika Sheet Masih Kosong -> Tarik Historis 1 Tahun
    if len(valid_rows) <= 2:
        print("Mulai unduh historis via Direct Web Endpoint...")
        df_hist = fetch_historical_backup()
        
        rows_to_insert = [["Tanggal", "CPO", "Crude Oil"]]
        for _, row in df_hist.iterrows():
            cpo_val = round(float(row['CPO']), 2) if pd.notna(row['CPO']) else "N/A"
            oil_val = round(float(row['Crude Oil']), 2) if pd.notna(row['Crude Oil']) else "N/A"
            rows_to_insert.append([row['Tanggal'], cpo_val, oil_val])
            
        sheet.clear()
        sheet.update(values=rows_to_insert, range_name="A1")
        print(f"Berhasil mengisi {len(rows_to_insert)-1} baris data historis!")

    # Jika Sudah Ada Data -> Update Harian
    else:
        print("Melakukan update harian...")
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        
        cpo_price = get_investing_price("CPO")
        oil_price = get_investing_price("OIL")
        
        last_date = valid_rows[-1][0]
        row_data = [today_str, cpo_price, oil_price]

        if last_date == today_str:
            row_idx = len(valid_rows)
            sheet.update(values=[row_data], range_name=f"A{row_idx}:C{row_idx}")
            print(f"Update baris tanggal {today_str}: {row_data}")
        else:
            sheet.append_row(row_data)
            print(f"Tambah baris baru {today_str}: {row_data}")

if __name__ == "__main__":
    run_pipeline()

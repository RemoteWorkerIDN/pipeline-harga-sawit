import os
import json
import datetime
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

def get_commodity_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="7d")
        if not hist.empty:
            # Mengambil harga penutupan terakhir yang valid
            valid_closes = hist['Close'].dropna()
            if not valid_closes.empty:
                return float(valid_closes.iloc[-1])
    except Exception as e:
        print(f"Gagal mengambil {ticker_symbol}: {e}")
    return None

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

    # Buka Google Sheet
    try:
        spreadsheet = client.open("Data_Komoditas")
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheets = client.openall()
        spreadsheet = [s for s in spreadsheets if s.title == "Data_Komoditas"][0]

    sheet = spreadsheet.sheet1
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # 1. Ambil Harga CPO (Coba FCPO=F bursa Malaysia, jika gagal pakai cadangan)
    cpo_price = get_commodity_price("FCPO=F")
    if cpo_price is None:
        cpo_price = get_commodity_price("PALMOIL.KL")

    # 2. Ambil Harga Crude Oil (WTI)
    oil_price = get_commodity_price("CL=F")

    # Format baris baru
    row_data = [
        today_str,
        round(cpo_price, 2) if cpo_price else "N/A",
        round(oil_price, 2) if oil_price else "N/A"
    ]

    # Cek agar tidak menulis baris ganda di hari yang sama
    records = sheet.get_all_values()
    last_date = records[-1][0] if len(records) > 1 else ""

    if last_date == today_str:
        # Update baris terakhir jika hari ini sudah pernah diisi
        row_idx = len(records)
        sheet.update(f"A{row_idx}:C{row_idx}", [row_data])
        print(f"Memperbarui data tanggal {today_str}: {row_data}")
    else:
        # Tambah baris baru jika tanggal baru
        sheet.append_row(row_data)
        print(f"Berhasil menambahkan data tanggal {today_str}: {row_data}")

if __name__ == "__main__":
    run_pipeline()

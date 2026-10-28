import os
import json
import datetime
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

def get_commodity_history(ticker_symbol, period="1y"):
    """Mengambil riwayat data harga penutupan komoditas"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)
        if not hist.empty and 'Close' in hist:
            df = hist[['Close']].copy()
            df.index = df.index.strftime('%Y-%m-%d')
            return df
    except Exception as e:
        print(f"Gagal mengambil riwayat {ticker_symbol}: {e}")
    return pd.DataFrame()

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
    existing_records = sheet.get_all_values()

    # CEK PERTAMA: Jika Sheet masih kosong (hanya ada Header / < 2 baris)
    if len(existing_records) <= 2:
        print("Sheet masih kosong. Memulai proses download data historis (1 Tahun)...")
        
        # Tarik data historis 1 tahun untuk Oil & CPO
        oil_df = get_commodity_history("CL=F", period="1y")
        cpo_df = get_commodity_history("FCPO=F", period="1y")
        
        if cpo_df.empty:
            cpo_df = get_commodity_history("PALMOIL.KL", period="1y")

        # Gabungkan data berdasarkan tanggal
        combined = pd.merge(cpo_df, oil_df, left_index=True, right_index=True, how='outer', suffixes=('_CPO', '_OIL'))
        combined = combined.sort_index().ffill().bfill()  # Isi nilai kosong
        
        # Susun format data baris
        rows_to_insert = [["Tanggal", "CPO", "Crude Oil"]]
        for date_str, row in combined.iterrows():
            cpo_val = round(float(row.iloc[0]), 2) if not pd.isna(row.iloc[0]) else "N/A"
            oil_val = round(float(row.iloc[1]), 2) if not pd.isna(row.iloc[1]) else "N/A"
            rows_to_insert.append([date_str, cpo_val, oil_val])
        
        sheet.clear()
        sheet.update("A1", rows_to_insert)
        print(f"Berhasil mengunggah {len(rows_to_insert)-1} baris data historis!")

    # CEK KEDUA: Jika data historis sudah ada, lakukan Update Harian
    else:
        print("Data historis ditemukan. Memproses update harian...")
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        
        oil_recent = get_commodity_history("CL=F", period="5d")
        cpo_recent = get_commodity_history("FCPO=F", period="5d")
        if cpo_recent.empty:
            cpo_recent = get_commodity_history("PALMOIL.KL", period="5d")

        cpo_price = round(float(cpo_recent['Close'].iloc[-1]), 2) if not cpo_recent.empty else "N/A"
        oil_price = round(float(oil_recent['Close'].iloc[-1]), 2) if not oil_recent.empty else "N/A"

        last_date = existing_records[-1][0]
        row_data = [today_str, cpo_price, oil_price]

        if last_date == today_str:
            row_idx = len(existing_records)
            sheet.update(f"A{row_idx}:C{row_idx}", [row_data])
            print(f"Update baris tanggal {today_str}: {row_data}")
        else:
            sheet.append_row(row_data)
            print(f"Tambah baris baru {today_str}: {row_data}")

if __name__ == "__main__":
    run_pipeline()

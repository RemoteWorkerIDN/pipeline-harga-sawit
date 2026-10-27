import os
import json
import datetime
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

def run_pipeline():
    # 1. Autentikasi ke Google Sheets menggunakan Secret/Credentials
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Membaca credentials dari environment variable (keamanan di GitHub Actions)
    creds_json = os.environ.get("GCP_SA_KEY")
    if not creds_json:
        raise ValueError("GCP_SA_KEY tidak ditemukan di Environment Variables!")
        
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)

    # Buka Google Sheet berdasarkan nama file
    spreadsheet = client.open("Data_Komoditas")
    sheet = spreadsheet.sheet1

    # 2. Ambil Data Komoditas via yfinance
    # Ticker: FCPO=F (CPO Malaysia) & CL=F (Minyak Dunia WTI)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    cpo_ticker = yf.Ticker("FCPO=F")
    cpo_hist = cpo_ticker.history(period="5d")
    cpo_price = float(cpo_hist['Close'].iloc[-1]) if not cpo_hist.empty else None

    oil_ticker = yf.Ticker("CL=F")
    oil_hist = oil_ticker.history(period="5d")
    oil_price = float(oil_hist['Close'].iloc[-1]) if not oil_hist.empty else None

    # 3. Format Baris Data Baru
    row_data = [
        today_str,
        round(cpo_price, 2) if cpo_price else "N/A",
        round(oil_price, 2) if oil_price else "N/A"
    ]

    # 4. Tambahkan ke Google Sheets (Append)
    sheet.append_row(row_data)
    print(f"Berhasil menambahkan data tanggal {today_str}: {row_data}")

if __name__ == "__main__":
    run_pipeline()

import os
import json
import datetime
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

def run_pipeline():
    # Autentikasi
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(json.loads(os.environ.get("GCP_SA_KEY")), scopes=scopes)
    client = gspread.authorize(creds)
    
    # Buka Google Sheet
    sheet = client.open("Data_Komoditas").sheet1
    all_values = sheet.get_all_values()
    
    # Deteksi baris yang benar-benar berisi data
    valid_rows = [r for r in all_values if len(r) > 0 and str(r[0]).strip() != ""]
    
    # KONDISI 1: TARIK HISTORIS 1 TAHUN (Jika data kurang dari 5 baris)
    if len(valid_rows) < 5:
        print("Sheet Kosong. Mengunduh data historis 1 tahun...")
        oil = yf.Ticker("CL=F").history(period="1y")['Close']
        cpo = yf.Ticker("FCPO=F").history(period="1y")['Close']
        
        # Fallback (cadangan) jika ticker CPO Malaysia kosong
        if cpo.empty:
            cpo = yf.Ticker("PALMOIL.KL").history(period="1y")['Close']
            
        df = pd.DataFrame({'CPO': cpo, 'Crude Oil': oil})
        df.index = df.index.strftime('%Y-%m-%d')
        df = df.ffill().bfill().dropna() # Bersihkan data kosong
        
        rows = [["Tanggal", "CPO", "Crude Oil"]]
        for date_str, row in df.iterrows():
            rows.append([date_str, round(row['CPO'], 2), round(row['Crude Oil'], 2)])
            
        sheet.clear()
        sheet.update(values=rows, range_name="A1")
        print(f"Sukses! {len(rows)-1} baris historis tersimpan.")
        
    # KONDISI 2: UPDATE HARIAN (Hanya dijalankan jika data historis sudah ada)
    else:
        print("Data historis ditemukan. Memproses update harian...")
        today = datetime.date.today().strftime("%Y-%m-%d")
        
        oil_price = yf.Ticker("CL=F").history(period="5d")['Close'].iloc[-1]
        cpo_data = yf.Ticker("FCPO=F").history(period="5d")
        if cpo_data.empty:
            cpo_data = yf.Ticker("PALMOIL.KL").history(period="5d")
            
        cpo_price = cpo_data['Close'].iloc[-1] if not cpo_data.empty else "N/A"
        row_data = [today, round(float(cpo_price), 2) if cpo_price != "N/A" else "N/A", round(float(oil_price), 2)]
        
        last_date = valid_rows[-1][0]
        if last_date == today:
            sheet.update(values=[row_data], range_name=f"A{len(valid_rows)}:C{len(valid_rows)}")
        else:
            sheet.append_row(row_data)

if __name__ == "__main__":
    run_pipeline()

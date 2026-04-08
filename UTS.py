import streamlit as st
import pandas as pd
import sqlite3
from hashlib import sha256
from pathlib import Path

st.set_page_config(page_title="Dashboard Keuangan", layout="wide")

# ================= DB SETUP (FIXED & STABLE) =================
DB_PATH = Path(__file__).parent / "keuangan.db"

# Buat koneksi dan cursor DI AWAL (hindari error 'c not defined')
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    return conn

conn = get_connection()
c = conn.cursor()

# Pastikan tabel dibuat setelah cursor tersedia
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS transaksi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    tanggal TEXT,
    jenis TEXT,
    jumlah INTEGER
)
""")
conn.commit()

# ================= HELPER =================
def hash_password(pw: str) -> str:
    return sha256(pw.encode()).hexdigest()


def format_rupiah(x):
    try:
        return f"Rp {int(x):,}".replace(",", ".")
    except Exception:
        return "Rp 0"

# ================= SESSION =================
if "login" not in st.session_state:
    st.session_state.login = False
if "user" not in st.session_state:
    st.session_state.user = None

# ================= LOGIN / REGISTER =================
if not st.session_state.login:
    st.title("🔐 Login / Register")
    menu = st.selectbox("Pilih", ["Login", "Register"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if menu == "Register":
        if st.button("Daftar"):
            if not username or not password:
                st.error("Isi username dan password")
            else:
                c.execute("SELECT 1 FROM users WHERE username=?", (username,))
                if c.fetchone():
                    st.error("Username sudah ada")
                else:
                    c.execute("INSERT INTO users VALUES (?,?)", (username, hash_password(password)))
                    conn.commit()
                    st.success("Registrasi berhasil")

    if menu == "Login":
        if st.button("Login"):
            c.execute("SELECT 1 FROM users WHERE username=? AND password=?",
                      (username, hash_password(password)))
            if c.fetchone():
                st.session_state.login = True
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Login gagal")

    st.stop()

# ================= DASHBOARD =================
st.title(f"📊 Dashboard Keuangan - {st.session_state.user}")

# ================= INPUT =================
st.subheader("➕ Tambah Transaksi")
col1, col2, col3 = st.columns(3)

with col1:
    tanggal = st.date_input("Tanggal")
with col2:
    jenis = st.selectbox("Jenis", ["Pemasukan", "Pengeluaran"])
with col3:
    jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000)

if st.button("Simpan"):
    if jumlah <= 0:
        st.error("Jumlah harus > 0")
    else:
        c.execute("INSERT INTO transaksi (username, tanggal, jenis, jumlah) VALUES (?,?,?,?)",
                  (st.session_state.user, str(tanggal), jenis, int(jumlah)))
        conn.commit()
        st.success("Tersimpan")
        st.rerun()

# ================= LOAD DATA =================
df = pd.read_sql_query(
    "SELECT id, tanggal, jenis, jumlah FROM transaksi WHERE username=? ORDER BY id DESC",
    conn, params=(st.session_state.user,)
)

if not df.empty:
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")

    # ================= HAPUS =================
    st.subheader("🗑️ Hapus Transaksi")
    pilih_id = st.selectbox("Pilih ID", df["id"].tolist())

    if st.button("Hapus"):
        c.execute("DELETE FROM transaksi WHERE id=? AND username=?",
                  (int(pilih_id), st.session_state.user))
        conn.commit()
        st.success("Terhapus")
        st.rerun()

    # ================= TABEL =================
    st.subheader("📋 Data")
    df_display = df.copy()
    df_display["jumlah"] = df_display["jumlah"].apply(format_rupiah)
    st.dataframe(df_display)

    # ================= RINGKASAN =================
    masuk = df[df["jenis"] == "Pemasukan"]["jumlah"].sum()
    keluar = df[df["jenis"] == "Pengeluaran"]["jumlah"].sum()

    st.subheader("📈 Ringkasan")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pemasukan", format_rupiah(masuk))
    c2.metric("Pengeluaran", format_rupiah(keluar))
    c3.metric("Saldo", format_rupiah(masuk - keluar))

    # ================= MINGGUAN =================
    st.subheader("📅 Mingguan")
    df["Minggu"] = df["tanggal"].dt.to_period("W").apply(lambda r: r.start_time)
    df["jumlah"] = pd.to_numeric(df["jumlah"], errors="coerce").fillna(0)
    mingguan = df.groupby(["Minggu", "jenis"]) ["jumlah"].sum().unstack().fillna(0)
    mingguan["Saldo"] = mingguan.get("Pemasukan", 0) - mingguan.get("Pengeluaran", 0)

    mingguan_display = mingguan.copy()

    for col in mingguan_display.columns:
           mingguan_display[col] = mingguan_display[col].apply(format_rupiah)

    st.dataframe(mingguan_display)

    # ================= BULANAN =================
    st.subheader("📆 Bulanan")
    df["Bulan"] = df["tanggal"].dt.to_period("M")
    df["jumlah"] = pd.to_numeric(df["jumlah"], errors="coerce").fillna(0)
    bulanan = df.groupby(["Bulan", "jenis"]) ["jumlah"].sum().unstack().fillna(0)
    bulanan["Saldo"] = bulanan.get("Pemasukan", 0) - bulanan.get("Pengeluaran", 0)

    bulanan_display = bulanan.copy()

    for col in bulanan_display.columns:
        bulanan_display[col] = bulanan_display[col].apply(format_rupiah)

    st.dataframe(bulanan_display)

else:
    st.info("Belum ada data")

# ================= LOGOUT =================
if st.button("Logout"):
    st.session_state.login = False
    st.session_state.user = None
    st.rerun()

st.write("---")
st.write("Database aktif:", DB_PATH)

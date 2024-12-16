from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from Crypto.Cipher import AES
import base64
import qrcode
from io import BytesIO
from datetime import datetime
import os

app = Flask(__name__)

# Konfigurasi Database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "tiket_konser.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Kunci enkripsi (16, 24, atau 32 byte)
SECRET_KEY = b'SixteenByteKey!!'

# Model Database
class Tiket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    no_hp = db.Column(db.String(15), nullable=False)
    tempat_duduk = db.Column(db.String(10), nullable=False)
    jumlah_tiket = db.Column(db.Integer, nullable=False)
    id_tiket = db.Column(db.String(50), unique=True, nullable=False)
    tanggal_pesan = db.Column(db.DateTime, default=datetime.utcnow)
    qr_code = db.Column(db.Text, nullable=False)

# Fungsi padding dan unpadding AES
def pad(data):
    pad_length = 16 - (len(data) % 16)
    return data + (chr(pad_length) * pad_length)

def unpad(data):
    return data[:-ord(data[-1])]

# Fungsi enkripsi dan dekripsi
def encrypt_data(data):
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data).encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_data(data):
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    decrypted = cipher.decrypt(base64.b64decode(data))
    return unpad(decrypted.decode('utf-8'))

# Fungsi untuk membuat ID tiket dengan format khusus
def generate_ticket_id():
    urutan = Tiket.query.count() + 1  # Pelanggan selanjutnya berdasarkan jumlah tiket yang ada
    tanggal = datetime.now().strftime('%Y%m%d')
    return f"TKT{urutan:04d}{tanggal}"

# Route untuk halaman utama
@app.route('/')
def home():
    return render_template('index.html')

# Route untuk generate QR code
@app.route('/generate', methods=['POST'])
def generate_qr():
    try:
        # Ambil data dari form
        nama = request.form.get('nama', '').strip()
        email = request.form.get('email', '').strip()
        no_hp = request.form.get('no_hp', '').strip()
        tempat_duduk = request.form.get('tempat_duduk', '').strip()
        jumlah_tiket = int(request.form.get('jumlah_tiket', '1'))

        if not nama or not email or not no_hp or not tempat_duduk or jumlah_tiket < 1:
            return jsonify({'status': 'error', 'message': 'Semua field harus diisi dengan benar'}), 400

        tiket_list = []
        tanggal_pesan = datetime.utcnow()
        for i in range(1, jumlah_tiket + 1):
            # Generate ID Tiket dengan format TKTurutanTanggal
            id_tiket = generate_ticket_id()

            # Enkripsi ID Tiket
            encrypted_data = encrypt_data(id_tiket)

            # Generate QR Code
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(encrypted_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            # Simpan ke Database
            tiket = Tiket(
                nama=nama,
                email=email,
                no_hp=no_hp,
                tempat_duduk=tempat_duduk,
                jumlah_tiket=1,  # Set jumlah tiket per iterasi
                id_tiket=id_tiket,
                qr_code=qr_base64
            )
            db.session.add(tiket)
            tiket_list.append({
                'id_tiket': id_tiket,
                'ciphertext': encrypted_data,
                'qr_image': qr_base64
            })
        db.session.commit()

        return jsonify({'status': 'success', 'tickets': tiket_list})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Route untuk decrypt QR code
@app.route('/decrypt', methods=['POST'])
def decrypt_qr():
    encrypted_data = request.form.get('encrypted_data', '').strip()
    if not encrypted_data:
        return jsonify({'status': 'error', 'message': 'Data terenkripsi tidak boleh kosong'}), 400

    try:
        decrypted_data = decrypt_data(encrypted_data)
        tiket = Tiket.query.filter_by(id_tiket=decrypted_data).first()
        if not tiket:
            return jsonify({'status': 'error', 'message': 'Tiket tidak ditemukan'}), 404

        return jsonify({
            'status': 'success',
            'ciphertext': encrypted_data,
            'decrypted_data': decrypted_data,
            'ticket_data': {
                'nama': tiket.nama,
                'email': tiket.email,
                'no_hp': tiket.no_hp,
                'tempat_duduk': tiket.tempat_duduk,
                'jumlah_tiket': tiket.jumlah_tiket,
                'tanggal_pesan': tiket.tanggal_pesan.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Dekripsi gagal: ' + str(e)}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

## VI Library - Kullanim Kilavuzu

Bu proje UCE-CTL321L Component Tester cihazına veri tabanı özelliği kazandırmak için oluşturulmuştur. UCE-CTL321L chiazının ürettiği ekran görüntüleri temizlenerek grafik bilgisi ve ölçüm değerleri sayısal hale getirilir. Üretilen değerler Elektrünik Kart görseli üzerinde işaretlenen test point noktalarına atanarak veri tabanına kayıt edilir. Test aşamasında cihazın ürettiği test sonuçları ile veri tabanındaki kayıtlar karşılaştırılarak arıza kontrolü yapılır.

## Gereksinimler

1. Python 3.10+
2. Tesseract OCR motoru (pytesseract icin zorunlu)
3. Sanal ortam (onerilir)

Linux icin ornek Tesseract kurulumu:

```bash
sudo apt update
sudo apt install -y tesseract-ocr
```

Windows icin ornek Tesseract kurulumu (PowerShell):

```powershell
winget install UB-Mannheim.TesseractOCR
```

Alternatif olarak Tesseract'i manuel kurabilirsiniz.

## Kurulum

1. Sanal ortami olusturun ve aktive edin:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Bagimliliklari yukleyin:

```bash
pip install -r requirements.txt
```

Windows icin de ayni komut gecerlidir.

3. Ilk kullanimda admin hesabi olusturun:

```bash
python run.py create-admin --username admin --password sifreniz
```

Tesseract PATH'te degilse (ozellikle Windows), calistirmadan once komut yolunu tanimlayin:

Linux/macOS:

```bash
export TESSERACT_CMD=/usr/bin/tesseract
```

Windows (PowerShell):

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## Uygulamayi Baslatma

Standart calistirma:

```bash
python run.py
```

Windows'ta da ayni komut kullanilir.

Uygulama varsayilan olarak 0.0.0.0:8086 uzerinden dinler.

Farkli host/port ile:

```bash
python run.py --host 0.0.0.0 --port 8086
```

Gelistirme modunda otomatik yeniden yukleme ile:

```bash
python run.py --reload
```

Not: Bu proje FastAPI ile calisir. python backend/manage.py runserver komutu bu proje icin kullanilmamalidir.

## Hizli Baslatma Ozeti

Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py create-admin --username admin --password sifreniz
python run.py
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py create-admin --username admin --password sifreniz
python run.py
```

## Temel Kullanim Akisi

1. Tarayicida /login sayfasina gidin ve giris yapin.
2. Ust bardan Kütüphane sayfasini acin.
3. Yeni test eklemek icin:
	- Test ismi girin.
	- Kart fotografi secin.
	- Kart uzerine cift tiklayarak marker ekleyin.
	- Marker adini/aciklamasini duzenleyin.
	- Her nokta icin TP gorseli yukleyin (OCR verisi otomatik cikartilir).
	- GND noktasini (opsiyonel): Test noktasi tablosunda "Ayarla" butonuna tiklayarak GND noktesini tanimlayabilirsiniz. Iki probe'li test cihazlarinda bir probe sabit GND noktasinda tutulur, diger probe ise test noktalarindan gecmek icin kullanilir. Sadece bir nokta GND olabilir.
	- Kaydet butonuna basin.
4. Mevcut test guncellemek icin:
	- Kayitli testi listeden secin.
	- Gerekli alanlari duzenleyin.
	- Kart fotografini degistirmek istemiyorsaniz tekrar secmek zorunda degilsiniz.
	- Yeni eklenen noktalarda TP gorseli zorunludur.
	- Kaydet butonuna basin.

## Yetki ve Sayfa Eristimi

- /library: sadece admin
- /setup: sadece admin
- /: giris yapmis kullanicilar
- /login: herkese acik

Ust bar butonlari:

- VI Library logosu ana sayfaya goturur
- Kütüphane
- Yonetim
- Cikis

## Login ve Cikis

- Login sayfasi: /login
- Oturum yoksa / istegi otomatik olarak /login sayfasina yonlendirilir
- Cikis: /logout

## Veritabani Ozeti

- tests: test adi, aciklama, kart fotografi (BLOB), olusturan kullanici
- testpoints: nokta adi, aciklama, koordinat, olcum alanlari (v, f, r, tol, grafik)
- users: kullanici ve rol bilgileri
- audit_logs: islem loglari

## API Uclari

Kullanici/Yonetim:

- GET /users (admin)
- POST /users (admin)
- DELETE /users/{username} (admin)
- POST /users/{username}/password (kendi hesabi veya admin)
- GET /logs?limit=100 (admin)

Kutuphane:

- GET /api/library/tests
- GET /api/library/tests/{test_id}
- POST /api/library/tests (yeni test)
- PUT /api/library/tests/{test_id} (test guncelleme)
- POST /api/library/tests/{test_id} (guncelleme fallback)
- POST /api/library/process-testpoint-image
- POST /api/library/testpoints/{testpoint_id}/grafik-gorsel

## Sistem Acilisinda Otomatik Baslatma

Bu bolumde uygulamanin Linux ve Windows ortamlarda bilgisayar acilisinda otomatik baslamasi icin gerekli ayarlar yer alir.

### Linux (systemd)

1. Servis dosyasi olusturun:

```bash
sudo nano /etc/systemd/system/vilib.service
```

2. Icerige asagidakini yazin (yol ve kullanici adini kendi ortaminiza gore duzenleyin):

```ini
[Unit]
Description=VI Library FastAPI Service
After=network.target

[Service]
Type=simple
User=ubntlnx
WorkingDirectory=/home/ubntlnx/MyWorks/Codes/Django/vilibprj/vilib
Environment="TESSERACT_CMD=/usr/bin/tesseract"
ExecStart=/home/ubntlnx/MyWorks/Codes/Django/vilibprj/vilib/.venv/bin/python run.py --host 0.0.0.0 --port 8086
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

3. Servisi etkinlestirin ve baslatin:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vilib.service
sudo systemctl start vilib.service
```

4. Durum kontrolu:

```bash
sudo systemctl status vilib.service
journalctl -u vilib.service -f
```

### Windows (Task Scheduler)

1. Gorev Zamanlayici acin (`taskschd.msc`).
2. `Create Task` secin.
3. `General` sekmesi:
	- Name: `VI Library`
	- `Run whether user is logged on or not`
	- `Run with highest privileges`
4. `Triggers` sekmesi:
	- `New` -> `At startup`
5. `Actions` sekmesi:
	- `New` -> `Start a program`
	- Program/script:

```text
C:\path\to\project\.venv\Scripts\python.exe
```

	- Add arguments:

```text
run.py --host 0.0.0.0 --port 8086
```

	- Start in:

```text
C:\path\to\project
```

6. `Conditions` sekmesinde gerekirse `Start the task only if the computer is on AC power` secenegini kaldirin.
7. Gorevi kaydedin.

PowerShell ile ayni gorevi komutla olusturmak isterseniz:

```powershell
$python = "C:\path\to\project\.venv\Scripts\python.exe"
$workdir = "C:\path\to\project"
$action = New-ScheduledTaskAction -Execute $python -Argument "run.py --host 0.0.0.0 --port 8086" -WorkingDirectory $workdir
$trigger = New-ScheduledTaskTrigger -AtStartup
Register-ScheduledTask -TaskName "VI Library" -Action $action -Trigger $trigger -Description "VI Library FastAPI autostart"
```

Windows ortami icin Tesseract yolunu kalici tanimlamak isterseniz (yonetici PowerShell):

```powershell
[Environment]::SetEnvironmentVariable("TESSERACT_CMD", "C:\Program Files\Tesseract-OCR\tesseract.exe", "Machine")
```

## Sorun Giderme

- OCR sonucunda veri cikmiyorsa Tesseract kurulumunu kontrol edin.
- Guncelleme isteginde 405 hatasi alirsaniz uygulamayi yeniden baslatin.
- Yeni bir test kaydinda kart fotografi zorunludur.
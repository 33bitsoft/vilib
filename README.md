Motor Gereksinimi: Pytesseract'in çalışması için sistemde Tesseract OCR motorunun kurulu olması gerekir.

Kullanıcı bilgileri SQLite veritabanı dosyasında saklanır: vilib.db

## Baslangic

1. İlk kullanımda admin hesabı oluşturun:

python run.py create-admin --username admin --password sifreniz

2. Uygulamayı başlatın:

python run.py

Varsayılan olarak uygulama artik 0.0.0.0:8086 adresinde dinler ve ayni agdaki baska cihazlardan da erisilebilir.
Farkli host/port icin:

python run.py --host 0.0.0.0 --port 8086

3. Tarayıcıda önce giriş sayfası açılır. Admin bilgilerinizle giriş yapınca ana sayfaya yönlendirilirsiniz.

## Çalıştırma Notu

- Bu proje FastAPI ile çalışır.
- Uygulamayı başlatmak için kullanılacak komut: python run.py
- Django komutu (python backend/manage.py runserver ...) bu proje için geçersizdir ve sayfa/routing davranışını bozabilir.

## Login ve Çıkış Akışı

- Login sayfası: /login
- Oturum yoksa ana sayfa (/) otomatik olarak /login sayfasına yönlendirir.
- Ana sayfadaki Çıkış butonu /logout üzerinden oturumu kapatır ve tekrar /login sayfasına yönlendirir.

## Üst Bar (Ana Sayfa)

- Ana sayfada top bar içinde şu butonlar bulunur: Kütüphane, Ana Sayfa, Yönetim, Çıkış.
- Tüm sayfalar Bootstrap responsive yerleşim ile mobil uyumludur.

## Kütüphane (VI Component Tester)

- Sayfa: /library
- Kayıtlı test verileri listelenir.
- Yeni test oluşturma:
	- Test ismi girilir.
	- Test için açıklama girilebilir.
	- Elektronik kart fotoğrafı yüklenir.
	- Fotoğraf üzerinde zoom kullanılabilir.
	- Tıklanan noktalara görünür + işareti konur ve koordinatlar kaydedilir.
	- Nokta isimleri varsayılan olarak TP1, TP2 ... şeklinde gelir ve değiştirilebilir.
	- Her test point için ayrı test point görseli yüklenir.
	- image_process.py modülü ile test point görselinden otomatik olarak v, f, r, tol ve grafik verisi çıkarılır.
	- Çıkarılan grafik verisi gerektiğinde yine image_process.py modülü ile görsele dönüştürülür.

## Veritabanı Tabloları (Kütüphane)

- tests: test adı, açıklama ve kart fotoğrafı (BLOB) bilgisi.
- testpoints: test nokta adı, açıklama, koordinatlar ve ölçüm alanları (v, f, r, tol, grafik).

## Kullanıcı Yönetimi

- Admin girişi ile setup sayfasında yeni kullanıcı ekleme/silme işlemleri yapılabilir.
- Tüm kullanıcılar kendi şifresini değiştirebilir.
- Admin kullanıcı, hedef kullanıcı adını girerek diğer kullanıcıların şifresini de değiştirebilir.

## Loglama

- İşlem logları SQLite içindeki audit_logs tablosuna kaydedilir.
- Login, logout, kullanıcı ekleme/silme, şifre değiştirme ve ana işlem tetikleme olayları loglanır.
- Setup sayfasında admin tarafında log listesi görüntülenebilir.

## API Uçları

- GET /users (admin)
- POST /users (admin)
- DELETE /users/{username} (admin)
- POST /users/{username}/password (kendi hesabi veya admin)
- GET /logs?limit=100 (admin)
- GET /api/library/tests
- GET /api/library/tests/{test_id}
- POST /api/library/process-testpoint-image
- POST /api/library/testpoints/{testpoint_id}/grafik-gorsel
- POST /api/library/tests (multipart form-data)
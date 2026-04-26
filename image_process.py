import re
import base64
import os
import shutil

import cv2
import numpy as np
import pytesseract


def _tesseract_yolunu_ayarla():
    """Tesseract komutunu platformdan bagimsiz sekilde belirler."""
    env_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if env_cmd:
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return

    bulunan = shutil.which("tesseract")
    if bulunan:
        pytesseract.pytesseract.tesseract_cmd = bulunan
        return

    if os.name == "nt":
        olasi_yollar = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for yol in olasi_yollar:
            if os.path.exists(yol):
                pytesseract.pytesseract.tesseract_cmd = yol
                return


_tesseract_yolunu_ayarla()


def _roi_hazirla(roi, olcek=5, enterpolasyon=cv2.INTER_CUBIC):
    """ROI alanını OCR için gri ton + ölçek + Otsu eşiği ile hazırlar."""
    gri = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    buyutulmus = cv2.resize(gri, None, fx=olcek, fy=olcek, interpolation=enterpolasyon)
    _, esik = cv2.threshold(buyutulmus, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return esik


def _ocr_hatalarini_duzelt(metin, alan):
    """OCR sonrası alan tipine göre tipik karakter hatalarını düzeltir."""
    if alan in ("f", "r"):
        lcd_ikame = {"S": "5", "O": "0", "D": "0", "B": "8", "I": "1", "l": "1"}
        metin = "".join(lcd_ikame.get(harf, harf) for harf in metin)
        eslesen = re.match(r"[\d.]+", metin)
        metin = eslesen.group(0) if eslesen else metin

    if alan == "v":
        metin = re.sub(r"H(?!z)", "0", metin)

    if alan == "tolerans":
        metin = metin.replace("o", "5")
        eslesen = re.search(r"(\d+\.?\d*)%?", metin)
        metin = (eslesen.group(1) + "%") if (eslesen and eslesen.group(1)) else ""

    return metin.strip()


def _gorseli_coz(gorsel_yolu=None, gorsel_bytes=None):
    if gorsel_bytes is not None:
        ham = np.frombuffer(gorsel_bytes, dtype=np.uint8)
        gorsel = cv2.imdecode(ham, cv2.IMREAD_COLOR)
    elif gorsel_yolu is not None:
        gorsel = cv2.imread(gorsel_yolu)
    else:
        raise ValueError("Görsel kaynağı verilmedi")

    if gorsel is None:
        raise ValueError("Görsel okunamadı")
    return gorsel


def testpoint_gorselini_isle(gorsel_yolu=None, gorsel_bytes=None):
    """Test point görselinden v, f, r, tolerans ve grafik koordinat verisini çıkarır."""
    gorsel = _gorseli_coz(gorsel_yolu=gorsel_yolu, gorsel_bytes=gorsel_bytes)

    roiler = {
        "grafik": (2, 272, 2, 272),
        "v": (8, 23, 294, 373),
        "f": (28, 45, 294, 373),
        "r": (48, 65, 294, 373),
        "tolerans": (198, 224, 380, 426),
    }

    alan_ayar = {
        "v": r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.Hz ",
        "f": r"--oem 3 --psm 13",
        "r": r"--oem 3 --psm 13",
        "tolerans": r"--oem 3 --psm 11",
    }

    sonuc = {}

    for alan in ["v", "f", "r", "tolerans"]:
        y1, y2, x1, x2 = roiler[alan]
        roi = gorsel[y1:y2, x1:x2]
        if alan == "tolerans":
            gri = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            hazir = cv2.resize(gri, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        else:
            hazir = _roi_hazirla(roi, olcek=5, enterpolasyon=cv2.INTER_CUBIC)
        ocr_metin = pytesseract.image_to_string(hazir, config=alan_ayar[alan]).strip()
        sonuc[alan] = _ocr_hatalarini_duzelt(ocr_metin, alan)

    hsv = cv2.cvtColor(gorsel, cv2.COLOR_BGR2HSV)
    alt_sari = np.array([20, 100, 100])
    ust_sari = np.array([40, 255, 255])

    gy1, gy2, gx1, gx2 = roiler["grafik"]
    grafik_hsv_roi = hsv[gy1:gy2, gx1:gx2]
    maske = cv2.inRange(grafik_hsv_roi, alt_sari, ust_sari)

    koordinatlar = np.column_stack(np.where(maske > 0))
    grafik_metin = "|".join([f"{x},{y}" for y, x in koordinatlar])

    return {
        "v": sonuc.get("v", ""),
        "f": sonuc.get("f", ""),
        "r": sonuc.get("r", ""),
        "tol": sonuc.get("tolerans", ""),
        "grafik": grafik_metin,
    }


def _olcumden_grafik_gorseli_uret_matris(v, f, r, tol, grafik_metin):
    tuval = np.zeros((271, 271, 3), dtype=np.uint8)

    for nokta in (grafik_metin or "").split("|"):
        if not nokta:
            continue
        try:
            x, y = map(int, nokta.split(","))
            if 0 <= x < 271 and 0 <= y < 271:
                tuval[y, x] = [0, 255, 255]
        except ValueError:
            continue
    return tuval


def olcumden_grafik_gorseli_uret(v, f, r, tol, grafik_metin, cikti_yolu):
    """Ölçüm verilerinden görsel üretir ve çıktı yoluna yazar."""
    son = _olcumden_grafik_gorseli_uret_matris(v, f, r, tol, grafik_metin)
    cv2.imwrite(cikti_yolu, son)
    return cikti_yolu


def olcumden_grafik_gorseli_uret_data_url(v, f, r, tol, grafik_metin):
    """Ölçüm verilerinden görsel üretir ve data URL olarak döndürür."""
    son = _olcumden_grafik_gorseli_uret_matris(v, f, r, tol, grafik_metin)
    ok, encoded = cv2.imencode(".jpg", son)
    if not ok:
        return ""
    b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"

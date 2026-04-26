import hashlib
import json
import secrets
import sqlite3
import base64
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.middleware.sessions import SessionMiddleware

from image_process import olcumden_grafik_gorseli_uret_data_url, testpoint_gorselini_isle

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "vilib.db"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    SessionMiddleware,
    secret_key="change-this-secret-in-production",
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class LoginPayload(BaseModel):
    username: str
    password: str


class CreateUserPayload(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class ChangePasswordPayload(BaseModel):
    current_password: str | None = None
    new_password: str


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


def _db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _init_db() -> None:
    with _db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                image_data BLOB NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS testpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                v TEXT,
                f TEXT,
                r TEXT,
                tol TEXT,
                grafik TEXT,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_gnd INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(test_id) REFERENCES tests(id) ON DELETE CASCADE
            )
            """
        )
        _kolon_ekle(connection, "tests", "description", "TEXT")
        _kolon_ekle(connection, "tests", "image_data", "BLOB")
        _kolon_ekle(connection, "testpoints", "v", "TEXT")
        _kolon_ekle(connection, "testpoints", "f", "TEXT")
        _kolon_ekle(connection, "testpoints", "r", "TEXT")
        _kolon_ekle(connection, "testpoints", "tol", "TEXT")
        _kolon_ekle(connection, "testpoints", "grafik", "TEXT")
        _kolon_ekle(connection, "testpoints", "description", "TEXT")
        _kolon_ekle(connection, "testpoints", "is_gnd", "INTEGER NOT NULL DEFAULT 0")
        _migrate_library_schema(connection)


def _kolon_ekle(connection: sqlite3.Connection, tablo: str, kolon: str, tip: str) -> None:
    kolonlar = connection.execute(f"PRAGMA table_info({tablo})").fetchall()
    kolon_isimleri = {satir[1] for satir in kolonlar}
    if kolon not in kolon_isimleri:
        connection.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tip}")


def _tablo_kolonlari(connection: sqlite3.Connection, tablo: str) -> set[str]:
    kolonlar = connection.execute(f"PRAGMA table_info({tablo})").fetchall()
    return {satir[1] for satir in kolonlar}


def _tablo_var_mi(connection: sqlite3.Connection, tablo: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (tablo,),
    ).fetchone()
    return row is not None


def _migrate_library_schema(connection: sqlite3.Connection) -> None:
    tests_kolon = _tablo_kolonlari(connection, "tests")
    tests_info = connection.execute("PRAGMA table_info(tests)").fetchall()
    image_data_notnull = any(
        satir[1] == "image_data" and int(satir[3]) == 1
        for satir in tests_info
    )

    if "image_path" in tests_kolon or not image_data_notnull:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tests_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                image_data BLOB NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        source_cols = _tablo_kolonlari(connection, "tests")
        description_expr = "description" if "description" in source_cols else "''"
        image_data_expr = "image_data" if "image_data" in source_cols else "X''"
        created_by_expr = "created_by" if "created_by" in source_cols else "'unknown'"
        created_at_expr = "created_at" if "created_at" in source_cols else "CURRENT_TIMESTAMP"

        connection.execute(
            f"""
            INSERT INTO tests_new (id, name, description, image_data, created_by, created_at)
            SELECT
                id,
                name,
                {description_expr},
                COALESCE({image_data_expr}, X''),
                COALESCE({created_by_expr}, 'unknown'),
                COALESCE({created_at_expr}, CURRENT_TIMESTAMP)
            FROM tests
            """
        )

        connection.execute("DROP TABLE tests")
        connection.execute("ALTER TABLE tests_new RENAME TO tests")
        connection.execute("PRAGMA foreign_keys = ON")

    if _tablo_var_mi(connection, "olcumlar"):
        connection.execute(
            """
            UPDATE testpoints
            SET
                v = COALESCE(v, (SELECT o.v FROM olcumlar o WHERE o.testpoint_id = testpoints.id ORDER BY o.id DESC LIMIT 1)),
                f = COALESCE(f, (SELECT o.f FROM olcumlar o WHERE o.testpoint_id = testpoints.id ORDER BY o.id DESC LIMIT 1)),
                r = COALESCE(r, (SELECT o.r FROM olcumlar o WHERE o.testpoint_id = testpoints.id ORDER BY o.id DESC LIMIT 1)),
                tol = COALESCE(tol, (SELECT o.tol FROM olcumlar o WHERE o.testpoint_id = testpoints.id ORDER BY o.id DESC LIMIT 1)),
                grafik = COALESCE(grafik, (SELECT o.grafik FROM olcumlar o WHERE o.testpoint_id = testpoints.id ORDER BY o.id DESC LIMIT 1))
            """
        )
        connection.execute("DROP TABLE olcumlar")


def _log_action(actor: str, action: str, target: str = "", details: dict | None = None) -> None:
    details_text = json.dumps(details, ensure_ascii=False) if details else None
    with _db_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit_logs (actor, action, target, details)
            VALUES (?, ?, ?, ?)
            """,
            (actor, action, target, details_text),
        )


def _find_user(username: str) -> dict | None:
    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT username, salt, password_hash, is_admin
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if not row:
        return None

    return {
        "username": row["username"],
        "salt": row["salt"],
        "password_hash": row["password_hash"],
        "is_admin": bool(row["is_admin"]),
    }


def has_admin_user() -> bool:
    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM users
            WHERE is_admin = 1
            LIMIT 1
            """
        ).fetchone()
    return row is not None


def create_admin_user(username: str, password: str) -> bool:
    created = _create_user(username=username, password=password, is_admin=True)
    if created:
        _log_action(actor="system", action="admin_created", target=username)
    return created


def _create_user(username: str, password: str, is_admin: bool = False) -> bool:
    if _find_user(username):
        return False

    salt = secrets.token_hex(16)
    password_hash = _hash_password(password, salt)
    with _db_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (username, salt, password_hash, is_admin)
            VALUES (?, ?, ?, ?)
            """,
            (username, salt, password_hash, 1 if is_admin else 0),
        )
    return True


def validate_user(username: str, password: str) -> bool:
    user = _find_user(username)
    if not user:
        return False
    expected_hash = _hash_password(password, user["salt"])
    return secrets.compare_digest(expected_hash, user["password_hash"])


def _get_current_username(request: Request) -> str:
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Yetkisiz erişim")
    return username


def _is_admin(username: str) -> bool:
    user = _find_user(username)
    return bool(user and user.get("is_admin"))


def _require_admin(request: Request) -> str:
    current_username = _get_current_username(request)
    if not _is_admin(current_username):
        raise HTTPException(status_code=403, detail="Bu işlem için admin yetkisi gerekir")
    return current_username


def _form_dosyasi_al(form_data, alan_adi: str) -> UploadFile:
    dosya = form_data.get(alan_adi)
    if isinstance(dosya, (UploadFile, StarletteUploadFile)) and getattr(dosya, "filename", ""):
        return dosya
    raise HTTPException(status_code=400, detail=f"{alan_adi} alanı için dosya zorunlu")


@app.get("/")
def home(request: Request):
    if not request.session.get("username"):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse(BASE_DIR / "home.html")


@app.get("/login")
def login_page(request: Request):
    return FileResponse(BASE_DIR / "login.html")


@app.get("/setup")
def setup_page(request: Request):
    _require_admin(request)
    return FileResponse(BASE_DIR / "setup.html")

@app.get("/test")
def test_page(request: Request):
    _get_current_username(request)
    return RedirectResponse(url="/", status_code=303)

@app.get("/library")
def library_page(request: Request):
    _require_admin(request)
    return FileResponse(BASE_DIR / "library.html")

@app.post("/login")
def login(payload: LoginPayload, request: Request):
    if not has_admin_user():
        raise HTTPException(
            status_code=503,
            detail="Admin hesabı bulunamadı. Önce komut satırından admin oluşturun: python run.py create-admin --username admin --password sifreniz",
        )

    if not validate_user(payload.username, payload.password):
        _log_action(actor=payload.username, action="login_failed", target=payload.username)
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")

    request.session["username"] = payload.username
    _log_action(actor=payload.username, action="login_success", target=payload.username)
    return {"message": "Giriş başarılı"}


@app.post("/logout")
def logout_post(request: Request):
    username = request.session.get("username")
    if username:
        _log_action(actor=username, action="logout", target=username)
    request.session.clear()
    return {"message": "Çıkış yapıldı"}


@app.get("/logout")
def logout_get(request: Request):
    username = request.session.get("username")
    if username:
        _log_action(actor=username, action="logout", target=username)
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/me")
def me(request: Request):
    current_username = _get_current_username(request)
    return {"username": current_username, "is_admin": _is_admin(current_username)}


@app.get("/users")
def list_users(request: Request):
    current_username = _require_admin(request)
    with _db_connection() as connection:
        rows = connection.execute(
            """
            SELECT username, is_admin
            FROM users
            ORDER BY username
            """
        ).fetchall()
    _log_action(actor=current_username, action="users_listed")
    users = [{"username": row["username"], "is_admin": bool(row["is_admin"])} for row in rows]
    return {"users": users}


@app.post("/users")
def create_user(payload: CreateUserPayload, request: Request):
    current_username = _require_admin(request)
    created = _create_user(payload.username, payload.password, payload.is_admin)
    if not created:
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten mevcut")
    _log_action(
        actor=current_username,
        action="user_created",
        target=payload.username,
        details={"is_admin": payload.is_admin},
    )
    return {"message": "Kullanıcı oluşturuldu"}


@app.delete("/users/{username}")
def delete_user(username: str, request: Request):
    current_username = _require_admin(request)
    if username == current_username:
        raise HTTPException(status_code=400, detail="Aktif admin hesabı silinemez")

    target_user = _find_user(username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    with _db_connection() as connection:
        if target_user.get("is_admin"):
            row = connection.execute(
                """
                SELECT COUNT(*) AS admin_count
                FROM users
                WHERE is_admin = 1
                """
            ).fetchone()
            if row and row["admin_count"] <= 1:
                raise HTTPException(status_code=400, detail="En az bir admin kalmalı")

        connection.execute("DELETE FROM users WHERE username = ?", (username,))
    _log_action(actor=current_username, action="user_deleted", target=username)
    return {"message": "Kullanıcı silindi"}


@app.post("/users/{username}/password")
def change_password(username: str, payload: ChangePasswordPayload, request: Request):
    current_username = _get_current_username(request)
    current_is_admin = _is_admin(current_username)
    if not current_is_admin and username != current_username:
        raise HTTPException(status_code=403, detail="Sadece kendi şifrenizi değiştirebilirsiniz")

    target_user = _find_user(username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if not current_is_admin or username == current_username:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="Mevcut şifre gerekli")
        current_hash = _hash_password(payload.current_password, target_user["salt"])
        if not secrets.compare_digest(current_hash, target_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Mevcut şifre hatalı")

    target_user["salt"] = secrets.token_hex(16)
    target_user["password_hash"] = _hash_password(payload.new_password, target_user["salt"])
    with _db_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET salt = ?, password_hash = ?
            WHERE username = ?
            """,
            (target_user["salt"], target_user["password_hash"], username),
        )
    _log_action(actor=current_username, action="password_changed", target=username)
    return {"message": "Şifre güncellendi"}


@app.get("/logs")
def list_logs(request: Request, limit: int = 100):
    current_username = _require_admin(request)
    safe_limit = max(1, min(limit, 500))
    with _db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, actor, action, target, details, created_at
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    _log_action(actor=current_username, action="logs_viewed", details={"limit": safe_limit})
    logs = [
        {
            "id": row["id"],
            "actor": row["actor"],
            "action": row["action"],
            "target": row["target"],
            "details": row["details"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"logs": logs}


@app.get("/api/library/tests")
def list_library_tests(request: Request):
    _get_current_username(request)
    with _db_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                t.id,
                t.name,
                t.description,
                t.created_by,
                t.created_at,
                COUNT(tp.id) AS point_count
            FROM tests t
            LEFT JOIN testpoints tp ON tp.test_id = t.id
            GROUP BY t.id
            ORDER BY t.id DESC
            """
        ).fetchall()
    tests = [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "point_count": row["point_count"],
        }
        for row in rows
    ]
    return {"tests": tests}


@app.get("/api/library/tests/{test_id}")
def get_library_test(test_id: int, request: Request):
    _get_current_username(request)
    with _db_connection() as connection:
        test_row = connection.execute(
            """
            SELECT id, name, description, image_data, created_by, created_at
            FROM tests
            WHERE id = ?
            """,
            (test_id,),
        ).fetchone()
        if not test_row:
            raise HTTPException(status_code=404, detail="Test bulunamadı")

        point_rows = connection.execute(
            """
            SELECT
                tp.id,
                tp.name,
                tp.x,
                tp.y,
                tp.description,
                tp.sort_order,
                tp.v,
                tp.f,
                tp.r,
                tp.tol,
                tp.grafik,
                tp.is_gnd
            FROM testpoints tp
            WHERE tp.test_id = ?
            ORDER BY tp.sort_order ASC, tp.id ASC
            """,
            (test_id,),
        ).fetchall()

    image_data = test_row["image_data"]
    image_data_url = ""
    if image_data:
        image_data_url = "data:image/jpeg;base64," + base64.b64encode(image_data).decode("ascii")

    points = [
        {
            "id": row["id"],
            "name": row["name"],
            "x": row["x"],
            "y": row["y"],
            "description": row["description"] or "",
            "is_gnd": bool(row["is_gnd"]),
            "measurement": {
                "v": row["v"] or "",
                "f": row["f"] or "",
                "r": row["r"] or "",
                "tol": row["tol"] or "",
                "grafik": row["grafik"] or "",
                "grafik_gorsel_path": olcumden_grafik_gorseli_uret_data_url(
                    row["v"] or "",
                    row["f"] or "",
                    row["r"] or "",
                    row["tol"] or "",
                    row["grafik"] or "",
                ) if (row["grafik"] or "") else "",
            },
        }
        for row in point_rows
    ]

    return {
        "test": {
            "id": test_row["id"],
            "name": test_row["name"],
            "description": test_row["description"] or "",
            "image_path": image_data_url,
            "created_by": test_row["created_by"],
            "created_at": test_row["created_at"],
        },
        "points": points,
    }


@app.post("/api/library/process-testpoint-image")
async def process_testpoint_image(request: Request, image: UploadFile = File(...)):
    _require_admin(request)
    image_bytes = await image.read()
    try:
        measurement = testpoint_gorselini_isle(gorsel_bytes=image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Görsel işleme hatası: {exc}") from exc

    grafik_gorsel_url = olcumden_grafik_gorseli_uret_data_url(
        measurement.get("v", ""),
        measurement.get("f", ""),
        measurement.get("r", ""),
        measurement.get("tol", ""),
        measurement.get("grafik", ""),
    ) if measurement.get("grafik") else ""

    return {
        "message": "Test point görseli işlendi",
        "measurement": {
            **measurement,
            "grafik_gorsel_path": grafik_gorsel_url,
        },
    }


@app.post("/api/library/testpoints/{testpoint_id}/grafik-gorsel")
def regenerate_testpoint_graph_image(testpoint_id: int, request: Request):
    _require_admin(request)
    with _db_connection() as connection:
        row = connection.execute(
            """
            SELECT tp.v, tp.f, tp.r, tp.tol, tp.grafik
            FROM testpoints tp
            WHERE tp.id = ?
            """,
            (testpoint_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Test point ölçüm verisi bulunamadı")

    grafik_gorsel_url = olcumden_grafik_gorseli_uret_data_url(
        row["v"] or "",
        row["f"] or "",
        row["r"] or "",
        row["tol"] or "",
        row["grafik"] or "",
    ) if (row["grafik"] or "") else ""

    return {"grafik_gorsel_path": grafik_gorsel_url}


@app.post("/api/library/tests")
async def create_library_test(request: Request):
    current_username = _require_admin(request)

    form = await request.form()
    test_name = str(form.get("test_name") or "").strip()
    test_description = str(form.get("test_description") or "").strip()
    points_json = str(form.get("points_json") or "")
    image = form.get("image")

    if not test_name:
        raise HTTPException(status_code=400, detail="Test adı zorunlu")
    if not isinstance(image, (UploadFile, StarletteUploadFile)) or not getattr(image, "filename", ""):
        raise HTTPException(status_code=400, detail="Kart görseli zorunlu")

    try:
        parsed_points = json.loads(points_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Test noktası verisi hatalı") from exc

    if not isinstance(parsed_points, list) or not parsed_points:
        raise HTTPException(status_code=400, detail="En az bir test noktası gerekli")

    card_image_bytes = await image.read()
    if not card_image_bytes:
        raise HTTPException(status_code=400, detail="Kart görseli okunamadı")

    with _db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tests (name, description, image_data, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (test_name.strip(), test_description, card_image_bytes, current_username),
        )
        test_id = cursor.lastrowid

        for index, point in enumerate(parsed_points):
            point_num = index + 1
            point_name = str(point.get("name") or f"TP{point_num}")
            x = float(point.get("x", 0))
            y = float(point.get("y", 0))
            point_description = str(point.get("description") or "")
            is_gnd = 1 if point.get("is_gnd", False) else 0

            point_image = form.get(f"point_image_{index}")
            point_image_bytes = b""
            if isinstance(point_image, (UploadFile, StarletteUploadFile)) and getattr(point_image, "filename", ""):
                point_image_bytes = await point_image.read()

            extracted = {"v": "", "f": "", "r": "", "tol": "", "grafik": ""}
            if point_image_bytes:
                try:
                    extracted = testpoint_gorselini_isle(gorsel_bytes=point_image_bytes)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=f"TP{point_num} işleme hatası: {exc}") from exc

            connection.execute(
                """
                INSERT INTO testpoints (test_id, name, x, y, v, f, r, tol, grafik, description, sort_order, is_gnd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    test_id,
                    point_name,
                    x,
                    y,
                    str(extracted.get("v", "")),
                    str(extracted.get("f", "")),
                    str(extracted.get("r", "")),
                    str(extracted.get("tol", "")),
                    str(extracted.get("grafik", "")),
                    point_description,
                    point_num,
                    is_gnd,
                ),
            )

    _log_action(
        actor=current_username,
        action="library_test_created",
        target=str(test_id),
        details={"name": test_name, "description": test_description, "point_count": len(parsed_points)},
    )

    return {"message": "Test kaydı oluşturuldu", "test_id": test_id}


@app.put("/api/library/tests/{test_id}")
@app.post("/api/library/tests/{test_id}")
async def update_library_test(test_id: int, request: Request):
    current_username = _require_admin(request)

    form = await request.form()
    test_name = str(form.get("test_name") or "").strip()
    test_description = str(form.get("test_description") or "").strip()
    points_json = str(form.get("points_json") or "")
    image = form.get("image")

    if not test_name:
        raise HTTPException(status_code=400, detail="Test adı zorunlu")

    try:
        parsed_points = json.loads(points_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Test noktası verisi hatalı") from exc

    if not isinstance(parsed_points, list) or not parsed_points:
        raise HTTPException(status_code=400, detail="En az bir test noktası gerekli")

    with _db_connection() as connection:
        test_row = connection.execute(
            "SELECT id FROM tests WHERE id = ?", (test_id,)
        ).fetchone()
        if not test_row:
            raise HTTPException(status_code=404, detail="Test bulunamadı")

        has_new_image = isinstance(image, (UploadFile, StarletteUploadFile)) and getattr(image, "filename", "")
        if has_new_image:
            card_image_bytes = await image.read()
            if card_image_bytes:
                connection.execute(
                    "UPDATE tests SET name=?, description=?, image_data=? WHERE id=?",
                    (test_name, test_description, card_image_bytes, test_id),
                )
            else:
                connection.execute(
                    "UPDATE tests SET name=?, description=? WHERE id=?",
                    (test_name, test_description, test_id),
                )
        else:
            connection.execute(
                "UPDATE tests SET name=?, description=? WHERE id=?",
                (test_name, test_description, test_id),
            )

        existing_ids = {
            row["id"]
            for row in connection.execute(
                "SELECT id FROM testpoints WHERE test_id = ?", (test_id,)
            ).fetchall()
        }

        submitted_ids = set()

        for index, point in enumerate(parsed_points):
            point_num = index + 1
            point_id = point.get("id")
            point_name = str(point.get("name") or f"TP{point_num}")
            x = float(point.get("x", 0))
            y = float(point.get("y", 0))
            point_description = str(point.get("description") or "")
            is_gnd = 1 if point.get("is_gnd", False) else 0

            point_image = form.get(f"point_image_{index}")
            has_point_image = isinstance(point_image, (UploadFile, StarletteUploadFile)) and getattr(point_image, "filename", "")

            if point_id and int(point_id) in existing_ids:
                submitted_ids.add(int(point_id))
                if has_point_image:
                    point_image_bytes = await point_image.read()
                    if point_image_bytes:
                        try:
                            extracted = testpoint_gorselini_isle(gorsel_bytes=point_image_bytes)
                        except Exception as exc:
                            raise HTTPException(status_code=400, detail=f"TP{point_num} işleme hatası: {exc}") from exc
                        connection.execute(
                            """
                            UPDATE testpoints
                            SET name=?, x=?, y=?, description=?, v=?, f=?, r=?, tol=?, grafik=?, sort_order=?, is_gnd=?
                            WHERE id=?
                            """,
                            (
                                point_name, x, y, point_description,
                                str(extracted.get("v", "")), str(extracted.get("f", "")),
                                str(extracted.get("r", "")), str(extracted.get("tol", "")),
                                str(extracted.get("grafik", "")), point_num, is_gnd, int(point_id),
                            ),
                        )
                    else:
                        connection.execute(
                            "UPDATE testpoints SET name=?, x=?, y=?, description=?, sort_order=?, is_gnd=? WHERE id=?",
                            (point_name, x, y, point_description, point_num, is_gnd, int(point_id)),
                        )
                else:
                    connection.execute(
                        "UPDATE testpoints SET name=?, x=?, y=?, description=?, sort_order=?, is_gnd=? WHERE id=?",
                        (point_name, x, y, point_description, point_num, is_gnd, int(point_id)),
                    )
            else:
                extracted = {"v": "", "f": "", "r": "", "tol": "", "grafik": ""}
                if has_point_image:
                    point_image_bytes = await point_image.read()
                    if point_image_bytes:
                        try:
                            extracted = testpoint_gorselini_isle(gorsel_bytes=point_image_bytes)
                        except Exception as exc:
                            raise HTTPException(status_code=400, detail=f"TP{point_num} işleme hatası: {exc}") from exc
                connection.execute(
                    """
                    INSERT INTO testpoints (test_id, name, x, y, v, f, r, tol, grafik, description, sort_order, is_gnd)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        test_id, point_name, x, y,
                        str(extracted.get("v", "")), str(extracted.get("f", "")),
                        str(extracted.get("r", "")), str(extracted.get("tol", "")),
                        str(extracted.get("grafik", "")), point_description, point_num, is_gnd,
                    ),
                )

        ids_to_delete = existing_ids - submitted_ids
        for del_id in ids_to_delete:
            connection.execute("DELETE FROM testpoints WHERE id = ?", (del_id,))

    _log_action(
        actor=current_username,
        action="library_test_updated",
        target=str(test_id),
        details={"name": test_name, "point_count": len(parsed_points)},
    )

    return {"message": "Test güncellendi", "test_id": test_id}


_init_db()

@app.get("/run")
def run(request: Request):
    current_username = _get_current_username(request)
    _log_action(actor=current_username, action="run_triggered")
    return "İşlem tamamlandı"
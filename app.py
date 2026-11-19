#!/usr/bin/env python3
"""
Sistema de Asistencia - Versión Web Multiplataforma
Soporta SQLite (local) y PostgreSQL (producción / nube).
"""

import os
import sys
from datetime import datetime
from functools import wraps
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
)
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "asistencia.db"
ESTADOS = ("Presente", "Ausente", "Excusa")

# DATABASE_URL: si existe → PostgreSQL; si no → SQLite local
# Ejemplo Render/Railway: postgresql://user:pass@host:5432/dbname
_raw_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_url.startswith("postgres://"):
    # SQLAlchemy 2.x requiere el esquema postgresql://
    _raw_url = "postgresql://" + _raw_url[len("postgres://"):]

if _raw_url:
    DATABASE_URL = _raw_url
    IS_POSTGRES = True
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    IS_POSTGRES = False

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    # SQLite: permitir uso desde varios hilos de Flask en desarrollo
    connect_args={"check_same_thread": False} if not IS_POSTGRES else {},
)

# Activar foreign keys en SQLite
if not IS_POSTGRES:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "asistencia-secreta-cambiar-en-produccion-2026"
)
app.config["TEMPLATES_AUTO_RELOAD"] = True


# -----------------------------------------------------------------------------
# Capa de base de datos (compatible SQLite + PostgreSQL)
# -----------------------------------------------------------------------------
class DB:
    """Pequeño wrapper para consultas con la misma API que usaba sqlite3."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        if params is None:
            params = {}
        elif isinstance(params, (list, tuple)):
            # Convertir ? a :p0, :p1... y lista a dict (SQLAlchemy text)
            sql, params = _qmarks_to_named(sql, params)
        result = self.conn.execute(text(sql), params)
        return ResultProxy(result)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


class ResultProxy:
    def __init__(self, result):
        self._result = result
        self._rows = None

    def _load(self):
        if self._rows is None:
            self._rows = [Row(r) for r in self._result.mappings().all()]
        return self._rows

    def fetchone(self):
        rows = self._load()
        return rows[0] if rows else None

    def fetchall(self):
        return self._load()

    def __iter__(self):
        return iter(self._load())


class Row:
    """Acceso por nombre (row['col']) y por índice (row[0])."""

    def __init__(self, mapping):
        self._data = dict(mapping)
        self._keys = list(self._data.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name)

    def keys(self):
        return self._keys

    def __repr__(self):
        return f"Row({self._data})"


def _qmarks_to_named(sql, params):
    """Convierte 'WHERE id = ?' + (1,) en 'WHERE id = :p0' + {'p0': 1}."""
    parts = sql.split("?")
    if len(parts) - 1 != len(params):
        raise ValueError(
            f"Placeholders (?) no coinciden con parámetros: "
            f"{len(parts) - 1} vs {len(params)}"
        )
    named = {}
    out = [parts[0]]
    for i, p in enumerate(params):
        key = f"p{i}"
        named[key] = p
        out.append(f":{key}")
        out.append(parts[i + 1])
    return "".join(out), named


def get_db():
    if "db" not in g:
        g.db = DB(engine.connect())
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        if exception is not None:
            try:
                db.conn.rollback()
            except Exception:
                pass
        db.close()


def _table_columns(conn, table):
    """Lista de nombres de columnas (funciona en SQLite y PostgreSQL)."""
    if IS_POSTGRES:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = 'public'"
            ),
            {"t": table},
        ).fetchall()
        return {r[0] for r in rows}
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # PRAGMA: cid, name, type, notnull, dflt_value, pk
    return {r[1] for r in rows}


def init_db():
    """Crea tablas e inserta datos iniciales si no existen."""
    pk = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    # TEXT en ambos; BOOLEAN no necesario

    ddl = f"""
        CREATE TABLE IF NOT EXISTS carreras (
            id {pk},
            nombre TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id {pk},
            nombre TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL,
            carrera_id INTEGER REFERENCES carreras(id),
            semestre INTEGER CHECK (semestre BETWEEN 1 AND 3),
            documento_identidad TEXT
        );

        CREATE TABLE IF NOT EXISTS materias (
            id {pk},
            nombre TEXT NOT NULL,
            carrera_id INTEGER NOT NULL REFERENCES carreras(id),
            semestre INTEGER CHECK (semestre BETWEEN 1 AND 3),
            UNIQUE (nombre, carrera_id)
        );

        CREATE TABLE IF NOT EXISTS asistencias (
            id {pk},
            estudiante TEXT NOT NULL,
            estudiante_id INTEGER REFERENCES usuarios(id),
            fecha TEXT NOT NULL,
            hora TEXT,
            estado TEXT NOT NULL,
            docente TEXT NOT NULL,
            materia_id INTEGER REFERENCES materias(id)
        );

        CREATE TABLE IF NOT EXISTS docente_materias (
            docente_id INTEGER NOT NULL REFERENCES usuarios(id),
            materia_id INTEGER NOT NULL REFERENCES materias(id),
            PRIMARY KEY (docente_id, materia_id)
        );

        CREATE TABLE IF NOT EXISTS estudiante_materias (
            estudiante_id INTEGER NOT NULL REFERENCES usuarios(id),
            materia_id INTEGER NOT NULL REFERENCES materias(id),
            PRIMARY KEY (estudiante_id, materia_id)
        );
    """

    with engine.begin() as conn:
        # Ejecutar cada sentencia por separado (Postgres no admite multi-statement fácil)
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))

        # Índice único en documento (si la columna existe)
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_documento_identidad "
                    "ON usuarios (documento_identidad)"
                )
            )
        except Exception:
            # En Postgres, IF NOT EXISTS del índice está bien desde PG 9.5+;
            # si falla por NULL duplicados, se ignora.
            pass

        # Migraciones suaves (solo columnas que puedan faltar en DBs antiguas SQLite)
        cols_u = _table_columns(conn, "usuarios")
        if "carrera_id" not in cols_u:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN carrera_id INTEGER REFERENCES carreras(id)"))
        if "semestre" not in cols_u:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN semestre INTEGER"))
        if "documento_identidad" not in cols_u:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN documento_identidad TEXT"))

        cols_m = _table_columns(conn, "materias")
        if "semestre" not in cols_m:
            conn.execute(text("ALTER TABLE materias ADD COLUMN semestre INTEGER"))

        cols_a = _table_columns(conn, "asistencias")
        if "materia_id" not in cols_a:
            conn.execute(text("ALTER TABLE asistencias ADD COLUMN materia_id INTEGER REFERENCES materias(id)"))
        if "estudiante_id" not in cols_a:
            conn.execute(text("ALTER TABLE asistencias ADD COLUMN estudiante_id INTEGER REFERENCES usuarios(id)"))
        if "hora" not in cols_a:
            conn.execute(text("ALTER TABLE asistencias ADD COLUMN hora TEXT"))

        # Datos iniciales (compatibles con ambos motores)
        if IS_POSTGRES:
            conn.execute(
                text(
                    "INSERT INTO carreras (nombre) VALUES (:n) "
                    "ON CONFLICT (nombre) DO NOTHING"
                ),
                {"n": "Sistemas"},
            )
        else:
            conn.execute(
                text("INSERT OR IGNORE INTO carreras (nombre) VALUES (:n)"),
                {"n": "Sistemas"},
            )

        row = conn.execute(
            text("SELECT id FROM carreras WHERE nombre = :n"), {"n": "Sistemas"}
        ).fetchone()
        carrera_sistemas_id = row[0]

        for materia_inicial in ("Programación", "Arduino"):
            if IS_POSTGRES:
                conn.execute(
                    text(
                        "INSERT INTO materias (nombre, carrera_id, semestre) "
                        "VALUES (:nombre, :cid, 1) "
                        "ON CONFLICT (nombre, carrera_id) DO NOTHING"
                    ),
                    {"nombre": materia_inicial, "cid": carrera_sistemas_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO materias (nombre, carrera_id, semestre) "
                        "VALUES (:nombre, :cid, 1)"
                    ),
                    {"nombre": materia_inicial, "cid": carrera_sistemas_id},
                )

        usuarios_iniciales = [
            ("Docente de prueba", "docente", "1234", "docente"),
            ("Secretario de prueba", "secretario", "1234", "secretario"),
            ("Estudiante de prueba", "estudiante", "1234", "estudiante"),
        ]
        for nombre, usuario, clave, rol in usuarios_iniciales:
            if IS_POSTGRES:
                conn.execute(
                    text(
                        "INSERT INTO usuarios (nombre, usuario, clave, rol) "
                        "VALUES (:nombre, :usuario, :clave, :rol) "
                        "ON CONFLICT (usuario) DO NOTHING"
                    ),
                    {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol},
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO usuarios (nombre, usuario, clave, rol) "
                        "VALUES (:nombre, :usuario, :clave, :rol)"
                    ),
                    {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol},
                )

        conn.execute(
            text(
                "UPDATE usuarios SET carrera_id = :cid, semestre = 1 "
                "WHERE usuario = 'estudiante' AND rol = 'estudiante' AND carrera_id IS NULL"
            ),
            {"cid": carrera_sistemas_id},
        )

        est = conn.execute(
            text(
                "SELECT id FROM usuarios "
                "WHERE usuario = 'estudiante' AND rol = 'estudiante' AND carrera_id = :cid"
            ),
            {"cid": carrera_sistemas_id},
        ).fetchone()
        if est:
            if IS_POSTGRES:
                conn.execute(
                    text(
                        "INSERT INTO estudiante_materias (estudiante_id, materia_id) "
                        "SELECT :eid, id FROM materias WHERE carrera_id = :cid "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"eid": est[0], "cid": carrera_sistemas_id},
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO estudiante_materias (estudiante_id, materia_id) "
                        "SELECT :eid, id FROM materias WHERE carrera_id = :cid"
                    ),
                    {"eid": est[0], "cid": carrera_sistemas_id},
                )


def insert_returning_id(db, sql, params):
    """INSERT y devuelve el id generado (RETURNING en PG, lastrowid en SQLite)."""
    if IS_POSTGRES:
        if "RETURNING" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " RETURNING id"
        row = db.execute(sql, params).fetchone()
        return row[0] if row else None
    # SQLite: lastrowid del CursorResult (no hacer commit aquí: el caller gestiona la tx)
    sql2, named = (
        _qmarks_to_named(sql, params)
        if isinstance(params, (list, tuple))
        else (sql, params)
    )
    result = db.conn.execute(text(sql2), named)
    return result.lastrowid


# -----------------------------------------------------------------------------
# Autenticación
# -----------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                flash("Debes iniciar sesión.", "warning")
                return redirect(url_for("login"))
            if session.get("rol") not in roles:
                flash("No tienes permiso para esta acción.", "danger")
                return redirect(url_for("menu"))
            return f(*args, **kwargs)

        return decorated

    return decorator


def current_user():
    if "user_id" not in session:
        return None
    return {
        "id": session["user_id"],
        "nombre": session["nombre"],
        "rol": session["rol"],
        "usuario": session.get("usuario", ""),
    }


# -----------------------------------------------------------------------------
# Rutas principales
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("menu"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("menu"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "")
        db = get_db()
        row = db.execute(
            "SELECT id, nombre, rol, usuario FROM usuarios WHERE usuario = ? AND clave = ?",
            (usuario, clave),
        ).fetchone()
        if row is None:
            flash("Usuario o contraseña incorrectos.", "danger")
        else:
            session.clear()
            session["user_id"] = row["id"]
            session["nombre"] = row["nombre"]
            session["rol"] = row["rol"]
            session["usuario"] = row["usuario"]
            flash(f"Bienvenido, {row['nombre']}", "success")
            return redirect(url_for("menu"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("login"))


@app.route("/menu")
@login_required
def menu():
    return render_template("menu.html", user=current_user())


# -----------------------------------------------------------------------------
# Consultar asistencia
# -----------------------------------------------------------------------------
@app.route("/consultar", methods=["GET", "POST"])
@login_required
def consultar():
    user = current_user()
    registros = []
    busqueda = ""

    if user["rol"] == "estudiante":
        db = get_db()
        registros = db.execute(
            """
            SELECT COALESCE(u.nombre, a.estudiante) AS estudiante,
                   COALESCE(u.documento_identidad, '—') AS documento,
                   a.fecha, COALESCE(a.hora, '—') AS hora, a.estado, a.docente,
                   COALESCE(m.nombre, 'Sin materia') AS materia,
                   COALESCE(c.nombre, 'Sin carrera') AS carrera
            FROM asistencias AS a
            LEFT JOIN usuarios AS u ON u.id = a.estudiante_id
            LEFT JOIN materias AS m ON m.id = a.materia_id
            LEFT JOIN carreras AS c ON c.id = m.carrera_id
            WHERE a.estudiante_id = ?
            ORDER BY a.fecha DESC, a.hora DESC
            """,
            (user["id"],),
        ).fetchall()
        return render_template(
            "consultar.html", user=user, registros=registros, solo_propio=True
        )

    if request.method == "POST":
        busqueda = request.form.get("busqueda", "").strip()
        if busqueda:
            db = get_db()
            registros = db.execute(
                """
                SELECT COALESCE(u.nombre, a.estudiante) AS estudiante,
                       COALESCE(u.documento_identidad, '—') AS documento,
                       a.fecha, COALESCE(a.hora, '—') AS hora, a.estado, a.docente,
                       COALESCE(m.nombre, 'Sin materia') AS materia,
                       COALESCE(c.nombre, 'Sin carrera') AS carrera
                FROM asistencias AS a
                LEFT JOIN usuarios AS u ON u.id = a.estudiante_id
                LEFT JOIN materias AS m ON m.id = a.materia_id
                LEFT JOIN carreras AS c ON c.id = m.carrera_id
                WHERE (COALESCE(u.nombre, a.estudiante) LIKE ?
                       OR u.documento_identidad = ?)
                ORDER BY a.fecha DESC, a.hora DESC
                """,
                (f"%{busqueda}%", busqueda),
            ).fetchall()
            if not registros:
                flash("No se encontraron registros.", "info")

    return render_template(
        "consultar.html",
        user=user,
        registros=registros,
        busqueda=busqueda,
        solo_propio=False,
    )


# -----------------------------------------------------------------------------
# Reporte mensual (secretario)
# -----------------------------------------------------------------------------
@app.route("/reporte")
@role_required("secretario")
def reporte():
    user = current_user()
    mes = datetime.now().astimezone().strftime("%Y-%m")
    db = get_db()
    registros = db.execute(
        """
        SELECT COALESCE(u.nombre, a.estudiante) AS estudiante,
               COALESCE(u.documento_identidad, '—') AS documento,
               COALESCE(c.nombre, 'Sin carrera') AS carrera,
               COALESCE(m.nombre, 'Sin materia') AS materia,
               COUNT(*) AS total,
               SUM(CASE WHEN a.estado = 'Presente' THEN 1 ELSE 0 END) AS presentes,
               SUM(CASE WHEN a.estado = 'Ausente' THEN 1 ELSE 0 END) AS ausentes,
               SUM(CASE WHEN a.estado = 'Excusa' THEN 1 ELSE 0 END) AS excusas
        FROM asistencias AS a
        LEFT JOIN usuarios AS u ON u.id = a.estudiante_id
        LEFT JOIN materias AS m ON m.id = a.materia_id
        LEFT JOIN carreras AS c ON c.id = m.carrera_id
        WHERE a.fecha LIKE ?
        GROUP BY a.estudiante_id, a.estudiante, m.id, c.id,
                 u.nombre, u.documento_identidad, c.nombre, m.nombre
        ORDER BY c.nombre, m.nombre, u.nombre
        """,
        (f"{mes}-%",),
    ).fetchall()
    return render_template("reporte.html", user=user, registros=registros, mes=mes)


# -----------------------------------------------------------------------------
# Registro de datos (secretario)
# -----------------------------------------------------------------------------
@app.route("/registro")
@role_required("secretario")
def menu_registro():
    return render_template("menu_registro.html", user=current_user())


@app.route("/registro/estudiante", methods=["GET", "POST"])
@role_required("secretario")
def registrar_estudiante():
    user = current_user()
    db = get_db()
    carreras = db.execute("SELECT id, nombre FROM carreras ORDER BY nombre").fetchall()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        documento = request.form.get("documento", "").strip()
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "")
        carrera_id = request.form.get("carrera_id", type=int)
        semestre = request.form.get("semestre", type=int)
        materias_ids = request.form.getlist("materias", type=int)

        if not all([nombre, documento, usuario, clave, carrera_id, semestre]):
            flash("Completa todos los campos obligatorios.", "danger")
        elif not materias_ids:
            flash("Selecciona al menos una materia.", "danger")
        else:
            try:
                with engine.begin() as conn:
                    dbw = DB(conn)
                    estudiante_id = insert_returning_id(
                        dbw,
                        "INSERT INTO usuarios "
                        "(nombre, documento_identidad, usuario, clave, rol, carrera_id, semestre) "
                        "VALUES (?, ?, ?, ?, 'estudiante', ?, ?)",
                        (nombre, documento, usuario, clave, carrera_id, semestre),
                    )
                    for mid in materias_ids:
                        if IS_POSTGRES:
                            dbw.execute(
                                "INSERT INTO estudiante_materias (estudiante_id, materia_id) "
                                "VALUES (?, ?) ON CONFLICT DO NOTHING",
                                (estudiante_id, mid),
                            )
                        else:
                            dbw.execute(
                                "INSERT OR IGNORE INTO estudiante_materias "
                                "(estudiante_id, materia_id) VALUES (?, ?)",
                                (estudiante_id, mid),
                            )
                flash("Estudiante registrado correctamente.", "success")
                return redirect(url_for("menu_registro"))
            except IntegrityError:
                flash("Documento o nombre de usuario ya existe.", "danger")

    materias = db.execute(
        """
        SELECT m.id, m.nombre, m.carrera_id, m.semestre, c.nombre AS carrera
        FROM materias m JOIN carreras c ON c.id = m.carrera_id
        ORDER BY c.nombre, m.nombre
        """
    ).fetchall()
    return render_template(
        "registrar_estudiante.html",
        user=user,
        carreras=carreras,
        materias=materias,
    )


@app.route("/registro/docente", methods=["GET", "POST"])
@role_required("secretario")
def registrar_docente():
    user = current_user()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "")
        if not all([nombre, usuario, clave]):
            flash("Completa todos los campos.", "danger")
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES (?, ?, ?, 'docente')",
                    (nombre, usuario, clave),
                )
                db.commit()
                flash("Docente registrado correctamente.", "success")
                return redirect(url_for("menu_registro"))
            except IntegrityError:
                flash("Ese nombre de usuario ya existe.", "danger")
    return render_template("registrar_docente.html", user=user)


@app.route("/registro/carrera", methods=["GET", "POST"])
@role_required("secretario")
def registrar_carrera():
    user = current_user()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("Escribe el nombre de la carrera.", "danger")
        else:
            try:
                db = get_db()
                db.execute("INSERT INTO carreras (nombre) VALUES (?)", (nombre,))
                db.commit()
                flash("Carrera registrada correctamente.", "success")
                return redirect(url_for("menu_registro"))
            except IntegrityError:
                flash("Esa carrera ya existe.", "danger")
    return render_template("registrar_carrera.html", user=user)


@app.route("/registro/materia", methods=["GET", "POST"])
@role_required("secretario")
def registrar_materia():
    user = current_user()
    db = get_db()
    carreras = db.execute("SELECT id, nombre FROM carreras ORDER BY nombre").fetchall()
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        carrera_id = request.form.get("carrera_id", type=int)
        semestre = request.form.get("semestre", type=int)
        if not nombre or not carrera_id or not semestre:
            flash("Completa todos los campos.", "danger")
        else:
            try:
                db.execute(
                    "INSERT INTO materias (nombre, carrera_id, semestre) VALUES (?, ?, ?)",
                    (nombre, carrera_id, semestre),
                )
                db.commit()
                flash("Materia registrada correctamente.", "success")
                return redirect(url_for("menu_registro"))
            except IntegrityError:
                flash("Esa materia ya existe en la carrera seleccionada.", "danger")
    return render_template("registrar_materia.html", user=user, carreras=carreras)


# -----------------------------------------------------------------------------
# Asignar asistencia
# -----------------------------------------------------------------------------
@app.route("/asistencia")
@role_required("docente", "secretario")
def asignar_asistencia():
    user = current_user()
    db = get_db()
    carreras = db.execute(
        """
        SELECT DISTINCT c.id, c.nombre
        FROM carreras c
        JOIN materias m ON m.carrera_id = c.id
        ORDER BY c.nombre
        """
    ).fetchall()
    return render_template("seleccionar_carrera.html", user=user, carreras=carreras)


@app.route("/asistencia/<int:carrera_id>")
@role_required("docente", "secretario")
def seleccionar_materia(carrera_id):
    user = current_user()
    db = get_db()
    carrera = db.execute(
        "SELECT id, nombre FROM carreras WHERE id = ?", (carrera_id,)
    ).fetchone()
    if not carrera:
        flash("Carrera no encontrada.", "danger")
        return redirect(url_for("asignar_asistencia"))
    materias = db.execute(
        "SELECT id, nombre FROM materias WHERE carrera_id = ? ORDER BY nombre",
        (carrera_id,),
    ).fetchall()
    return render_template(
        "seleccionar_materia.html",
        user=user,
        carrera=carrera,
        materias=materias,
    )


@app.route("/asistencia/<int:carrera_id>/<int:materia_id>", methods=["GET", "POST"])
@role_required("docente", "secretario")
def formulario_asistencia(carrera_id, materia_id):
    user = current_user()
    db = get_db()
    carrera = db.execute(
        "SELECT id, nombre FROM carreras WHERE id = ?", (carrera_id,)
    ).fetchone()
    materia = db.execute(
        "SELECT id, nombre FROM materias WHERE id = ? AND carrera_id = ?",
        (materia_id, carrera_id),
    ).fetchone()
    if not carrera or not materia:
        flash("Carrera o materia no encontrada.", "danger")
        return redirect(url_for("asignar_asistencia"))

    estudiantes = db.execute(
        """
        SELECT u.id, u.nombre, COALESCE(u.documento_identidad, '') AS documento
        FROM usuarios u
        JOIN estudiante_materias em ON em.estudiante_id = u.id
        WHERE u.rol = 'estudiante' AND u.carrera_id = ? AND em.materia_id = ?
        ORDER BY u.nombre
        """,
        (carrera_id, materia_id),
    ).fetchall()

    if request.method == "POST":
        fecha_hora = datetime.now().astimezone()
        fecha = fecha_hora.date().isoformat()
        hora = fecha_hora.strftime("%H:%M")
        for est in estudiantes:
            estado = request.form.get(f"estado_{est['id']}", "Presente")
            if estado not in ESTADOS:
                estado = "Presente"
            db.execute(
                """
                INSERT INTO asistencias
                    (estudiante, estudiante_id, fecha, hora, estado, docente, materia_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    est["nombre"],
                    est["id"],
                    fecha,
                    hora,
                    estado,
                    user["nombre"],
                    materia_id,
                ),
            )
        db.commit()
        flash(f"Se registró la asistencia de {len(estudiantes)} estudiante(s).", "success")
        return redirect(url_for("menu"))

    hoy = datetime.now().astimezone().date().isoformat()
    ya = db.execute(
        "SELECT COUNT(*) AS n FROM asistencias WHERE materia_id = ? AND fecha = ?",
        (materia_id, hoy),
    ).fetchone()
    ya_registradas = ya[0] if ya else 0

    return render_template(
        "formulario_asistencia.html",
        user=user,
        carrera=carrera,
        materia=materia,
        estudiantes=estudiantes,
        estados=ESTADOS,
        fecha=hoy,
        ya_registradas=ya_registradas,
    )


# -----------------------------------------------------------------------------
# Auto-registro de estudiante (público)
# -----------------------------------------------------------------------------
@app.route("/registrarme", methods=["GET", "POST"])
def registrarme():
    if "user_id" in session:
        return redirect(url_for("menu"))
    db = get_db()
    carreras = db.execute("SELECT id, nombre FROM carreras ORDER BY nombre").fetchall()
    materias = db.execute(
        """
        SELECT m.id, m.nombre, m.carrera_id, m.semestre, c.nombre AS carrera
        FROM materias m JOIN carreras c ON c.id = m.carrera_id
        ORDER BY c.nombre, m.nombre
        """
    ).fetchall()

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        documento = request.form.get("documento", "").strip()
        usuario = request.form.get("usuario", "").strip()
        clave = request.form.get("clave", "")
        carrera_id = request.form.get("carrera_id", type=int)
        semestre = request.form.get("semestre", type=int)
        materias_ids = request.form.getlist("materias", type=int)

        if not all([nombre, documento, usuario, clave, carrera_id, semestre]):
            flash("Completa todos los campos obligatorios.", "danger")
        elif not materias_ids:
            flash("Selecciona al menos una materia.", "danger")
        else:
            try:
                with engine.begin() as conn:
                    dbw = DB(conn)
                    estudiante_id = insert_returning_id(
                        dbw,
                        "INSERT INTO usuarios "
                        "(nombre, documento_identidad, usuario, clave, rol, carrera_id, semestre) "
                        "VALUES (?, ?, ?, ?, 'estudiante', ?, ?)",
                        (nombre, documento, usuario, clave, carrera_id, semestre),
                    )
                    for mid in materias_ids:
                        if IS_POSTGRES:
                            dbw.execute(
                                "INSERT INTO estudiante_materias (estudiante_id, materia_id) "
                                "VALUES (?, ?) ON CONFLICT DO NOTHING",
                                (estudiante_id, mid),
                            )
                        else:
                            dbw.execute(
                                "INSERT OR IGNORE INTO estudiante_materias "
                                "(estudiante_id, materia_id) VALUES (?, ?)",
                                (estudiante_id, mid),
                            )
                flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
                return redirect(url_for("login"))
            except IntegrityError:
                flash("Documento o nombre de usuario ya existe.", "danger")

    return render_template(
        "registrarme.html",
        carreras=carreras,
        materias=materias,
    )


# -----------------------------------------------------------------------------
# Exportar Excel
# -----------------------------------------------------------------------------
@app.route("/exportar")
@login_required
def exportar_excel():
    db = get_db()
    filas = db.execute(
        """
        SELECT COALESCE(u.nombre, a.estudiante),
               COALESCE(u.documento_identidad, ''),
               COALESCE(c.nombre, 'Sin carrera'),
               COALESCE(m.nombre, 'Sin materia'),
               a.estado, a.fecha, COALESCE(a.hora, ''), a.docente
        FROM asistencias AS a
        LEFT JOIN usuarios AS u ON u.id = a.estudiante_id
        LEFT JOIN materias AS m ON m.id = a.materia_id
        LEFT JOIN carreras AS c ON c.id = m.carrera_id
        ORDER BY a.fecha DESC, a.hora DESC, u.nombre
        """
    ).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Asistencias"
    encabezados = [
        "Estudiante",
        "Documento",
        "Carrera",
        "Materia",
        "Estado",
        "Fecha",
        "Hora",
        "Docente",
    ]
    ws.append(encabezados)

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    for col, cell in enumerate(ws[1], 1):
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin

    for fila in filas:
        ws.append([fila[i] for i in range(8)])

    for col in range(1, 9):
        max_len = max(
            len(str(ws.cell(row=r, column=col).value or ""))
            for r in range(1, ws.max_row + 1)
        )
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 2, 12), 40)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="asistencia.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# -----------------------------------------------------------------------------
# API auxiliar
# -----------------------------------------------------------------------------
@app.route("/api/materias/<int:carrera_id>")
def api_materias(carrera_id):
    db = get_db()
    materias = db.execute(
        "SELECT id, nombre, semestre FROM materias WHERE carrera_id = ? ORDER BY nombre",
        (carrera_id,),
    ).fetchall()
    return {"materias": [{k: m[k] for k in m.keys()} for m in materias]}


@app.route("/salud")
def salud():
    """Endpoint para comprobar que la app y la BD responden (útil en Render)."""
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
        motor = "PostgreSQL" if IS_POSTGRES else "SQLite"
        return {"ok": True, "base_de_datos": motor}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


# -----------------------------------------------------------------------------
# Arranque
# -----------------------------------------------------------------------------
# Inicializar tablas al importar (gunicorn) y al ejecutar en local
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    motor = "PostgreSQL" if IS_POSTGRES else f"SQLite ({DB_PATH.name})"
    print("=" * 60)
    print("  Sistema de Asistencia - Versión Web Multiplataforma")
    print("=" * 60)
    print(f"  Base de datos: {motor}")
    print(f"  Puerto: {port}")
    print(f"  Local:  http://127.0.0.1:{port}")
    print(f"  Red:    http://<IP-de-este-equipo>:{port}")
    print("=" * 60)
    print("  Usuarios de prueba (clave 1234):")
    print("    docente  |  secretario  |  estudiante")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("PORT") is None))

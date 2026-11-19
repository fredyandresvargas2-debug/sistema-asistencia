# Cómo subir el Sistema de Asistencia a internet

Con el servidor en la nube, **cualquiera** (móvil, tablet, PC) podrá usarlo desde cualquier lugar, sin tener un ordenador encendido en casa.

---

## Opciones recomendadas (de más fácil a más avanzada)

| Plataforma        | Plan gratuito | Dificultad | Ideal para                          | Enlace                          |
|-------------------|---------------|------------|-------------------------------------|---------------------------------|
| **Render**        | Sí (se duerme) | Muy fácil  | Principiantes, uso escolar         | https://render.com              |
| **Railway**       | Créditos gratis | Fácil     | Uso frecuente                      | https://railway.app             |
| **PythonAnywhere**| Sí            | Fácil      | Solo Python, sin Docker            | https://www.pythonanywhere.com  |
| **Fly.io**        | Sí            | Media      | Más control y velocidad            | https://fly.io                  |

**Recomendación principal: Render** — es gratis, con interfaz sencilla y no necesitas tarjeta de crédito para empezar.

---

## Opción 1: Render (recomendada)

### Pasos

1. Crea una cuenta en [https://render.com](https://render.com) (puedes usar GitHub).
2. Sube este proyecto a un repositorio de **GitHub** (ver sección “Subir a GitHub” más abajo).
3. En Render → **New** → **Web Service**.
4. Conecta el repositorio de GitHub.
5. Configura:
   - **Name:** `sistema-asistencia` (o el que quieras)
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -b 0.0.0.0:$PORT app:app`
   - **Instance type:** Free
6. En **Environment** (variables de entorno) añade:
   - `SECRET_KEY` = una frase secreta larga (ej. `mi-clave-super-secreta-2026`)
7. Pulsa **Create Web Service**.

En unos minutos tendrás una URL pública tipo:
`https://sistema-asistencia-xxxx.onrender.com`

> En el plan gratuito el servicio se “duerme” tras ~15 min sin uso. La primera visita puede tardar 30–60 segundos en despertar. Para uso diario en clase suele ser suficiente.

---

## Opción 2: Railway

1. Cuenta en [https://railway.app](https://railway.app).
2. **New Project** → **Deploy from GitHub repo**.
3. Selecciona el repositorio.
4. Railway detecta Python. Si no, en Settings → Start Command:
   ```
   gunicorn -b 0.0.0.0:$PORT app:app
   ```
5. Añade variable `SECRET_KEY`.
6. Deploy. Te dan una URL pública.

Railway da créditos mensuales gratis; si se acaban, el servicio se pausa hasta el siguiente mes.

---

## Opción 3: PythonAnywhere

1. Cuenta en [https://www.pythonanywhere.com](https://www.pythonanywhere.com) (plan Beginner gratuito).
2. **Files** → sube la carpeta del proyecto (o clona desde GitHub).
3. **Web** → **Add a new web app** → Manual configuration → Python 3.
4. En **WSGI configuration file** pon algo como:

```python
import sys
path = '/home/TU_USUARIO/sistema_asistencia_web'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

5. En **Virtualenv** crea uno e instala:
   ```
   pip install -r requirements.txt
   ```
6. Reload la web app. Tu URL será: `https://TU_USUARIO.pythonanywhere.com`

---

## Subir el proyecto a GitHub (necesario para Render y Railway)

### Desde el ordenador

1. Crea una cuenta en [https://github.com](https://github.com) si no tienes.
2. Crea un repositorio nuevo (ej. `sistema-asistencia`), **sin** README.
3. En la carpeta del proyecto ejecuta:

```bash
git init
git add .
git commit -m "Sistema de asistencia web"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/sistema-asistencia.git
git push -u origin main
```

(Sustituye `TU_USUARIO` por tu usuario de GitHub.)

### Archivos importantes que ya están preparados

- `requirements.txt` — dependencias
- `Procfile` — comando de arranque (Render/Railway/Heroku)
- `runtime.txt` — versión de Python
- `app.py` — ya usa `PORT` del entorno cuando está en la nube

---

## Seguridad recomendada antes de publicar

1. **Cambia las claves** de los usuarios de prueba (`docente`, `secretario`, `estudiante`).
2. Cambia `SECRET_KEY` en el código o mejor ponla como variable de entorno (como se indica en Render).
3. No subas archivos innecesarios (`.venv`, `__pycache__`). Ya hay un `.gitignore`.

---

## Uso en clase / institución

- Comparte la URL pública con docentes y estudiantes.
- Desde el móvil solo hace falta abrir el enlace en el navegador (Chrome, Safari, etc.).
- No hace falta instalar nada en los teléfonos.
- El Excel se descarga con el botón “Descargar Excel” del menú.

---

## Resumen rápido

| Quieres…                         | Usa          |
|----------------------------------|--------------|
| Lo más fácil y gratis            | **Render**   |
| Más uso diario sin dormirse      | **Railway**  |
| Solo Python, sin GitHub          | **PythonAnywhere** |
| Control avanzado                 | **Fly.io**   |

Si eliges **Render**, con los pasos de arriba en menos de 15 minutos tendrás el sistema online.

---

## Configurar PostgreSQL (recomendado en la nube)

SQLite funciona en local, pero **en Render / Railway el disco se borra al reiniciar**.  
Por eso en producción debes usar **PostgreSQL**.

La aplicación detecta sola la variable `DATABASE_URL`:
- Si existe → usa PostgreSQL
- Si no existe → usa SQLite (`asistencia.db`)

### En Render

1. En tu servicio web (o en el dashboard) ve a **New** → **PostgreSQL**.
2. Crea la base (plan Free).
3. Cuando esté lista, copia la **Internal Database URL** (o External).
4. En tu **Web Service** → **Environment** añade:
   - `DATABASE_URL` = (pega la URL de Postgres)
   - `SECRET_KEY` = una frase secreta larga
5. **Manual Deploy** → Deploy latest commit (o reinicia el servicio).

La app creará las tablas automáticamente al arrancar.

Comprueba que todo va bien abriendo:
`https://TU-URL.onrender.com/salud`

Debería responder algo como:
```json
{"ok": true, "base_de_datos": "PostgreSQL"}
```

### En Railway

1. En el proyecto → **New** → **Database** → **PostgreSQL**.
2. Railway inyecta `DATABASE_URL` automáticamente en el servicio web si están en el mismo proyecto.
3. Si no, copia la variable desde la pestaña de Postgres y pégala en el servicio web.
4. Redeploy.

### Migrar datos de SQLite a PostgreSQL (opcional)

Si ya tienes datos en `asistencia.db` y quieres pasarlos a Postgres:

1. Con la app en local (SQLite), exporta Excel desde el menú.
2. Arranca con Postgres vacío (solo tablas).
3. Vuelve a registrar usuarios / importa manualmente, **o** usa un script de migración.

Para una migración automática completa se puede usar `pgloader` o un script Python; si lo necesitas, pídelo.

### Variables de entorno mínimas en producción

| Variable       | Ejemplo                                      | Obligatorio |
|----------------|----------------------------------------------|-------------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/asistencia` | Sí (nube)   |
| `SECRET_KEY`   | `una-frase-muy-larga-y-secreta`              | Sí          |
| `PORT`         | Lo pone el hosting solo                      | Automático  |

### Local con PostgreSQL (opcional)

Si tienes Postgres instalado en tu PC:

```bash
export DATABASE_URL="postgresql://usuario:clave@localhost:5432/asistencia"
python app.py
```

Sin esa variable, sigue usando SQLite.

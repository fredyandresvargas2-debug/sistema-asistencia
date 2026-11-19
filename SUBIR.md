# Cómo subir este proyecto (paso a paso)

Esta carpeta ya está lista para GitHub + Render (o Railway).

---

## 1. Subir a GitHub

### Opción A — Desde la terminal

```bash
cd sistema_asistencia_web

git init
git add .
git commit -m "Sistema de asistencia web listo para desplegar"
git branch -M main

# Crea antes el repositorio vacío en github.com (sin README)
git remote add origin https://github.com/TU_USUARIO/sistema-asistencia.git
git push -u origin main
```

Sustituye `TU_USUARIO` por tu usuario de GitHub.

### Opción B — Arrastrar en la web

1. Entra en https://github.com/new  
2. Nombre del repo: `sistema-asistencia` (público o privado).  
3. **No** marques “Add a README”.  
4. Create repository.  
5. En la página del repo vacío: **uploading an existing file** → arrastra **todos** los archivos de esta carpeta → Commit.

---

## 2. Desplegar en Render (gratis)

1. Entra en https://render.com e inicia sesión (puedes usar GitHub).  
2. **New → Web Service**.  
3. Conecta el repositorio `sistema-asistencia`.  
4. Configura:

| Campo | Valor |
|--------|--------|
| Name | `sistema-asistencia` |
| Language | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn -b 0.0.0.0:$PORT app:app` |
| Instance | Free |

5. **New → PostgreSQL** (plan Free). Cuando esté lista, copia la **Internal Database URL**.  
6. En el Web Service → **Environment** añade:

| Key | Value |
|-----|--------|
| `DATABASE_URL` | (pega la URL de Postgres) |
| `SECRET_KEY` | cualquier frase larga secreta (ej. `MiClaveSuperSecreta2026Escuela`) |

7. Guarda y espera el deploy (2–5 min).  
8. Abre la URL que te dan, por ejemplo:  
   `https://sistema-asistencia-xxxx.onrender.com`

9. Comprueba la base de datos:  
   `https://sistema-asistencia-xxxx.onrender.com/salud`  
   Debe decir `"base_de_datos": "PostgreSQL"`.

---

## 3. Usuarios de prueba

| Usuario | Clave | Rol |
|---------|-------|-----|
| docente | 1234 | Docente |
| secretario | 1234 | Secretario |
| estudiante | 1234 | Estudiante |

**Cambia estas claves** cuando lo uses con datos reales (entra como secretario y registra usuarios nuevos, o edita en la base).

---

## Archivos que debe incluir el repositorio

```
sistema_asistencia_web/
├── app.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── .gitignore
├── README.md
├── INSTRUCCIONES.md
├── DESPLIEGUE.md
├── SUBIR.md
├── ejecutar.bat
├── ejecutar.sh
├── asistencia.db          (opcional en la nube; en local sí)
├── static/
│   └── style.css
└── templates/
    └── (todas las plantillas HTML)
```

No subas: `__pycache__/`, `.venv/`, archivos `.pyc`.

---

## Uso local (sin subir)

```bash
pip install -r requirements.txt
python app.py
```

Abre http://127.0.0.1:5000

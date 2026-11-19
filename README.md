# Sistema de Asistencia · Versión Web Multiplataforma

Funciona en **cualquier sistema operativo y dispositivo** con un navegador:

- Windows, macOS, Linux
- Android, iOS (teléfonos y tablets)
- Chromebooks, y cualquier otro con navegador moderno

Es la misma funcionalidad de la app de escritorio, pero accesible desde el navegador.

---

## Requisitos

- Python 3.5 o superior
- Conexión a internet solo para instalar dependencias la primera vez

---

## Cómo ejecutarlo

### 1. Instalar dependencias (una sola vez)

Abre una terminal en esta carpeta y ejecuta:

```bash
python -m pip install -r requirements.txt
```

(o `python3 -m pip install -r requirements.txt` en Mac/Linux)

### 2. Arrancar el servidor

```bash
python app.py
```

(o `python3 app.py`)

Verás algo como:

```
  Sistema de Asistencia - Versión Web Multiplataforma
  Abre en tu navegador:
    http://127.0.0.1:5000
```

### 3. Abrir en el navegador

- **En el mismo equipo:** abre `http://127.0.0.1:5000`
- **Desde el móvil / otra PC en la misma red Wi‑Fi:**
  1. En el equipo donde corre el servidor, averigua su IP local  
     - Windows: `ipconfig` → IPv4  
     - Mac/Linux: `ifconfig` o `ip addr` → inet
  2. En el móvil/tablet abre: `http://IP-DEL-EQUIPO:5000`  
     Ejemplo: `http://192.168.1.45:5000`

---

## Usuarios de prueba (clave: `1234`)

| Usuario      | Rol         |
|--------------|-------------|
| docente      | Docente     |
| secretario   | Secretario  |
| estudiante   | Estudiante  |

> Cambia estas claves antes de usarlo con datos reales.

---

## Funciones por rol

| Función                         | Docente | Secretario | Estudiante |
|---------------------------------|---------|------------|------------|
| Consultar asistencia            | ✅      | ✅         | Solo la suya |
| Asignar asistencia              | ✅      | ✅         | —          |
| Reporte mensual                 | —       | ✅         | —          |
| Registrar estudiante/docente/materia/carrera | — | ✅ | — |
| Descargar Excel                 | ✅      | ✅         | —          |
| Auto-registro de estudiante     | Público (sin login) | | |

---

## Datos

- Base de datos: `asistencia.db` (SQLite, se crea/actualiza sola)
- Exportación Excel: botón **Descargar Excel** en el menú

---

## Notas

- El servidor debe estar en marcha para que cualquier dispositivo pueda usarlo.
- Para uso permanente en una red, puedes dejar `python app.py` corriendo en un PC o servidor, o desplegarlo en un hosting (Render, Railway, PythonAnywhere, etc.).
- Esta versión web **reemplaza** la necesidad de crear un .exe: no hace falta instalar nada en móviles ni en otros equipos, solo un navegador.

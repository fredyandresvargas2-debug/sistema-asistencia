# Sistema de Asistencia — Instrucciones rápidas

## ¿Qué es?

Aplicación web para controlar asistencia de estudiantes.  
Funciona en **cualquier dispositivo** (PC, Mac, Android, iPhone) solo con el navegador.

---

## Uso local (en tu PC)

1. Instala Python 3.9 o superior.
2. Abre una terminal en esta carpeta.
3. Ejecuta:

```bash
pip install -r requirements.txt
python app.py
```

4. Abre en el navegador: **http://127.0.0.1:5000**

- Windows: también puedes usar `ejecutar.bat`
- Mac / Linux: `./ejecutar.sh`

### Acceso desde el móvil en la misma Wi‑Fi

1. Arranca el servidor en el PC.
2. Averigua la IP del PC (`ipconfig` en Windows, `ifconfig` o `ip addr` en Mac/Linux).
3. En el móvil abre: `http://IP-DEL-PC:5000`

---

## Usuarios de prueba

| Usuario      | Contraseña | Rol        |
|--------------|------------|------------|
| docente      | 1234       | Docente    |
| secretario   | 1234       | Secretario |
| estudiante   | 1234       | Estudiante |

**Importante:** cambia estas claves antes de usarlo con datos reales.

---

## Funciones

### Docente
- Consultar asistencia de cualquier estudiante
- Registrar asistencia por carrera y materia
- Descargar Excel

### Secretario
- Todo lo del docente
- Reporte mensual
- Registrar estudiantes, docentes, materias y carreras

### Estudiante
- Ver solo su propia asistencia
- Puede crear su cuenta desde “Registrarme como estudiante”

---

## Subir a internet (para usar desde cualquier lugar)

Lee el archivo **DESPLIEGUE.md**.

**Recomendación:** usa **Render.com** (gratis).

Pasos resumidos:
1. Sube este proyecto a GitHub.
2. En Render crea un Web Service conectado al repositorio.
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn -b 0.0.0.0:$PORT app:app`
5. Variable de entorno: `SECRET_KEY` = una frase secreta.

En unos minutos tendrás una URL pública que puedes compartir con docentes y estudiantes.

---

## Archivos importantes

| Archivo            | Para qué sirve                          |
|--------------------|-----------------------------------------|
| `app.py`           | Programa principal                      |
| `asistencia.db`    | Base de datos (se crea sola si no existe)|
| `requirements.txt` | Dependencias de Python                  |
| `DESPLIEGUE.md`    | Guía para subir a internet              |
| `README.md`        | Descripción general del proyecto        |
| `Procfile`         | Arranque en Render / Railway            |

---

## Soporte

Si algo no funciona:
1. Comprueba que Python esté instalado (`python --version` o `python3 --version`).
2. Instala de nuevo las dependencias: `pip install -r requirements.txt`
3. Asegúrate de estar en la carpeta del proyecto al ejecutar `python app.py`.

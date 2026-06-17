# 🚀 Empieza aquí (Windows)

Guía rápida para usar **Mundial Studio** en tu PC.

## 1) Tener el proyecto en tu ordenador

Si aún no lo tienes en local, abre **PowerShell** y:

```powershell
cd E:\sergi\Documents
git clone -b claude/nightclub-photo-auto-edit-mzcloz https://github.com/sergibrierton/mundial.git
cd mundial
```

> ¿Sin Git? Entra en el repositorio en GitHub, botón verde **Code → Download ZIP**,
> y descomprímelo en `E:\sergi\Documents\mundial`.

## 2) Tener Python instalado (solo una vez)

Descárgalo de **https://www.python.org/downloads/** y, al instalar,
**marca la casilla “Add Python to PATH”**. (Sirve Python 3.9 o superior.)

## 3) Abrir la app

**Haz doble clic en `INICIAR.bat`.**

- La **primera vez** instalará todo lo necesario (tarda unos minutos). No necesitas
  instalar ffmpeg por tu cuenta: viene incluido.
- Cuando termine, se abrirá sola en el navegador: **http://127.0.0.1:5000**

## 4) Usarla

1. Pega la ruta de tu carpeta de fotos/vídeos arriba y pulsa **Abrir**.
   Por ejemplo: `E:\sergi\Documents\iphone`
2. Elige un **preset** (prueba **Flash Y2K**, **Teal & Orange**, **Cyberpunk Neon**…).
3. Ajusta lo que quieras con los controles; arrastra la **marca de agua** si la usas.
4. Pulsa **Exportar carpeta…** y elige dónde guardar.

---

## ¿Prefieres por línea de comandos? (lotes automáticos)

Con el entorno activado (`.venv\Scripts\activate`):

```powershell
REM Fotos: selecciona las mejores + look + marca de agua
python auto_edit.py -i "E:\sergi\Documents\iphone" -o "E:\salida\fotos" --preset presets\flash_y2k.json --cull --text "MUNDIAL"

REM Vídeos: look + Reel 9:16 + recorte del mejor tramo
python video_edit.py -i "E:\sergi\Documents\iphone" -o "E:\salida\videos" --preset presets\teal_orange.json --aspect reel --cull --auto-trim --text "MUNDIAL"
```

## Problemas frecuentes

- **“python no se reconoce…”** → no marcaste *Add to PATH*. Reinstala Python con esa casilla.
- **Quiero reinstalar de cero** → borra la carpeta `.venv` y vuelve a ejecutar `INICIAR.bat`.
- **Una foto RAW o un vídeo da error** → cópiame el mensaje y lo arreglo.

> En macOS/Linux, en vez del `.bat` usa:  `bash iniciar.sh`

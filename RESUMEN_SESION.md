# Resumen de sesión / Traspaso para Claude Code en local

Este documento resume TODO lo construido en la sesión web para que una sesión
de **Claude Code ejecutándose en el PC** (Windows) pueda continuar y poner el
sistema en marcha con archivos reales.

---

## 1. Qué es el proyecto

Sistema de **edición automática de fotos y vídeo para una discoteca** ("Mundial").
El usuario hace fotos/vídeo en un club con una **Sony ZV-E10** (objetivo 16mm f/1.4)
y quiere: pasar una carpeta de material sin editar y recibirlo **editado con un
estilo consistente**, listo para publicar, con **marca de agua** opcional, y que
el sistema **elija la mejor toma** de cada ráfaga/clip. Hay una **interfaz visual**
para previsualizar looks y corregir a mano.

- **Repo (GitHub):** `sergibrierton/mundial`
- **Rama de trabajo:** `claude/nightclub-photo-auto-edit-mzcloz`
- **Ruta local (PC):** `E:\sergi\Documents\mundial`
- **Carpeta con el material del usuario:** `E:\sergi\Documents\iphone`
  (son archivos de la **Sony ZV-E10**: JPEG + RAW **.ARW** y vídeo **.MP4 XAVC S**;
  se transfieren a través del iPhone pero NO son archivos de iPhone).

---

## 2. Estado: qué está construido (y probado)

### Motor (`editor/`)
- `loader.py` — carga RAW (.ARW vía rawpy), JPEG/PNG/TIFF y **HEIC/HEIF** (pillow-heif);
  miniaturas rápidas; lectura de fecha EXIF.
- `adjustments.py` — ajustes de color/tono en numpy (exposición, temp/tint, contraste,
  luces/sombras/blancos/negros, vibrance/saturación, split-toning, curva, viñeta, grano)
  + auto balance de blancos y auto exposición.
- `pipeline.py` — tubería completa foto: `apply_color_look` (solo color, reutilizable en
  LUT) + `apply_look` (auto + color + efectos) + watermark + export.
- `preset.py` — carga de presets .json con valores por defecto.
- `lut.py` — lee LUTs .cube (interpolación trilineal).
- `lut_export.py` — **exporta un preset a LUT .cube** (así foto y vídeo comparten color).
- `watermark.py` — marca de agua logo PNG o texto, con posición libre (arrastrar).
- `culling.py` — selección de la mejor foto de ráfagas (nitidez=Laplaciano, exposición,
  encuadre, caras con OpenCV opcional, hash perceptual para agrupar).
- `ffmpeg_tools.py` — localiza ffmpeg (usa imageio-ffmpeg si no hay del sistema) y sondea vídeo.
- `video.py` — procesa vídeo con ffmpeg: LUT, reencuadre (Reel 9:16, feed 4:5, cuadrado,
  16:9), recorte centro/fondo-desenfocado, marca de agua, export H.264.
- `video_cull.py` — analiza clips (nitidez, estabilidad, exposición, caras) y propone el
  mejor tramo.

### Herramientas de línea de comandos
- `auto_edit.py` — edición de FOTOS por lotes (preset + marca + `--cull`).
- `cull.py` — solo selección de mejores fotos (informe CSV).
- `video_edit.py` — edición de VÍDEO por lotes (LUT + reencuadre + `--cull` + `--auto-trim`).
- `make_lut.py` — exporta preset → .cube.

### Interfaz visual
- `app.py` (Flask) + `webui/` (HTML/CSS/JS): app web local en `http://127.0.0.1:5000`.
  Previsualiza presets/LUTs en vivo, coloca la marca de agua arrastrándola, corrige
  cualquier ajuste por foto/vídeo, guarda presets y exporta la carpeta.

### Presets (`presets/`) — 9 en total
Existentes: `mundial_neon`, `mundial_warm`, `mundial_bw`.
Nuevos (basados en tendencias de nightlife 2025-26):
- `flash_y2k` — flash directo / digicam (el más en tendencia).
- `teal_orange` — cinematográfico complementario (vídeo).
- `cyberpunk_neon` — magenta/cian, potencia las luces.
- `film_35mm` — analógico cálido desvaído.
- `vibrant_pop` — color punzante para parar el scroll.
- `moody_dark` — oscuro desaturado, aire premium.

### Lanzadores
- `INICIAR.bat` (Windows, doble clic), `iniciar.sh` (mac/Linux), `EMPIEZA_AQUI.md`.

### Probado ✅
- Pipeline de fotos, culling, export con watermark (con JPEG sintéticos).
- LUT export reproduce el look (error medio 0.001).
- Pipeline de vídeo (vídeos sintéticos): cull puntúa bien, reframe, auto-trim, logo, export.
- Endpoints de la app vía curl (presets/open/render/thumb/save_preset/export) y render visual.
- Instalación limpia de `requirements.txt` en venv nuevo (resuelve sin errores).

### NO probado todavía ⚠️ (tareas para la sesión local)
- Cargar/editar **.ARW reales** de la Sony.
- **Vídeo real** de la Sony (XAVC S .MP4 / posible HEVC 4K).
- La **interfaz en un navegador real** de forma interactiva.
- HEIC end-to-end (soporte añadido pero el test se interrumpió).

---

## 3. Cómo arrancar en local (Windows)

1. Tener Python 3.9+ instalado ("Add Python to PATH").
2. Doble clic en `INICIAR.bat` (instala todo la primera vez y abre la app).
3. En la app: pegar `E:\sergi\Documents\iphone` → Abrir → elegir preset → Exportar.

O por comandos (con `.venv\Scripts\activate`):
```powershell
python auto_edit.py  -i "E:\sergi\Documents\iphone" -o "E:\salida\fotos"  --preset presets\flash_y2k.json   --cull --text "MUNDIAL"
python video_edit.py -i "E:\sergi\Documents\iphone" -o "E:\salida\videos" --preset presets\teal_orange.json --aspect reel --cull --auto-trim --text "MUNDIAL"
```

---

## 4. Ajustes de cámara ya acordados (Sony ZV-E10, 16mm f/1.4)

- **RAW + JPEG Fina, 3:2** ✓ · **Rango color sRGB** ✓
- **Modo de toma → M (Manual) + ISO Auto** (estaba en "Recall"; cambiar a M).
- **AF-C** ✓; **activar detección de cara/ojo**; área "Amplia" si se quiere más cómodo.
- **ISO Auto máx 6400** (objetivo luminoso); **compensación -0.3/-0.7 EV** (proteger luces).
- **Pendiente de confirmar en cámara:** Picture Profile **OFF**, balance de blancos **fijo
  ~3200-3400K** (mejor que automático para un lote uniforme).

---

## 5. Tareas siguientes sugeridas (para la sesión local)

1. Ejecutar `INICIAR.bat` y abrir la app; probar los 9 presets sobre **fotos .ARW reales**.
2. Procesar una carpeta de prueba con `auto_edit.py --cull` y revisar la selección.
3. Probar `video_edit.py` con un vídeo real (verificar reframe a Reel y audio).
4. Si una **.ARW** o un **vídeo** da error → diagnosticar y corregir (rawpy/ffmpeg).
5. Afinar 2-3 presets sobre fotos reales (grano, fuerza de color, recorte de sombras)
   y dejarlos como sello de la marca.
6. Exportar LUTs .cube de los presets elegidos (`make_lut.py`) para Premiere/DaVinci.
7. (Opcional) Reencuadre de vídeo con seguimiento de caras; denoise para ISO alto.

---

## 6. Convenciones

- Todo el código y la UI están en **español**.
- Trabajar en la rama `claude/nightclub-photo-auto-edit-mzcloz`; hacer commit/push al terminar.
- Dependencias en `requirements.txt` (rawpy, Pillow, numpy, Flask, imageio-ffmpeg,
  opencv-python-headless, pillow-heif). ffmpeg viene vía imageio-ffmpeg (no hace falta instalarlo aparte).

# Mundial — Edición automática de fotos y vídeo

Sistema para **editar por lotes** el material de la discoteca: le pasas una
carpeta con **fotos** (RAW `.ARW` de tu Sony o JPEG) y **vídeos** sin editar
y te devuelve material **con un estilo consistente**, listo para publicar,
con **marca de agua** si quieres. Elige **automáticamente la mejor toma** de
cada ráfaga/clip, y trae una **interfaz visual** para ajustar el look a ojo.

Fotos y vídeos comparten **exactamente el mismo color** porque el look del
preset se exporta a un **LUT `.cube`** que se aplica a ambos.

| Herramienta | Qué hace |
|-------------|----------|
| `app.py` | **Interfaz visual** (app web local): prueba presets/LUTs en vivo, coloca la marca de agua arrastrándola, corrige foto/vídeo individualmente y exporta. |
| `auto_edit.py` | Edita fotos por lotes con preset + marca de agua. `--cull` selecciona la mejor de cada ráfaga. |
| `cull.py` | Solo selección: elige la mejor foto de cada ráfaga (enfoque, exposición, encuadre, caras). |
| `video_edit.py` | Edita vídeos por lotes: look (LUT), reencuadre a redes (Reel/feed/cuadrado), recorte del mejor tramo, descarte de clips malos y marca de agua. |
| `make_lut.py` | Exporta un preset a LUT `.cube` (para vídeo o cualquier editor). |

---

## 🖥️ 0. Interfaz visual (lo más cómodo)

```bash
pip install -r requirements.txt
python app.py        # abre http://127.0.0.1:5000 en tu navegador
```

En la app puedes:
- Pegar la **ruta de tu carpeta** y ver fotos y vídeos.
- Probar **presets/LUTs en vivo** sobre tus fotos o **referencias** que subas,
  para decidir el estilo de la discoteca.
- **Arrastrar la marca de agua** (logo o texto) a donde quieras, con tamaño y
  opacidad.
- **Corregir cualquier ajuste** (exposición, color, contraste, viñeta…) de una
  foto o vídeo concreto y **guardar ese retoque** solo para esa toma.
- En vídeo: elegir **formato** (Reel 9:16, feed 4:5…) y **recorte** (con botón
  “mejor tramo ✨”).
- **Guardar tu propio preset** y **exportar** toda la carpeta con un clic.

Las herramientas de línea de comandos de abajo hacen lo mismo de forma
automática/masiva.

---

## 📸 1. Ajustes de la cámara (Sony ZV-E10)

Para que la edición automática salga lo mejor posible:

**Lo más importante: dispara en RAW.** Da el máximo margen para corregir.

- **Calidad de imagen** → `RAW` (o `RAW+JPEG Fine`)
- **Tipo de archivo RAW** → `Comprimido`
- **Relación de aspecto** → `3:2`
- **Perfil de imagen (Picture Profile)** → `OFF` (nada de S-Log)
- **Creative Look** → `STD`
- **Modo** → `M (Manual) + ISO Auto` → fijas el look y solo varía el ISO,
  así **todo el lote queda uniforme** y fácil de editar.
- **Balance de blancos** → **fijo en Kelvin (~3200–3400 K)**, no automático.
- **Exposición** → un pelín **por debajo** para no quemar focos/neón.

Sitio oscuro, por objetivo:

| | 16 mm | 50 mm f/1.8 |
|---|---|---|
| Apertura | f/2.8 (o f/2) | f/1.8–2.0 |
| Velocidad | 1/125–1/200 s | 1/160–1/250 s |
| ISO | Auto, tope 6400 | Auto, tope 6400 |

- Enfoque: `AF-C` + **detección de cara/ojo ON** + zona Amplia.
- Velocidad mínima **1/125** para congelar el movimiento.
- **Truco:** al llegar, haz una foto a un papel blanco bajo la luz
  principal; sirve de referencia de color para todo el lote.

Resumen: **RAW + Manual + ISO Auto + WB fijo + exponer algo por debajo.**

---

## ⚙️ 2. Instalación (una sola vez)

Necesitas Python 3.9+.

```bash
cd Mundial
python3 -m venv .venv && source .venv/bin/activate   # opcional pero recomendado
pip install -r requirements.txt
```

> En Windows: `py -m venv .venv` y `.venv\Scripts\activate`.

`opencv-python-headless` es opcional: solo se usa para el criterio de
**caras** al elegir la mejor foto. Si no se instala, el resto de criterios
(enfoque, exposición, encuadre) siguen funcionando.

---

## 🚀 3. Uso

### Opción A — Todo de una vez (seleccionar + editar)

```bash
python auto_edit.py -i ./fotos_raw -o ./editadas \
    --preset presets/mundial_neon.json \
    --cull \
    --logo assets/logo.png \
    --max-size 2048
```

Selecciona la mejor de cada ráfaga, aplica el look y pone el logo.

### Opción B — En dos pasos (más control)

```bash
# 1) Elegir las mejores (deja las descartadas en una subcarpeta + informe CSV)
python cull.py -i ./fotos_raw -o ./seleccionadas --move-rejects

# 2) Revisas la carpeta y editas
python auto_edit.py -i ./seleccionadas -o ./editadas \
    --preset presets/mundial_warm.json --text "MUNDIAL"
```

### Opción C — Solo editar (sin selección)

```bash
python auto_edit.py -i ./fotos_raw -o ./editadas \
    --preset presets/mundial_neon.json --text "MUNDIAL"
```

---

## 🎨 4. Presets (el "look")

En `presets/` hay tres estilos listos:

- **`mundial_neon.json`** — discoteca: contraste, sombras frías, luces
  cálidas, grano. Para ambiente de neón.
- **`mundial_warm.json`** — cálido y cinematográfico, favorecedor para piel.
- **`mundial_bw.json`** — blanco y negro con contraste y grano (reportaje).

Son archivos JSON: puedes **copiarlos y tocar los valores** para crear tu
propio estilo (cada parámetro está explicado en `editor/preset.py`). Lo más
útil de ajustar: `contrast`, `temp`, `vibrance`, `shadows`, `highlights`,
`vignette`, `grain` y el `tone_curve`.

¿Tienes un **LUT `.cube`** (de Lightroom, DaVinci o comprado)? Úsalo como
base del look:

```bash
python auto_edit.py -i ./fotos -o ./editadas \
    --preset presets/mundial_neon.json --lut assets/mi_look.cube
```

---

## 🏷️ 5. Marca de agua

- **Logo** (PNG con transparencia): `--logo assets/logo.png`
- **Texto** (si no tienes logo): `--text "MUNDIAL CLUB"`

Opciones: `--wm-pos br|bl|tr|tl|center`, `--wm-opacity 0.85`,
`--wm-scale` (logo: ancho relativo; texto: alto relativo), `--wm-margin`.

```bash
python auto_edit.py -i ./fotos -o ./editadas \
    --preset presets/mundial_neon.json \
    --logo assets/logo.png --wm-pos br --wm-scale 0.16 --wm-opacity 0.8
```

---

## 🤖 6. Cómo elige "la mejor" foto

Para cada foto calcula métricas de fotógrafo profesional y, **dentro de cada
ráfaga**, las compara y se queda con la mejor:

- **Enfoque/nitidez** — varianza del Laplaciano (lo más importante).
- **Exposición** — penaliza quemados y empastados.
- **Contraste/presencia.**
- **Caras** (si hay OpenCV): nitidez de la cara, que esté **centrada** /
  en los puntos fuertes (regla de los tercios) y que no quede cortada.

Las ráfagas se detectan agrupando fotos **consecutivas y visualmente
parecidas** (hash perceptual + tiempo de captura si está disponible).

`cull.py` genera un **informe `seleccion.csv`** con la puntuación de cada
foto para que puedas revisar por qué eligió cada una. Si no estás de acuerdo
con algún corte, ajusta `--hash-thresh` (más bajo = grupos más estrictos).

---

## 📂 7. Opciones útiles

| Opción | Para qué |
|--------|----------|
| `--max-size 2048` | Tamaño del lado largo de salida (2048 va perfecto para Instagram). `0` = resolución original. |
| `--quality 90` | Calidad JPEG. |
| `--jobs 8` | Fotos en paralelo (por defecto, núcleos − 1). |
| `--recursive` | Buscar también en subcarpetas. |
| `--suffix _mundial` | Añade un sufijo al nombre de salida. |
| `--overwrite` | Reprocesa aunque ya exista la salida. |

---

## 🎬 8. Vídeo (mismo look que las fotos)

El look del preset se hornea en un **LUT `.cube`** y se aplica al vídeo con
ffmpeg, así fotos y vídeos quedan **idénticos de color**.

```bash
# Reels verticales con el look neon, recorte del mejor tramo y logo
python video_edit.py -i ./videos -o ./videos_editados \
    --preset presets/mundial_neon.json --aspect reel \
    --cull --auto-trim --logo assets/logo.png
```

- `--aspect` → `reel`/`story`/`tiktok` (9:16), `feed` (4:5), `square` (1:1),
  `landscape` (16:9) o `keep` (original).
- `--fit crop` recorta al centro; `--fit pad` rellena con fondo desenfocado.
- `--cull` analiza y **descarta clips malos** (movidos/desenfocados/oscuros);
  ajusta el listón con `--min-score`.
- `--auto-trim` recorta cada clip a **su mejor tramo**.
- Marca de agua igual que en fotos (`--logo` / `--text` …).
- Genera un informe `analisis_video.csv` con la nota de cada clip.

> Necesita **ffmpeg**. Si no lo tienes en el sistema, `pip install
> imageio-ffmpeg` (ya está en `requirements.txt`) trae uno listo.

Exportar solo el LUT (para usarlo en DaVinci/Premiere/Lightroom):

```bash
python make_lut.py --preset presets/mundial_neon.json -o assets/neon.cube
```

---

## 🗂️ Estructura del proyecto

```
Mundial/
├── app.py                # Interfaz visual (app web local)
├── webui/                # Frontend de la interfaz (HTML/CSS/JS)
├── auto_edit.py          # Editor de FOTOS por lotes (look + marca [+ --cull])
├── cull.py               # Selección de la mejor foto de cada ráfaga
├── video_edit.py         # Editor de VÍDEO por lotes (LUT + reencuadre + cull)
├── make_lut.py           # Exporta un preset a LUT .cube
├── presets/              # Estilos (.json)
├── assets/               # Pon aquí tu logo.png / LUTs .cube
├── editor/               # Motor (RAW/JPEG, ajustes, LUT, caras, vídeo...)
└── requirements.txt
```

---

## Flujo recomendado para una noche

1. Disparas con los ajustes de la sección 1.
2. Vuelcas las `.ARW` a una carpeta, p. ej. `noche_2026_06_12/`.
3. Un solo comando:
   ```bash
   python auto_edit.py -i ./noche_2026_06_12 -o ./publicar \
       --preset presets/mundial_neon.json --cull \
       --logo assets/logo.png --max-size 2048
   ```
4. Subes lo que hay en `./publicar/`. 🎉

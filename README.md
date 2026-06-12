# Mundial — Edición fotográfica automática

Sistema para **editar por lotes** las fotos de la discoteca: le pasas una
carpeta con las fotos **sin editar** (RAW `.ARW` de tu Sony o JPEG) y te
devuelve **JPEG editados con un estilo consistente**, listos para publicar,
con la **marca de agua** de la discoteca si quieres. Además puede **elegir
automáticamente la mejor foto de cada ráfaga**.

Dos herramientas que puedes usar juntas o por separado:

| Herramienta | Qué hace |
|-------------|----------|
| `cull.py` | Detecta fotos parecidas (ráfagas) y **elige la mejor** de cada grupo (enfoque, exposición, encuadre, caras centradas). |
| `auto_edit.py` | Aplica el **look/preset** a toda la carpeta, opcional **marca de agua**, y exporta JPEG listos. Puede hacer la selección antes con `--cull`. |

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

## 🗂️ Estructura del proyecto

```
Mundial/
├── auto_edit.py          # Editor por lotes (look + marca de agua [+ --cull])
├── cull.py               # Selección de la mejor foto de cada ráfaga
├── presets/              # Estilos (.json)
├── assets/               # Pon aquí tu logo.png / LUTs .cube
├── editor/               # Motor (carga RAW/JPEG, ajustes, LUT, caras...)
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

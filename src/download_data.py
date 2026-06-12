"""Descarga los datasets históricos de partidos internacionales (martj42).

Los ficheros se guardan en data/raw/. La descarga es idempotente: si el
fichero ya existe y no se fuerza, no se vuelve a descargar.
"""

import sys
import time
import urllib.request

from config import DATA_FILES, RAW_DIR


def download(force=False):
    for name, url in DATA_FILES.items():
        dest = RAW_DIR / f"{name}.csv"
        if dest.exists() and not force:
            print(f"  [skip] {dest.name} ya existe ({dest.stat().st_size//1024} KB)")
            continue
        for attempt in range(5):
            try:
                print(f"  [down] {name}.csv ...", end=" ", flush=True)
                urllib.request.urlretrieve(url, dest)
                print(f"OK ({dest.stat().st_size//1024} KB)")
                break
            except Exception as exc:  # pragma: no cover - red
                wait = 2 ** attempt
                print(f"fallo ({exc}); reintento en {wait}s")
                time.sleep(wait)
        else:
            print(f"  [ERROR] no se pudo descargar {name}", file=sys.stderr)
            return False
    return True


if __name__ == "__main__":
    ok = download(force="--force" in sys.argv)
    sys.exit(0 if ok else 1)

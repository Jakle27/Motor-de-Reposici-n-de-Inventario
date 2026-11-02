from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile


def comando(args, cwd=None):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(
        list(map(str, args)), cwd=cwd, check=True,
        text=True, capture_output=False
    )


def capturar(args):
    return subprocess.check_output(args, text=True).strip()


def sha256(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


raiz = Path.cwd()
fecha = "2017-07-29"
commit = capturar(["git", "rev-parse", "HEAD"])
imagen = capturar(["docker", "compose", "images", "-q", "airflow"])
if not imagen:
    raise SystemExit("No se encontró la imagen de Airflow.")

archivos = [
    f"data/published/{fecha}/pronostico_baseline.csv",
    f"data/published/{fecha}/pronostico_extra_trees.csv",
    f"data/published/{fecha}/pedidos_baseline.csv",
    f"data/published/{fecha}/pedidos_extra_trees.csv",
]
for archivo in archivos:
    if not (raiz / archivo).is_file():
        raise SystemExit(f"Falta la publicación original: {archivo}")

esperados = {archivo: sha256(raiz / archivo) for archivo in archivos}
temporal = Path(tempfile.mkdtemp(prefix="reproduccion-lab1-"))
copia = temporal / "proyecto"

comando(["git", "worktree", "add", "--detach", copia, commit])
comando([
    "dvc", "pull", "data/historical.dvc",
    "data/inbox.dvc", "data/published.dvc"
], cwd=copia)

# Verificar primero que DVC recuperó exactamente lo publicado.
recuperados = {
    archivo: sha256(copia / archivo) for archivo in archivos
}
if recuperados != esperados:
    raise SystemExit(
        "Los archivos recuperados con DVC difieren de la carpeta actual. "
        "Se conserva la copia para revisión: " + str(copia)
    )

# Reconstruir desde las fuentes históricas recuperadas, con la misma imagen.
programa = (
    "from inventario.ingesta import ejecutar as ingesta; "
    "from inventario.features import ejecutar as variables; "
    "from inventario.modelo import ejecutar as modelo; "
    f"ingesta('{fecha}'); variables('{fecha}'); modelo('{fecha}')"
)
comando([
    "docker", "run", "--rm",
    "--user", f"{os.getuid()}:0",
    "-e", "PYTHONPATH=/opt/project/src",
    "-e", "OMP_NUM_THREADS=2",
    "-v", f"{copia}:/opt/project",
    "-w", "/opt/project",
    imagen, "python", "-c", programa,
])

comparacion = [{
    "archivo": archivo,
    "sha256_publicado": esperados[archivo],
    "sha256_recuperado_dvc": recuperados[archivo],
    "sha256_recalculado": sha256(copia / archivo),
    "identico": esperados[archivo] == sha256(copia / archivo),
} for archivo in archivos]

correcto = all(fila["identico"] for fila in comparacion)
evidencia = {
    "commit": commit,
    "imagen_docker": imagen,
    "fecha_corte": fecha,
    "recuperacion_dvc_identica": True,
    "reproduccion_identica": correcto,
    "archivos": comparacion,
}
destino = raiz / "evidencias"
destino.mkdir(exist_ok=True)
(destino / "reproduccion.json").write_text(
    json.dumps(evidencia, indent=2), encoding="utf-8"
)
print(json.dumps(evidencia, indent=2))

if correcto:
    comando(["git", "worktree", "remove", "--force", copia])
    temporal.rmdir()
    print("REPRODUCCIÓN CORRECTA: los cuatro CSV son idénticos.")
else:
    raise SystemExit(
        "Hay diferencias. Se conserva la copia para revisión: " + str(copia)
    )

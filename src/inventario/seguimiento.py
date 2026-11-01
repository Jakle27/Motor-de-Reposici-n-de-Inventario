from pathlib import Path
import json
import pandas as pd
import yaml
from inventario.evaluacion import medir


def ejecutar(fecha, config_path="config/producto.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    corte = pd.Timestamp(fecha).normalize()
    etiqueta = corte.strftime("%Y-%m-%d")
    carpeta = Path(config["datos"]["procesados"]) / etiqueta
    reales = pd.read_parquet(carpeta / "train.parquet")

    registros = []
    for ruta in sorted(Path("data/published").glob("*/pronostico_*.csv")):
        emision = pd.Timestamp(ruta.parent.name)
        if emision >= corte:
            continue

        pronostico = pd.read_csv(ruta)
        fechas = pd.to_datetime(pronostico["date"])
        # Todavía no existen resultados observables para esta emisión.
        claves = ["date", "store_nbr", "family"]
        disponibles = pronostico[claves].copy()
        disponibles["date"] = fechas
        if disponibles.merge(
            reales[claves], on=claves, how="inner"
        ).empty:
            continue

        metricas, _ = medir(
            pronostico,
            reales,
            config["costos"]["faltante_por_unidad"],
            config["costos"]["merma_por_unidad"],
        )
        registros.append({
            "fecha_seguimiento": etiqueta,
            "fecha_emision": ruta.parent.name,
            "modelo": pronostico["modelo"].iloc[0],
            **metricas,
        })

    destino = Path("reports/generated") / "seguimiento" / etiqueta
    destino.mkdir(parents=True, exist_ok=True)
    columnas = [
        "fecha_seguimiento", "fecha_emision", "modelo",
        "filas_esperadas", "filas_evaluadas", "cobertura_datos",
        "mae", "rmse", "wape", "sesgo",
        "costo_total", "costo_medio", "cobertura_q10_q90",
    ]
    pd.DataFrame(registros, columns=columnas).to_csv(
        destino / "metricas.csv", index=False
    )
    resumen = {
        "fecha_seguimiento": etiqueta,
        "comparaciones": len(registros),
        "estado": (
            "Evaluado" if registros
            else "Sin pronosticos anteriores con ventas observadas"
        ),
    }
    (destino / "resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return resumen

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import yaml
from inventario.ingesta import ejecutar as ingerir
from inventario.features import ejecutar as preparar
from inventario.modelo import ejecutar as entrenar


def medir(pronostico, reales, faltante, merma):
    claves = ["date", "store_nbr", "family"]
    pronostico = pronostico.copy()
    reales = reales.copy()
    pronostico["date"] = pd.to_datetime(pronostico["date"])
    reales["date"] = pd.to_datetime(reales["date"])

    unidos = pronostico.merge(
        reales[claves + ["sales"]],
        on=claves, how="left", validate="one_to_one"
    )
    observados = unidos.dropna(subset=["sales"]).copy()
    if observados.empty:
        raise ValueError("Todavía no hay ventas reales para evaluar")

    y = observados["sales"].to_numpy()
    pred = observados["prediccion"].to_numpy()
    pedido = observados["pedido_diario"].to_numpy()
    error = pred - y
    costo = (
        faltante * np.maximum(y - pedido, 0)
        + merma * np.maximum(pedido - y, 0)
    )
    observados["error"] = error
    observados["costo"] = costo

    metricas = {
        "filas_esperadas": len(unidos),
        "filas_evaluadas": len(observados),
        "cobertura_datos": len(observados) / len(unidos),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "wape": (
            float(np.abs(error).sum() / y.sum())
            if y.sum() > 0 else None
        ),
        "sesgo": float(error.mean()),
        "costo_total": float(costo.sum()),
        "costo_medio": float(costo.mean()),
        "cobertura_q10_q90": float(
            ((y >= observados["q10"].to_numpy()) &
             (y <= observados["q90"].to_numpy())).mean()
        ),
    }
    return metricas, observados


def ejecutar(config_path="config/producto.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    horizonte = config["pronostico"]["horizonte_dias"]
    faltante = config["costos"]["faltante_por_unidad"]
    merma = config["costos"]["merma_por_unidad"]
    reportes = Path("reports/generated")
    reportes.mkdir(parents=True, exist_ok=True)
    registros = []
    fechas_seguimiento = []

    for fecha in config["evaluacion"]["cortes"]:
        print(f"\n=== Corte {fecha} ===", flush=True)
        # Reconstruir cada corte desde sus fuentes disponibles.
        ingerir(fecha, config_path)
        preparar(fecha, config_path)
        entrenar(fecha, config_path)

        # Ventas del último día del horizonte disponibles al día siguiente.
        seguimiento = (
            pd.Timestamp(fecha) + pd.Timedelta(days=horizonte)
        ).strftime("%Y-%m-%d")
        fechas_seguimiento.append(seguimiento)
        carpeta_reales = ingerir(seguimiento, config_path)
        reales = pd.read_parquet(carpeta_reales / "train.parquet")

        for nombre in ["baseline", "extra_trees"]:
            ruta = Path("data/published") / fecha
            pronostico = pd.read_csv(
                ruta / f"pronostico_{nombre}.csv"
            )
            metricas, detalle = medir(
                pronostico, reales, faltante, merma
            )
            registros.append({
                "fecha_corte": fecha,
                "fecha_seguimiento": seguimiento,
                "modelo": nombre,
                **metricas,
            })
            detalle.to_parquet(
                reportes / f"seguimiento_{fecha}_{nombre}.parquet",
                index=False,
            )

        # Guardar avances aunque un corte posterior falle.
        pd.DataFrame(registros).to_csv(
            reportes / "comparacion_cortes.csv", index=False
        )

    tabla = pd.DataFrame(registros)
    resumen = tabla.groupby("modelo", as_index=False).agg(
        costo_total=("costo_total", "sum"),
        mae_promedio=("mae", "mean"),
        rmse_promedio=("rmse", "mean"),
        wape_promedio=("wape", "mean"),
        cobertura_intervalo=("cobertura_q10_q90", "mean"),
        cobertura_datos_minima=("cobertura_datos", "min"),
    )
    resumen.to_csv(reportes / "comparacion_modelos.csv", index=False)
    costos = resumen.set_index("modelo")["costo_total"]
    costo_base = float(costos["baseline"])
    costo_ml = float(costos["extra_trees"])
    mejora = (
        (costo_base - costo_ml) / costo_base
        if costo_base > 0 else None
    )
    completos = bool((tabla["cobertura_datos"] == 1).all())
    promover = (
        completos and mejora is not None
        and mejora >= config["evaluacion"]["mejora_minima_costo"]
    )
    decision = {
        "modelo_recomendado": "extra_trees" if promover else "baseline",
        "mejora_relativa_costo_ml": mejora,
        "mejora_minima_exigida": config["evaluacion"]["mejora_minima_costo"],
        "evaluacion_completa": completos,
        "evidencia_disponible_desde": max(fechas_seguimiento),
        "alcance": (
            "Seleccion retrospectiva. Aplicar solo en emisiones posteriores "
            "a la disponibilidad de toda esta evidencia; no cambiar "
            "pronosticos publicados anteriormente."
        ),
    }
    (reportes / "seleccion.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n=== Comparación temporal ===")
    print(resumen.to_string(index=False))
    print("\n=== Decisión ===")
    print(json.dumps(decision, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/producto.yaml")
    args = parser.parse_args()
    ejecutar(args.config)

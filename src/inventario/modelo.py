from pathlib import Path
import argparse
import json
import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor

VARIABLES = [
    "store_nbr", "familia_codigo", "lag_7", "lag_14", "lag_28",
    "dia_semana", "mes", "dia_mes", "tendencia",
]


def matriz(tabla, familias):
    x = tabla.copy()
    x["familia_codigo"] = x["family"].map(familias).fillna(-1)
    return x[VARIABLES].fillna(0).astype(float)


def baseline(tabla):
    return tabla["lag_7"].fillna(
        tabla[["lag_14", "lag_28"]].mean(axis=1)
    ).fillna(0).clip(lower=0).to_numpy()


def escala(tabla):
    return tabla[["lag_7", "lag_14", "lag_28"]].mean(
        axis=1
    ).fillna(1).clip(lower=1).to_numpy()


def ejecutar(fecha, config_path="config/producto.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    corte = pd.Timestamp(fecha).normalize()
    etiqueta = corte.strftime("%Y-%m-%d")
    carpeta = Path(config["datos"]["procesados"]) / etiqueta

    entrenamiento = pd.read_parquet(carpeta / "entrenamiento.parquet")
    futuro = pd.read_parquet(carpeta / "futuro.parquet")
    entrenamiento["date"] = pd.to_datetime(entrenamiento["date"])

    # Siete días reservados: no participan en el ajuste del modelo.
    inicio_calibracion = corte - pd.Timedelta(days=7)
    ajuste = entrenamiento.loc[
        entrenamiento["date"] < inicio_calibracion
    ].copy()
    calibracion = entrenamiento.loc[
        entrenamiento["date"] >= inicio_calibracion
    ].copy()

    if ajuste.empty or calibracion.empty or futuro.empty:
        raise ValueError("Datos insuficientes para ajustar y calibrar")

    familias = {
        nombre: i for i, nombre in
        enumerate(sorted(entrenamiento["family"].unique()))
    }
    semilla = config["pronostico"]["semilla"]

    # Límite reproducible para reducir tiempo y memoria.
    muestra = ajuste.sample(
        n=min(len(ajuste), 180000), random_state=semilla
    )
    modelo = ExtraTreesRegressor(
        n_estimators=60,
        max_depth=18,
        min_samples_leaf=8,
        random_state=semilla,
        n_jobs=2,
    )

    print(f"Ajustando Extra Trees con {len(muestra):,} filas...", flush=True)
    modelo.fit(matriz(muestra, familias), muestra["sales"])

    faltante = float(config["costos"]["faltante_por_unidad"])
    merma = float(config["costos"]["merma_por_unidad"])
    if faltante <= 0 or merma <= 0:
        raise ValueError("Los costos deben ser positivos")
    cuantil_pedido = faltante / (faltante + merma)

    salida = Path("data/published") / etiqueta
    salida.mkdir(parents=True, exist_ok=True)
    artefactos = Path("models") / etiqueta
    artefactos.mkdir(parents=True, exist_ok=True)

    predicciones = {
        "baseline": (
            baseline(calibracion),
            baseline(futuro),
        ),
        "extra_trees": (
            modelo.predict(matriz(calibracion, familias)).clip(min=0),
            modelo.predict(matriz(futuro, familias)).clip(min=0),
        ),
    }

    parametros = {}
    for nombre, (pred_cal, pred_fut) in predicciones.items():
        # Residuos normalizados: la escala depende solo de ventas pasadas.
        residuos = (
            calibracion["sales"].to_numpy() - pred_cal
        ) / escala(calibracion)
        tabla_residuos = pd.DataFrame({
            "family": calibracion["family"].to_numpy(),
            "residuo": residuos,
        })
        cuantiles = {}
        for columna, q in [
            ("q10", 0.10), ("q50", 0.50),
            ("q90", 0.90), ("pedido_diario", cuantil_pedido)
        ]:
            cuantiles[columna] = (
                tabla_residuos.groupby("family")["residuo"]
                .quantile(q).to_dict()
            )

        resultado = futuro[["date", "store_nbr", "family"]].copy()
        resultado["fecha_corte"] = etiqueta
        resultado["modelo"] = nombre
        resultado["prediccion"] = pred_fut
        for columna, por_familia in cuantiles.items():
            ajuste_residual = futuro["family"].map(
                por_familia
            ).fillna(float(np.quantile(residuos, {
                "q10": 0.10, "q50": 0.50, "q90": 0.90,
                "pedido_diario": cuantil_pedido,
            }[columna]))).to_numpy()
            resultado[columna] = np.maximum(
                0, pred_fut + ajuste_residual * escala(futuro)
            )

        resultado.to_csv(
            salida / f"pronostico_{nombre}.csv", index=False
        )
        pedidos = resultado.groupby(
            ["store_nbr", "family"], as_index=False
        ).agg(pedido_sugerido=("pedido_diario", "sum"))
        pedidos["fecha_corte"] = etiqueta
        pedidos["modelo"] = nombre
        pedidos.to_csv(salida / f"pedidos_{nombre}.csv", index=False)
        parametros[nombre] = cuantiles
        print(f"{nombre}: {len(resultado):,} pronósticos; "
              f"{len(pedidos):,} pedidos", flush=True)

    joblib.dump(
        {
            "modelo": modelo,
            "familias": familias,
            "variables": VARIABLES,
            "calibracion": parametros,
            "configuracion": config,
            "fecha_corte": etiqueta,
        },
        artefactos / "modelo.joblib",
    )
    resumen = {
        "fecha_corte": etiqueta,
        "inicio_calibracion": str(inicio_calibracion.date()),
        "filas_ajuste": len(muestra),
        "filas_calibracion": len(calibracion),
        "cuantil_pedido": cuantil_pedido,
        "semilla": semilla,
        "seleccion": "Pendiente de evaluacion temporal",
    }
    (salida / "modelo.json").write_text(
        json.dumps(resumen, indent=2), encoding="utf-8"
    )
    print(f"Resultados: {salida}")
    print("Modelo guardado. Falta evaluar antes de seleccionar ganador.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fecha", required=True)
    parser.add_argument("--config", default="config/producto.yaml")
    args = parser.parse_args()
    ejecutar(args.fecha, args.config)

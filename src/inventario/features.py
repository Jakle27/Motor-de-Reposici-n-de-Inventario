from pathlib import Path
import argparse
import pandas as pd
import yaml

CLAVES = ["store_nbr", "family"]


def construir(ventas, corte, horizonte=7):
    corte = pd.Timestamp(corte).normalize()
    if not 1 <= horizonte <= 7:
        raise ValueError("Este diseño admite horizontes de 1 a 7 días")

    ventas = ventas.copy()
    ventas["date"] = pd.to_datetime(ventas["date"])
    ventas = ventas.loc[ventas["date"] < corte]

    if ventas.empty:
        raise ValueError("No hay ventas anteriores al corte")
    if ventas.duplicated(CLAVES + ["date"]).any():
        raise ValueError("Claves de ventas duplicadas")

    # Ventana de entrenamiento para reducir memoria y tiempo.
    inicio = corte - pd.Timedelta(days=365)
    historia = ventas.loc[
        ventas["date"] >= inicio - pd.Timedelta(days=28),
        CLAVES + ["date", "sales"]
    ]
    pares = ventas[CLAVES].drop_duplicates()
    fechas = pd.DataFrame({
        "date": pd.date_range(
            inicio, corte + pd.Timedelta(days=horizonte - 1)
        )
    })
    panel = pares.merge(fechas, how="cross")
    panel = panel.merge(
        historia, on=CLAVES + ["date"], how="left",
        validate="one_to_one"
    )

    # Unir por fecha exacta evita confundir filas ausentes con días.
    for dias in [7, 14, 28]:
        retraso = historia.rename(columns={"sales": f"lag_{dias}"})
        retraso["date"] = retraso["date"] + pd.Timedelta(days=dias)
        panel = panel.merge(
            retraso, on=CLAVES + ["date"], how="left",
            validate="one_to_one"
        )

    panel["dia_semana"] = panel["date"].dt.day_of_week
    panel["mes"] = panel["date"].dt.month
    panel["dia_mes"] = panel["date"].dt.day
    panel["tendencia"] = (
        panel["date"] - pd.Timestamp("2013-01-01")
    ).dt.days

    entrenamiento = panel.loc[
        (panel["date"] < corte) & panel["sales"].notna()
    ].copy()
    futuro = panel.loc[panel["date"] >= corte].copy()

    # No se convierten observaciones ausentes en ventas cero.
    return entrenamiento, futuro


def ejecutar(fecha, config_path="config/producto.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    corte = pd.Timestamp(fecha).strftime("%Y-%m-%d")
    carpeta = Path(config["datos"]["procesados"]) / corte
    ventas = pd.read_parquet(carpeta / "train.parquet")
    entrenamiento, futuro = construir(
        ventas, corte, config["pronostico"]["horizonte_dias"]
    )
    entrenamiento.to_parquet(carpeta / "entrenamiento.parquet", index=False)
    futuro.to_parquet(carpeta / "futuro.parquet", index=False)

    print(f"Entrenamiento: {len(entrenamiento):,} filas")
    print(f"Pronóstico: {len(futuro):,} filas")
    print(f"Desde {futuro['date'].min().date()} "
          f"hasta {futuro['date'].max().date()}")
    print("Variables preparadas sin utilizar ventas desde el corte.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fecha", required=True)
    parser.add_argument("--config", default="config/producto.yaml")
    args = parser.parse_args()
    ejecutar(args.fecha, args.config)

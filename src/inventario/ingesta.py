from pathlib import Path
import argparse
import json
import pandas as pd
import yaml

CLAVES = {
    "train": ["date", "store_nbr", "family"],
    "transactions": ["date", "store_nbr"],
    "oil": ["date"],
}

COLUMNAS = {
    "train": ["date", "store_nbr", "family", "sales", "onpromotion"],
    "transactions": ["date", "store_nbr", "transactions"],
    "oil": ["date", "dcoilwtico"],
}


def validar(tabla, fuente, corte, tiendas):
    faltantes = set(COLUMNAS[fuente]) - set(tabla.columns)
    if faltantes:
        raise ValueError(f"{fuente}: faltan columnas {sorted(faltantes)}")

    tabla = tabla.copy()
    tabla["date"] = pd.to_datetime(tabla["date"], errors="raise")

    if tabla[CLAVES[fuente]].isna().any().any():
        raise ValueError(f"{fuente}: claves vacías")
    if tabla.duplicated(CLAVES[fuente]).any():
        raise ValueError(f"{fuente}: claves duplicadas dentro del archivo")
    if (tabla["date"] > corte).any():
        raise ValueError(f"{fuente}: observaciones posteriores al corte")

    if "store_nbr" in tabla:
        if not tabla["store_nbr"].isin(tiendas).all():
            raise ValueError(f"{fuente}: tiendas desconocidas")

    numericas = {
        "train": ["sales", "onpromotion"],
        "transactions": ["transactions"],
        "oil": ["dcoilwtico"],
    }[fuente]

    for columna in numericas:
        valores = pd.to_numeric(tabla[columna], errors="raise")
        # Petróleo ausente es una situación esperada del origen.
        if fuente != "oil" and valores.isna().any():
            raise ValueError(f"{fuente}: valores vacíos en {columna}")
        if ((valores < 0) | valores.isin([float("inf"), -float("inf")])).any():
            raise ValueError(f"{fuente}: valores inválidos en {columna}")
        tabla[columna] = valores

    return tabla


def ejecutar(fecha, config_path="config/producto.yaml"):
    config = yaml.safe_load(Path(config_path).read_text())
    corte = pd.Timestamp(fecha).normalize()
    historico = Path(config["datos"]["historico"])
    bandeja = Path(config["datos"]["bandeja"])
    cierre = pd.Timestamp(config["simulacion"]["fin_historico"])

    if corte < cierre:
        raise ValueError("El corte es anterior al histórico disponible")

    tiendas = pd.read_parquet(historico / "stores.parquet")
    if tiendas["store_nbr"].isna().any() or tiendas["store_nbr"].duplicated().any():
        raise ValueError("Catálogo de tiendas inválido")

    manifiesto = pd.read_csv(bandeja / "manifest.csv")
    manifiesto["disponible_desde"] = pd.to_datetime(
        manifiesto["disponible_desde"], errors="raise"
    )
    manifiesto["version"] = pd.to_numeric(
        manifiesto["version"], errors="raise"
    )
    if manifiesto[["fuente", "disponible_desde", "version", "archivo"]].isna().any().any():
        raise ValueError("Manifiesto con campos vacíos")
    if not manifiesto["fuente"].isin(CLAVES).all():
        raise ValueError("Fuente desconocida en el manifiesto")
    if manifiesto.duplicated(["fuente", "disponible_desde", "version"]).any():
        raise ValueError("Orden de versiones ambiguo en el manifiesto")

    disponibles = manifiesto.loc[
        manifiesto["disponible_desde"] <= corte
    ].sort_values(["disponible_desde", "version"])

    # Validar todas las fuentes antes de escribir resultados.
    resultados = {}
    resumen = {}
    for fuente, claves in CLAVES.items():
        inicial = validar(
            pd.read_parquet(historico / f"{fuente}.parquet"),
            fuente, cierre, tiendas["store_nbr"]
        )
        partes = [inicial]
        llegadas = disponibles.loc[disponibles["fuente"] == fuente]

        for registro in llegadas.itertuples(index=False):
            ruta = (bandeja / registro.archivo).resolve()
            if not ruta.is_relative_to(bandeja.resolve()):
                raise ValueError("Archivo fuera de la bandeja")
            lote = validar(
                pd.read_csv(ruta), fuente,
                registro.disponible_desde, tiendas["store_nbr"]
            )
            partes.append(lote)

        # Una corrección sustituye el registro anterior con la misma clave.
        tabla = pd.concat(partes, ignore_index=True)
        tabla = tabla.drop_duplicates(claves, keep="last")
        tabla = tabla.sort_values(claves).reset_index(drop=True)
        resultados[fuente] = tabla
        resumen[fuente] = {
            "filas": len(tabla),
            "archivos_llegada": len(llegadas),
            "ultima_observacion": tabla["date"].max().strftime("%Y-%m-%d"),
        }

    destino = Path(config["datos"]["procesados"]) / corte.strftime("%Y-%m-%d")
    destino.mkdir(parents=True, exist_ok=True)
    for fuente, tabla in resultados.items():
        tabla.to_parquet(destino / f"{fuente}.parquet", index=False)

    tiendas.to_parquet(destino / "stores.parquet", index=False)
    pd.read_parquet(historico / "holidays_events.parquet").to_parquet(
        destino / "holidays_events.parquet", index=False
    )
    (destino / "ingesta.json").write_text(
        json.dumps({"corte": str(corte.date()), "fuentes": resumen},
                   indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fecha", required=True)
    parser.add_argument("--config", default="config/producto.yaml")
    args = parser.parse_args()
    ejecutar(args.fecha, args.config)

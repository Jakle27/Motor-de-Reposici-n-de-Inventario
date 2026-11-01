from pathlib import Path
import pandas as pd
import yaml

config = yaml.safe_load(Path("config/producto.yaml").read_text())
datos = config["datos"]
sim = config["simulacion"]
raw = Path(datos["originales"])
historico = Path(datos["historico"])
bandeja = Path(datos["bandeja"])

# Evitar sobrescribir una simulación existente.
if historico.exists() or bandeja.exists():
    raise SystemExit(
        "La simulación ya existe. Se conserva sin modificaciones."
    )

fin_historico = pd.Timestamp(sim["fin_historico"])
inicio = pd.Timestamp(sim["inicio"])
fin = pd.Timestamp(sim["fin"])

fuentes = {
    "train": sim["retraso_ventas_dias"],
    "transactions": sim["retraso_transacciones_dias"],
    "oil": sim["retraso_petroleo_dias"],
}

# Leer y comprobar los archivos antes de escribir.
tablas = {}
for fuente in [*fuentes, "stores", "holidays_events"]:
    tabla = pd.read_csv(raw / f"{fuente}.csv")
    if fuente != "stores":
        tabla["date"] = pd.to_datetime(tabla["date"], errors="raise")
    tablas[fuente] = tabla

historico.mkdir(parents=True)
bandeja.mkdir(parents=True)
manifiesto = []

for fuente, retraso in fuentes.items():
    tabla = tablas[fuente]
    disponible = tabla["date"] + pd.Timedelta(days=retraso)

    # El histórico incluye solo lo disponible al cierre inicial.
    inicial = tabla.loc[disponible <= fin_historico]
    inicial.to_parquet(historico / f"{fuente}.parquet", index=False)

    # Incluye llegadas tardías de observaciones anteriores al inicio.
    futuras = tabla.loc[
        (disponible > fin_historico) & (tabla["date"] <= fin)
    ].copy()
    futuras["_llegada"] = disponible.loc[futuras.index]

    carpeta = bandeja / fuente
    carpeta.mkdir()

    for llegada, lote in futuras.groupby("_llegada", sort=True):
        ruta = carpeta / f"{llegada:%Y-%m-%d}__v1.csv"
        lote.drop(columns="_llegada").to_csv(ruta, index=False)
        manifiesto.append({
            "fuente": fuente,
            "disponible_desde": llegada.strftime("%Y-%m-%d"),
            "version": 1,
            "archivo": ruta.relative_to(bandeja).as_posix(),
            "filas": len(lote),
        })

    print(f"{fuente}: {len(inicial):,} filas históricas")

# Supuesto: catálogo de tiendas y calendario conocidos al corte inicial.
tablas["stores"].to_parquet(
    historico / "stores.parquet", index=False
)
tablas["holidays_events"].to_parquet(
    historico / "holidays_events.parquet", index=False
)

pd.DataFrame(manifiesto).sort_values(
    ["disponible_desde", "fuente"]
).to_csv(bandeja / "manifest.csv", index=False)

print(f"Bandeja creada: {len(manifiesto)} archivos de llegada.")
print(f"Periodo operativo: {inicio.date()} a {fin.date()}")
print("Los archivos originales permanecen intactos.")

import hashlib
import pandas as pd
import pytest
import yaml
from inventario.ingesta import ejecutar
from inventario.features import construir


@pytest.fixture
def origen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    historico = tmp_path / "historical"
    bandeja = tmp_path / "inbox"
    historico.mkdir()
    bandeja.mkdir()

    def venta(fecha, cantidad):
        return pd.DataFrame({
            "date": pd.to_datetime([fecha]),
            "store_nbr": [1],
            "family": ["GROCERY I"],
            "sales": [cantidad],
            "onpromotion": [0],
        })

    venta("2017-05-30", 10).to_parquet(
        historico / "train.parquet", index=False
    )
    pd.DataFrame({
        "date": pd.to_datetime(["2017-05-29"]),
        "store_nbr": [1], "transactions": [5],
    }).to_parquet(historico / "transactions.parquet", index=False)
    pd.DataFrame({
        "date": pd.to_datetime(["2017-05-30"]),
        "dcoilwtico": [50.0],
    }).to_parquet(historico / "oil.parquet", index=False)
    pd.DataFrame({"store_nbr": [1]}).to_parquet(
        historico / "stores.parquet", index=False
    )
    pd.DataFrame({"date": pd.to_datetime(["2017-12-25"])}).to_parquet(
        historico / "holidays_events.parquet", index=False
    )

    venta("2017-05-31", 20).to_csv(bandeja / "original.csv", index=False)
    venta("2017-05-31", 25).to_csv(bandeja / "correccion.csv", index=False)
    pd.DataFrame([
        {
            "fuente": "train", "disponible_desde": "2017-06-01",
            "version": 1, "archivo": "original.csv",
        },
        {
            "fuente": "train", "disponible_desde": "2017-06-03",
            "version": 2, "archivo": "correccion.csv",
        },
    ]).to_csv(bandeja / "manifest.csv", index=False)

    config = {
        "datos": {
            "historico": str(historico),
            "bandeja": str(bandeja),
            "procesados": str(tmp_path / "processed"),
        },
        "simulacion": {"fin_historico": "2017-05-31"},
    }
    ruta = tmp_path / "config.yaml"
    ruta.write_text(yaml.safe_dump(config))
    return ruta, bandeja


def test_correccion_solo_desde_su_llegada(origen):
    config, _ = origen
    antes = pd.read_parquet(
        ejecutar("2017-06-02", config) / "train.parquet"
    )
    despues = pd.read_parquet(
        ejecutar("2017-06-03", config) / "train.parquet"
    )
    assert antes.loc[antes["date"] == "2017-05-31", "sales"].iloc[0] == 20
    assert despues.loc[despues["date"] == "2017-05-31", "sales"].iloc[0] == 25
    assert len(antes) == len(despues) == 2


def test_ingesta_idempotente_y_bandeja_intacta(origen):
    config, bandeja = origen

    def hashes():
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in bandeja.iterdir() if p.is_file()
        }

    originales = hashes()
    destino = ejecutar("2017-06-03", config)
    primera = pd.read_parquet(destino / "train.parquet")
    ejecutar("2017-06-03", config)
    segunda = pd.read_parquet(destino / "train.parquet")
    pd.testing.assert_frame_equal(primera, segunda)
    assert hashes() == originales


def test_features_ignora_ventas_desde_el_corte():
    fechas = pd.date_range("2017-04-01", "2017-06-21")
    ventas = pd.DataFrame({
        "date": fechas, "store_nbr": 1,
        "family": "GROCERY I", "sales": 10.0,
    })
    _, futuro1 = construir(ventas, "2017-06-15")
    ventas.loc[ventas["date"] >= "2017-06-15", "sales"] = 999999
    _, futuro2 = construir(ventas, "2017-06-15")
    pd.testing.assert_frame_equal(futuro1, futuro2)
    assert futuro1["sales"].isna().all()

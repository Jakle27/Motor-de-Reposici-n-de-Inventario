import pandas as pd
import pytest
from inventario.ingesta import validar


def ventas():
    return pd.DataFrame({
        "date": ["2017-06-14"],
        "store_nbr": [1],
        "family": ["GROCERY I"],
        "sales": [10.0],
        "onpromotion": [0],
    })


def comprobar(tabla, fuente="train"):
    return validar(
        tabla, fuente, pd.Timestamp("2017-06-15"),
        pd.Series([1, 2])
    )


def test_acepta_ventas_validas():
    resultado = comprobar(ventas())
    assert resultado["sales"].iloc[0] == 10
    assert resultado["date"].iloc[0] == pd.Timestamp("2017-06-14")


def test_rechaza_observacion_futura():
    tabla = ventas()
    tabla["date"] = "2017-06-16"
    with pytest.raises(ValueError, match="posteriores"):
        comprobar(tabla)


def test_rechaza_duplicados():
    tabla = pd.concat([ventas(), ventas()], ignore_index=True)
    with pytest.raises(ValueError, match="duplicadas"):
        comprobar(tabla)


def test_rechaza_tienda_desconocida():
    tabla = ventas()
    tabla["store_nbr"] = 999
    with pytest.raises(ValueError, match="desconocidas"):
        comprobar(tabla)


@pytest.mark.parametrize("valor", [-1, float("inf"), float("nan")])
def test_rechaza_ventas_invalidas(valor):
    tabla = ventas()
    tabla["sales"] = valor
    with pytest.raises(ValueError):
        comprobar(tabla)


def test_acepta_petroleo_ausente():
    tabla = pd.DataFrame({
        "date": ["2017-06-14"],
        "dcoilwtico": [float("nan")],
    })
    assert comprobar(tabla, "oil")["dcoilwtico"].isna().all()


def test_rechaza_columna_faltante():
    with pytest.raises(ValueError, match="faltan columnas"):
        comprobar(ventas().drop(columns="sales"))

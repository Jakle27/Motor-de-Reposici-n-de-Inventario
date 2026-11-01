from datetime import timedelta
import pendulum
from airflow.sdk import dag, task, get_current_context
from airflow.exceptions import AirflowSkipException


@dag(
    dag_id="motor_reposicion",
    start_date=pendulum.datetime(2017, 6, 1, tz="UTC"),
    schedule=timedelta(days=7),
    catchup=False,
    max_active_runs=1,
    tags=["laboratorio1", "inventario"],
)
def motor_reposicion():

    @task
    def fecha_corte():
        import pandas as pd
        import yaml
        from pathlib import Path

        contexto = get_current_context()
        configuracion = contexto["dag_run"].conf or {}
        fecha = configuracion.get("fecha")
        if not fecha:
            fecha = contexto["data_interval_start"].strftime("%Y-%m-%d")

        config = yaml.safe_load(Path("config/producto.yaml").read_text())
        corte = pd.Timestamp(fecha).normalize()
        inicio = pd.Timestamp(config["simulacion"]["inicio"])
        fin = pd.Timestamp(config["simulacion"]["fin"])

        if not inicio <= corte <= fin:
            raise AirflowSkipException(
                "Corte fuera del periodo simulado. "
                "Para ejecución manual indicar conf: fecha."
            )
        return corte.strftime("%Y-%m-%d")

    @task
    def ingesta(fecha):
        from inventario.ingesta import ejecutar
        ejecutar(fecha)
        return fecha

    @task
    def variables(fecha):
        from inventario.features import ejecutar
        ejecutar(fecha)
        return fecha

    @task
    def pronostico_y_pedido(fecha):
        from inventario.modelo import ejecutar
        ejecutar(fecha)
        return fecha

    @task
    def seguimiento(fecha):
        from inventario.seguimiento import ejecutar
        ejecutar(fecha)
        return fecha

    fecha = ingesta(fecha_corte())
    control = seguimiento(fecha)
    publicacion = pronostico_y_pedido(variables(fecha))
    control >> publicacion


motor_reposicion()

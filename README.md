# Motor de Reposición de Inventario

**Autora:** Jackeline Estrella León Sura
**Curso:** Product Development — Laboratorio 1

Producto que genera pronósticos diarios a siete días y pedidos sugeridos
por tienda y familia. Integra Git, DVC, Airflow 3, Docker Compose y pytest.

## Requisitos y datos

Docker con Docker Compose, Python 3.11 y DVC.
En Windows se utiliza Ubuntu mediante WSL 2.

Fuente: https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data

Colocar en data/raw/ los archivos train.csv, stores.csv,
holidays_events.csv, oil.csv y transactions.csv.
No se utilizan test.csv ni sample_submission.csv.

## Reconstrucción desde cero

Clonar el repositorio y entrar en su carpeta:

    git clone https://github.com/Jakle27/Motor-de-Reposici-n-de-Inventario.git
    cd Motor-de-Reposici-n-de-Inventario

La versión final se identificará con el tag entrega-lab1:

    git checkout entrega-lab1

Crear .env con AIRFLOW_UID igual al resultado del comando id -u.
Construir la imagen:

    docker compose build

Si no existen data/historical ni data/inbox, preparar las fuentes:

    docker compose run --rm --no-deps airflow python scripts/preparar_fuentes.py

El simulador no modifica los CSV originales ni sobrescribe una simulación
existente. El flujo de procesamiento solo lee el histórico y la bandeja.

## Recuperación con DVC

Como alternativa a reconstruir, ejecutar:

    dvc pull

El remoto actual es local: /home/jels/dvc-remote/lab1.
Para recuperar versiones exactas desde otro equipo se necesita una copia
completa de ese remoto y configurar su ubicación:

    dvc remote modify --local storage /ruta/a/la/copia/del/remoto
    dvc pull

La reconstrucción desde los CSV originales no requiere ese remoto.

## Airflow

    docker compose up -d
    docker compose exec airflow airflow dags list-import-errors
    docker compose exec airflow airflow dags unpause motor_reposicion
    docker compose exec airflow airflow dags trigger motor_reposicion --conf '{"fecha":"2017-07-29"}'

Interfaz: http://localhost:8080

Consultar el estado:

    docker compose exec airflow airflow dags list-runs motor_reposicion --output json

El DAG contiene cinco tareas: fecha_corte, ingesta, variables, seguimiento
y pronostico_y_pedido. Su frecuencia es de siete días. Las fechas fuera del
periodo simulado se omiten. Para reprocesar un corte pasado se crea una
ejecución manual con su fecha en conf.

La configuración standalone y el acceso local sin contraseña se utilizan
para esta demostración académica.

## Modelos, evaluación y resultados

    docker compose exec airflow python -m inventario.evaluacion

Se comparan baseline estacional y Extra Trees en los cortes 2017-06-15,
2017-07-01 y 2017-07-15, con el mismo horizonte de siete días.

La evaluación inicial en Conda obtuvo:
- MAE: baseline 80.80; Extra Trees 62.33.
- WAPE: baseline 16.34 %; Extra Trees 12.75 %.
- Reducción del costo ilustrativo: 36.74 % con Extra Trees.
- Cobertura del intervalo de Extra Trees: 75.51 %.
- Cobertura de datos para evaluación: 100 %.

Los resultados pueden variar entre Conda y Docker por las versiones de
dependencias. La comparación de Docker debe obtenerse con el comando anterior.

Reportes:
- reports/generated/comparacion_cortes.csv
- reports/generated/comparacion_modelos.csv
- reports/generated/seleccion.json
- reports/generated/seguimiento/FECHA/metricas.csv

Procesados: data/processed/FECHA/
Modelos: models/FECHA/modelo.joblib
Pronósticos: data/published/FECHA/pronostico_MODELO.csv
Pedidos: data/published/FECHA/pedidos_MODELO.csv

## Criterio de selección

Se recomienda Extra Trees si reduce el costo agregado al menos un 1 %
y todos los cortes tienen datos completos. En caso contrario se mantiene
el baseline como referencia.

La evidencia de selección está disponible desde 2017-07-22; no puede
aplicarse retrospectivamente. Se publican ambos candidatos identificados.
No se ha implementado un registro automático de promoción del modelo vigente.

## Pruebas

    python -m pip install -r requirements-airflow.txt pytest
    python -m pytest -q

Se ejecutaron 12 pruebas: validaciones, correcciones según llegada,
idempotencia de ingesta, bandeja intacta y exclusión de ventas futuras.
GitHub Actions ejecuta las pruebas en Pull Requests y ramas configuradas.

## Versionado y reproducción

Git conserva código y configuración. DVC conserva datos originales,
históricos, bandeja, procesados, modelos, pronósticos y reportes.

Después de generar resultados:

    dvc add data/processed data/published models reports/generated
    dvc push

Guardar los punteros actualizados mediante un commit.

Para reproducir una publicación pasada: crear una copia de trabajo en
su commit, recuperar sus datos con DVC, ejecutar el mismo corte con la
configuración y entorno de ese commit y comparar los SHA-256 de los CSV.
La evidencia de reproducción se incorpora después de ejecutar esta prueba.

## Supuestos y limitaciones

Histórico disponible al 2017-05-31; operación simulada del 2017-06-01
al 2017-08-15. Retrasos: ventas un día, transacciones dos y petróleo uno.
Catálogo y calendario considerados conocidos al cierre inicial.

El modelo usa rezagos de ventas y calendario básico. No usa todavía
petróleo, transacciones, promociones ni eventos como predictores.

Los cuantiles se calibran empíricamente por familia con siete días.
No garantizan cobertura nominal del 80 %.

Los costos faltante=5 y merma=1 son supuestos ilustrativos configurables.
El cuantil del pedido es costo_faltante / (costo_faltante + costo_merma).

El pedido semanal suma decisiones diarias y supone inventario inicial
cero, sin entregas pendientes ni restricciones de capacidad. No representa
el cuantil de la demanda semanal conjunta.

Las correcciones se prueban con datos sintéticos; la bandeja principal
contiene entregas originales. Reprocesar sobrescribe la carpeta del corte:
versionar con DVC antes permite conservar la publicación anterior.

El acceso al remoto DVC en otro equipo requiere transferirlo o configurar
almacenamiento compartido.


## Evidencia verificada de reproducción exacta

Se ejecutó:

    python scripts/verificar_reproduccion.py

Para el corte 2017-07-29, desde el commit
c50b3c9341eeb7e1d7f647ab34c02ad9361f14de:

1. Se creó una copia de trabajo separada en ese commit.
2. Se recuperaron histórico, bandeja y publicaciones mediante dvc pull.
3. Se recalcularon ingesta, variables, pronósticos y pedidos con la misma
   imagen Docker y Extra Trees configurado con n_jobs=1.
4. Los cuatro CSV resultaron idénticos byte a byte mediante SHA-256.

Resultado: REPRODUCCIÓN CORRECTA.
Detalle de hashes y entorno: evidencias/reproduccion.json.

Esta prueba utilizó el remoto DVC local. Su acceso desde otro equipo
requiere una copia del remoto o almacenamiento compartido.

# Reglas del proyecto

- Mantener la lógica en src/inventario; los DAGs solo orquestan.
- Usar rutas relativas y configuración versionada.
- No guardar datos, modelos ni credenciales en Git.
- Versionar con DVC entradas, datos procesados, modelos y pronósticos.
- No modificar la bandeja que simula el sistema de origen.
- Usar únicamente información disponible en la fecha de emisión.
- Conservar la fecha de llegada y las versiones de datos corregidos.
- Mantener las tareas idempotentes y permitir backfill.
- Validar los datos antes de publicar resultados.
- Comparar baseline y modelo ML con los mismos cortes temporales.
- Configurar los costos de faltantes y merma fuera del código.
- Probar la lógica con pytest y ejecutar las pruebas en Pull Requests.
- Documentar decisiones y limitaciones; no inventar resultados ni evidencias.

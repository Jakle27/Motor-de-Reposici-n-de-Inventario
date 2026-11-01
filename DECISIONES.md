# Decisiones técnicas y de producto

## Disponibilidad temporal
Se distinguen fecha de observación y fecha de llegada mediante un manifiesto.
Solo se incorporan entregas disponibles al corte. El histórico respeta los
retrasos configurados. Catálogo y calendario conocidos al cierre inicial
son supuestos de simulación.

## Validación y correcciones
Se rechazan columnas faltantes, claves vacías o duplicadas, tiendas
desconocidas, observaciones posteriores a su llegada y cantidades negativas
o infinitas. El petróleo ausente se admite como situación esperada.
Las correcciones sustituyen registros por clave según llegada y versión.
Las pruebas confirman que una corrección no se incorpora anticipadamente.
La ingesta conserva intacta la bandeja y produce tablas equivalentes al repetirse.

## Variables y modelo
Los rezagos de 7, 14 y 28 días se unen por fecha exacta. Las observaciones
ausentes no se convierten en ventas cero. Los predictores ausentes se imputan
a cero al construir la matriz del modelo.

Se compara un baseline semanal con Extra Trees. El modelo no lineal se
eligió por costo de cómputo y complejidad moderados frente a deep learning.
Se usa una ventana anual, muestra máxima de 180,000 filas y semilla fija.
Los siete días recientes se reservan para calibración.

## Incertidumbre y negocio
Los cuantiles usan residuos normalizados por familia y escala de ventas
rezagadas. Su cobertura se mide, no se garantiza.
Los costos 5 y 1 son ilustrativos y generan un cuantil objetivo de 0.8333.
El pedido suma recomendaciones diarias bajo inventario inicial cero,
sin pedidos pendientes ni plazos de entrega. Se mantienen cantidades
continuas porque el origen puede contener ventas fraccionarias.

## Evaluación y selección
Ambos modelos usan los mismos cortes temporales y horizontes. Se calculan
MAE, RMSE, WAPE, sesgo, cobertura y costo asimétrico.
Se recomienda un candidato si reduce el costo al menos un 1 % con datos
completos. La recomendación solo puede utilizarse después de disponer
de toda su evidencia. Se publican ambos candidatos; queda pendiente
automatizar el registro y aplicación de promociones.

## Operación y reproducibilidad
Los DAGs orquestan módulos Python. Se utiliza Airflow 3.1.0 standalone
con Docker Compose para una demostración local con recursos limitados.
Las dependencias del producto en Docker tienen versiones fijadas.
Los cortes pasados se reprocesan mediante ejecuciones manuales.
Las carpetas se sobrescriben; DVC conserva versiones registradas antes
del reprocesamiento. El remoto inicial es local y requiere transferencia
o sustitución para su acceso desde otro equipo.

## Uso de IA
Se utilizó asistencia de IA para generar y revisar código e instrucciones.
La autora conserva la responsabilidad de comprender y justificar el producto.
Solo las pruebas y ejecuciones realizadas se consideran evidencia.

---
title: Estado de las funciones y limitaciones conocidas
description: Qué funciones de InvenTag funcionan, cuáles son parciales, qué opciones se detienen con un error y qué límites, costes y riesgos conocer antes de usarlo.
sidebar_position: 5
---

# Estado de las funciones y limitaciones conocidas

**Para quién es:** cualquiera que vaya a depender de InvenTag para trabajo real.

**Qué sabrás después de leerlo:** qué funciones funcionan, dónde se quedan
cortas, qué opciones se detienen con un error y qué hacer ante cada límite.

Esta página es deliberadamente directa. Describe la versión actual; el
[registro de cambios](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) lista lo que cambió en cada versión. Comprobamos
cada punto ejecutando el código sin conexión contra AWS simulado (moto) o
leyendo la ruta del código. **Ninguna prueba se ha ejecutado contra una cuenta real de AWS.** Cuando un
punto de abajo depende de cómo se comporta el AWS real, la página lo indica. Si corriges o
cambias alguno de ellos, actualiza esta página en la misma solicitud de cambios (pull request).

## Qué se prueba {#what-is-tested}

Cada función tiene una prueba sin conexión contra AWS simulado (moto). La lista de pruebas
y lo que comprueba cada una está en la página de [Pruebas](../security/tests.md).

## Opciones con límites {#flags-with-a-limit}

| Opción | Qué ocurre en realidad |
|---|---|
| `--enable-cost-analysis` | Añade una hoja Cost Analysis y las cuatro columnas `forgotten_analysis.*`. Los costes son estimaciones de la API AWS Pricing, no tu factura. Hace llamadas adicionales a Cost Explorer, Pricing y CloudWatch. Consulta [Costes](#costs). |
| `--compliance-standard` | Se detiene con el código de salida 2. Un estándar como SOC 2 no se puede comprobar a partir de un inventario, y una opción que solo imprimiera una etiqueta te induciría a error. Usa una plantilla de política de etiquetas. |
| `--create-google-docs`, `--create-google-sheets` | Solo se han probado con clientes de Google simulados. Consulta [Google Sheets y Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Se mantienen para que los comandos antiguos sigan funcionando. La protección de solo lectura está siempre activa. |
| `--disable-production-safety` | Se detiene con el código de salida 2. La protección no se puede desactivar. |

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)

$ inventag --risk-threshold HIGH
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)

$ inventag --compliance-standard soc2
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)

$ inventag --disable-production-safety
inventag: error: --disable-production-safety: The read-only guard cannot be disabled from the CLI: InvenTag only needs read access, so non-read AWS calls are always blocked.
(exit code 2)
```

## Qué encuentra InvenTag y qué no {#what-inventag-finds-and-what-it-does-not}

- **Servicios con su propio código de descubrimiento (46):** VPC (VPC, subredes,
  grupos de seguridad, gateways de internet y NAT, tablas de rutas, ACL de red,
  direcciones IP elásticas), EC2 (instancias, volúmenes, instantáneas, pares de
  claves), S3, RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS,
  CloudWatch, ECS (clústeres y los servicios de cada clúster), EKS, SNS, SQS,
  DynamoDB, API Gateway, Glue, WorkMail, CloudFormation, ACM, CloudTrail,
  EventBridge, ElastiCache, Redshift, Redshift Serverless, OpenSearch, EFS, ECR,
  Step Functions, Kinesis, Firehose, Secrets Manager (solo nombres), parámetros
  de Systems Manager (solo nombres), grupos de Auto Scaling, almacenes de Backup,
  grupos de usuarios de Cognito, CodeBuild, CodePipeline, grupos de trabajo de
  Athena, EMR, MSK, AppSync, Elastic Beanstalk y ACL web de WAF.
- **Todo lo demás** solo puede aparecer si la API Resource Groups Tagging lo
  devuelve. Esa API lista los recursos que tienen, o tuvieron, etiquetas, así que
  faltan los recursos sin etiquetas de cualquier otro servicio. Con
  `--fallback-display auto` (el valor predeterminado), esos recursos solo se
  muestran para servicios que no tienen resultados de su propio código de
  descubrimiento. Usa `--fallback-display always` para mostrarlos todos.
- **No se recopila:** valores secretos, valores de parámetros, contenido de
  objetos ni ningún otro dato. La protección de solo lectura bloquea las llamadas
  que los devuelven.
- **Los valores secretos de las respuestas permitidas se ocultan.** Algunas
  llamadas de lectura devuelven un secreto junto a un ajuste. Los valores de los
  campos que suelen contener secretos se sustituyen por `***REDACTED***` en los
  informes, la salida JSON, las instantáneas de estado, los puntos de control de
  reanudación y los registros: variables de entorno de Lambda y App Runner,
  valores de entorno de ECS y CodeBuild, datos de usuario de EC2, valores de
  parámetros y de salidas de CloudFormation, argumentos de trabajos y
  desencadenadores de Glue y propiedades de conexión, y cualquier campo con un
  nombre como password, secret, token, private key o credentials. Los nombres
  se mantienen.
- **Los secretos de otros campos no se detectan.** InvenTag se guía por el
  nombre del campo, así que un secreto en una descripción, una etiqueta u otro
  campo de texto libre no se oculta.
- **Los informes y las instantáneas escritos por versiones anteriores a v1.2.0
  pueden contener valores secretos.** Borra o restringe las carpetas
  `bom_output/` antiguas y las copias compartidas.
- **Los servicios globales** (IAM, la lista de buckets de S3, CloudFront,
  Route 53, las ACL web de WAF para CloudFront y los certificados de ACM que usa
  CloudFront) se leen una vez por cuenta desde `us-east-1` (`cn-north-1` en
  China, `us-gov-west-1` en GovCloud), sean cuales sean las regiones que elijas.
  Su columna de región dice `global`; un bucket de S3 conserva su propia región.
  Consulta [Ejecutar un análisis](../guides/run-a-scan.md).
- **Regiones.** Sin `--account-regions`, InvenTag pregunta a EC2 por las
  regiones habilitadas en la cuenta. Si `ec2:DescribeRegions` falla, pregunta a
  `account:ListRegions`; si eso también falla, prueba todas las regiones de la
  partición y omite las que no superan la comprobación de acceso. Una región que
  no supera su comprobación de acceso se omite con una advertencia, y la
  ejecución sigue teniendo éxito.

## Cuando una ejecución sale mal {#when-a-run-goes-wrong}

- **Una cuenta falla y las demás funcionan:** la ejecución termina con el
  código 0, o con el código 5 si pasas `--fail-on-account-error`. El resumen de
  la ejecución y el informe predeterminado nombran cada cuenta que falló y el
  motivo; un informe hecho con `--template` no lo hace. Si fallan
  todas las cuentas, la ejecución termina con el código 1.
- **Una cuenta se queda sin tiempo:** cuenta como fallida. Los recursos
  encontrados antes del límite se quedan en el informe, y el informe
  predeterminado dice que la cuenta está incompleta.
- **No se encontraron recursos, o los filtros los quitaron todos:** sin
  `--template`, InvenTag no escribe ningún informe, registra una advertencia y
  termina con el código 0. Con `--template`, escribe un informe vacío.
  `--fail-if-empty` hace que ambos casos terminen con el código 6.
- **Un servicio para el que no tienes permiso:** InvenTag omite esa llamada,
  registra una advertencia para el servicio con el motivo y continúa. Los
  recursos de ese servicio pueden aparecer igualmente si la API Resource Groups
  Tagging los devuelve.
- **Un listado que falla por otro motivo** (limitado tras los reintentos, o un
  error) se registra como advertencia para ese servicio y región, y queda
  contado en la instantánea de estado (`metadata.tags.coverage_summary`).
- **Todas las llamadas de una cuenta denegadas:** la cuenta no cuenta como
  fallida. La ejecución termina con el código 0 sin recursos que informar, y la
  instantánea que guarda hace que la siguiente ejecución informe de todos los
  recursos de esa cuenta como eliminados.
- **Un servicio cuyo listado se limitó o falló con un error** en una ejecución
  aparece como eliminado en el siguiente informe de cambios.
- **Una sesión que caduca durante el análisis:** la ejecución termina con el
  código 0 y el informe parece completo.
- **Un token de IAM Identity Center (SSO) caducado** detiene la ejecución con un
  traceback de Python en lugar de un mensaje. Vuelve a ejecutar `aws sso login`.
- **Las advertencias del descubrimiento** aparecen en la consola, pero no se
  escriben en el archivo de `--log-file`.
- **Acceso denegado a Cost Explorer:** la ejecución continúa sin datos de
  facturación y registra una advertencia.
- **Una llamada bloqueada por la protección de solo lectura** se registra como
  un error que nombra la operación. Si ocurre dentro de un listado, ese listado
  se omite y la ejecución continúa con el código de salida 0. La CLI no hace
  esas llamadas por sí misma.
- **Una carga a S3 fallida** hace que toda la ejecución termine con el
  código 1, después de escribir los informes en local.
- **Un formato de informe que falla** hace que la ejecución termine con el
  código 1, y no se sube nada a S3, ni siquiera los formatos que sí se
  escribieron.
- **Una instantánea que no se puede guardar** se registra como error, y la
  ejecución termina igualmente con el código 0.
- **La salida a Google con `--template`** se omite, y la ejecución termina con
  el código 0.
- **Algunos valores no válidos se detienen con el código de salida 1, no 2,**
  por ejemplo `--max-concurrent-accounts 0` o `--account-processing-timeout 0`.
- **Los valores del bloque `settings` de un archivo de cuentas sustituyen a las
  opciones de línea de comandos correspondientes**, por ejemplo
  `max_concurrent_accounts`.

## Costes {#costs}

Por defecto, el descubrimiento llama a la API `GetCostAndUsage` de Cost Explorer. En nuestra
prueba sin conexión hizo dos solicitudes por cuenta. AWS cobra cada solicitud a Cost
Explorer. Consulta los
[precios actuales de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` detiene esas llamadas. El informe entonces no tiene datos
  de facturación con los que comparar.
- `--enable-cost-analysis` hace más llamadas, incluso con
  `--no-billing-validation`. En nuestra prueba sin conexión (una cuenta, `us-east-1`)
  hizo 5 llamadas a Cost Explorer, 3 a Pricing y 2 a CloudWatch. Las estimaciones
  ponen precio a cada tipo de instancia (y a cada otro tamaño o clase) por separado.
  Cada consulta de precio distinta se hace una vez y luego se reutiliza, así que el
  número de llamadas a Pricing crece con el número de tipos y tamaños de recursos
  distintos, no con el número de recursos.

Las demás llamadas son gratuitas, pero las cuentas grandes implican muchas solicitudes y posible
limitación (AWS ralentizando tus solicitudes). InvenTag reintenta una llamada limitada hasta 10
veces (modo de reintento standard); `AWS_RETRY_MODE` y `AWS_MAX_ATTEMPTS` cambian este ajuste.

## Rendimiento y límites {#performance-and-limits}

- InvenTag no tiene cifras de rendimiento para cuentas reales. Analizar todas las
  regiones de una cuenta grande es lento: un conjunto de llamadas por servicio y
  por región.
- Contra moto (dentro del proceso, así que sin tiempo de red),
  `scripts/benchmark_scan.py` analizó 9.547 recursos en una región con 2.027
  llamadas a la API. Para cuentas reales, la cifra útil es el número de llamadas:
  unas 60 llamadas fijas por región, más una llamada por bucket de S3 y por
  función Lambda, más una página de la API Tagging por cada 100 recursos
  etiquetados.
- De forma predeterminada se analizan cuatro cuentas a la vez
  (`--max-concurrent-accounts`). Cada cuenta tiene 1800 segundos desde que
  empieza su análisis (`--account-processing-timeout`).
- Cuando algunas cuentas fallan, se guardan los resultados de las que
  terminaron. Ejecuta el mismo comando con `--resume` en menos de 24 horas
  (`--resume-max-age-hours`) para analizar solo las demás.
- Los nombres de hoja de Excel tienen como máximo 31 caracteres: los nombres más
  largos se recortan, los caracteres que Excel no permite pasan a ser `-`, un
  nombre repetido recibe ` (2)`, y el registro nombra cada hoja cambiada. Las
  tablas de Word muestran hasta 50 recursos por servicio de forma predeterminada
  (`max_rows`).
- Cuando una ejecución guarda una instantánea, InvenTag borra las instantáneas de
  `bom_output/state/` con más de 30 días o que superan las 100 más recientes. La
  instantánea recién escrita y la que se usa para comparar nunca se borran.
  Cambia los límites con `--state-retention-days` y `--state-max-snapshots`, o
  consérvalo todo con `none`.
- Con `--enable-network-analysis` o `--enable-security-analysis`, las llamadas
  del análisis se hacen dos veces en una misma ejecución.

## Notas de seguridad {#security-notes}

- **Usa de todos modos una identidad de IAM de solo lectura.** La protección
  bloquea las llamadas de escritura, y tu política de IAM (Identity and Access
  Management) es una segunda red de seguridad independiente. Consulta
  [Configurar el acceso de solo lectura](../guides/read-only-access.md).
- **Los registros de depuración se ocultan** de forma predeterminada: los tokens
  de sesión, las claves, las firmas y los valores secretos indicados arriba se
  enmascaran. Aun así, trata los registros de depuración como confidenciales.
- **Dos funciones de la biblioteca pueden escribir en AWS** cuando se llaman
  desde tu propio código Python (la CLI no las llama):
  `CredentialManager.setup_cross_account_roles()` solo se ejecuta con
  `allow_iam_writes=True`, y la función auxiliar de ciclo de vida de S3 solo con
  `allow_bucket_writes=True`. La protección de solo lectura bloquea ambas en una
  ejecución de la CLI.
- **Usar `CloudBOMGenerator` desde tu propio código Python** no instala la
  protección de solo lectura. Solo lo hace el comando `inventag`.

## Pruebas y lista de materiales de software {#tests-and-the-software-bill-of-materials}

El conjunto de pruebas y el inventario de dependencias tienen sus propias páginas:
[Pruebas](../security/tests.md) y
[Lista de materiales de software](../security/sbom.md).

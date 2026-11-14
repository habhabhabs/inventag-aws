---
title: Estado de las funciones y limitaciones conocidas
sidebar_label: Estado de las funciones
description: Qué funciones de InvenTag funcionan, cuáles son parciales, qué opciones se detienen con un error y qué límites, costes y riesgos conocer antes de usarlo.
sidebar_position: 5
---

# Estado de las funciones y limitaciones conocidas

**Para quién es:** cualquiera que vaya a depender de InvenTag para trabajo real.

**Qué sabrás después de leerlo:** qué funciones funcionan, dónde se quedan
cortas, qué opciones se detienen con un error y qué hacer ante cada límite.

Esta página es deliberadamente directa. Describe la versión actual; el
[registro de cambios](https://github.com/habhabhabs/inventag-aws/blob/main/CHANGELOG.md) lista lo que cambió en cada versión. Cada punto de abajo está demostrado por una prueba sin conexión o una ejecución contra AWS simulado (moto). **Ninguna prueba se ha ejecutado contra una cuenta real de AWS.** Cuando un punto depende de cómo se comporta el AWS real, la página lo indica. Si corriges o cambias alguno de ellos, actualiza esta página en la misma solicitud de cambios (pull request).

## Qué se prueba {#what-is-tested}

La página de [Pruebas](../security/tests.md) lista las pruebas sin conexión contra AWS simulado (moto) y lo que comprueba cada una. Una afirmación de esta documentación que ninguna prueba demuestra lleva una nota que empieza por "No verificado contra".

## Opciones con límites {#flags-with-a-limit}

| Opción | Qué ocurre en realidad |
|---|---|
| `--enable-cost-analysis` | Añade una hoja Cost Analysis y las cuatro columnas `forgotten_analysis.*`, con estimaciones de la API AWS Pricing que no son tu factura, y hace llamadas adicionales a Cost Explorer, Pricing y CloudWatch (consulta [Costes](#costs)). |
| `--compliance-standard` | Se detiene con el código de salida 2, porque un estándar como SOC 2 no se puede comprobar a partir de un inventario; usa en su lugar una plantilla de política de etiquetas. |
| `--create-google-docs`, `--create-google-sheets` | Solo se han probado con clientes de Google simulados. Consulta [Google Sheets y Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Se mantienen para que los comandos antiguos sigan funcionando. La protección de solo lectura está siempre activa. |
| `--disable-production-safety` | Se detiene con el código de salida 2, porque la protección de solo lectura no se puede desactivar. |

```bash title="Terminal"
inventag --create-google-docs
```

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
inventag: error: Google: Google output needs libraries that are not installed (google.auth). Install the Google libraries with: pip install "inventag-aws[google]"
(exit code 2)
```

```bash title="Terminal"
inventag --risk-threshold HIGH
```

```text title="Salida"
inventag: error: --risk-threshold: needs --enable-security-analysis, which produces the risk levels it checks.
(exit code 2)
```

```bash title="Terminal"
inventag --compliance-standard soc2
```

```text title="Salida"
inventag: error: --compliance-standard: Compliance-standard enforcement is not implemented yet; the option has never changed InvenTag's behaviour.
(exit code 2)
```

```bash title="Terminal"
inventag --disable-production-safety
```

```text title="Salida"
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
- **Todo lo demás** aparece solo cuando la API Resource Groups Tagging lo
  devuelve, así que faltan los recursos sin etiquetas de cualquier otro
  servicio. Con `--fallback-display auto` (el valor predeterminado), esos
  recursos solo se muestran para servicios que no tienen resultados de su
  propio código de descubrimiento; `--fallback-display always` los muestra
  todos.
- **No se recopila:** valores secretos, valores de parámetros, contenido de
  objetos ni ningún otro dato, porque la protección de solo lectura bloquea las
  llamadas que los devuelven.
- **Los valores secretos de las respuestas permitidas se ocultan.** Algunas
  llamadas de lectura devuelven un secreto junto a un ajuste. Los valores de los
  campos que suelen contener secretos se sustituyen por `***REDACTED***` en los
  informes, la salida JSON, las instantáneas de estado, los puntos de control de
  reanudación y los registros: variables de entorno de Lambda y App Runner,
  valores de entorno de ECS y CodeBuild, datos de usuario de EC2, valores de
  parámetros de CloudFormation, valores de salida de pilas y cuerpos de
  plantilla de conjuntos de pilas, argumentos de trabajos, desencadenadores y
  ejecuciones de trabajos de Glue y propiedades de conexión, argumentos de
  trabajos de EMR on EKS, códigos de activación de WorkSpaces Thin Client,
  carteras de certificados de DMS, cadenas de conexión, URL firmadas, de
  descarga y de carga, tokens de Splunk HEC, de Grafana y de unión, y cualquier
  campo con un nombre como password, secret, token, access o refresh token,
  private key o credentials, también dentro de texto JSON. Los nombres se
  mantienen.
- **Los secretos de otros campos no se detectan:** un secreto en una
  descripción, una etiqueta, otro campo de texto libre o un campo que AWS añada
  más adelante se copia tal cual en los informes, porque el enmascaramiento se
  guía por el nombre del campo.
- **Las etiquetas se muestran tal cual**, también cuando una clave de etiqueta
  parece un secreto, como `password`.
- **Los informes y las instantáneas escritos por versiones anteriores a v1.2.0
  pueden contener valores secretos**, así que borra o restringe las carpetas
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
  código 0, o con el código 5 si pasas `--fail-on-account-error`.
- **Un informe hecho con `--template`** no nombra las cuentas que fallaron; el
  resumen de la ejecución y el informe predeterminado sí.
- **Fallan todas las cuentas:** la ejecución termina con el código 1 y no
  escribe ningún informe, también con `--fail-on-account-error`.
- **Una cuenta se queda sin tiempo:** cuenta como fallida, y los recursos
  encontrados antes del límite se quedan en el informe.
- **No se encontraron recursos, o los filtros los quitaron todos:** InvenTag no
  escribe ningún informe sin `--template` y escribe un informe vacío con
  `--template`, y termina con el código 0 salvo que pases `--fail-if-empty`
  (código 6).
- **Una política de etiquetas sin ningún recurso en su alcance** informa
  `0 of 0 resources compliant (100.0%)`, aunque no se comprobó nada.
- **Un servicio para el que no tienes permiso** se omite con una advertencia, y
  sus recursos aparecen solo si la API Resource Groups Tagging los devuelve.
- **Un listado que falla por otro motivo** (limitado tras los reintentos, o un
  error) es una advertencia y un recuento en la instantánea
  (`metadata.tags.coverage_summary`), y ningún informe lo nombra.
- **Todas las llamadas de una cuenta denegadas:** la cuenta no cuenta como
  fallida, la ejecución termina con el código 0 y el siguiente informe de
  cambios lista como eliminados todos los recursos de esa cuenta.
- **Un servicio cuyo listado se limitó o falló** en una ejecución muestra sus
  recursos como eliminados en el siguiente informe de cambios.
- **Una ejecución con otras regiones o servicios que la anterior** muestra como
  eliminados, en el informe de cambios, los recursos que quedan fuera del nuevo
  alcance.
- **El primer informe de cambios después de actualizar desde v1.1.4** lista los
  recursos de los servicios que ahora se cubren como añadidos, aunque ya
  existían.
- **Una sesión que caduca durante el análisis** deja un informe solo con lo que
  se leyó antes de que caducara, sin ninguna nota, y la ejecución termina con el
  código 0, también con `--fail-on-account-error`.
- **Una sesión que ya ha caducado cuando empieza el análisis** no da ningún
  archivo de informe y termina con el código 0.
- **Con `--resume`**, una cuenta cuya sesión caducó a mitad de la primera
  ejecución puede reutilizarse como si estuviera completa.
- **Un token de IAM Identity Center (SSO) caducado** detiene la ejecución con el
  código de salida 1 y un traceback de Python, y el mensaje no te dice que
  ejecutes `aws sso login`.
- **Acceso denegado a Cost Explorer:** la ejecución continúa sin datos de
  facturación, y las dos advertencias sobre ello solo se muestran con `--debug`.
- **Una llamada bloqueada por la protección de solo lectura** dentro de un
  listado omite ese listado con una línea de error, y la ejecución termina
  igualmente con el código 0.
- **Una carga a S3 fallida** hace que toda la ejecución termine con el
  código 1, después de escribir los informes en local.
- **Un formato de informe que falla** hace que la ejecución termine con el
  código 1 y no suba nada a S3, ni siquiera los formatos que sí se escribieron.
- **Una instantánea que no se puede guardar** es solo una línea de error, y la
  ejecución termina igualmente con el código 0.
- **La salida a Google con `--template`** se omite, y la ejecución termina con
  el código 0.
- **Algunos valores no válidos se detienen con el código de salida 1, no 2,**
  por ejemplo `--max-concurrent-accounts 0` o `--account-processing-timeout 0`.
- **Los valores del bloque `settings` de un archivo de cuentas sustituyen a las
  opciones de línea de comandos correspondientes**, por ejemplo
  `max_concurrent_accounts`.
- **Un resultado vacío con `--s3-bucket`** hace que la ejecución termine con el
  código 1 (`S3 upload of reports failed: no files`), también con
  `--fail-if-empty`.
- **Un nombre de región mal escrito en `--account-regions`** termina la
  ejecución con el código 0, un texto `KeyError` sin procesar y ningún informe.
- **Un perfil que necesita MFA, ejecutado sin terminal,** se detiene con un
  traceback de Python y un mensaje vacío, o espera para siempre cuando la
  entrada sigue abierta.
- **Una ruta de `--audit-output` o `--log-file` en la que no se puede
  escribir** termina la ejecución con un traceback de Python, y una carpeta de
  salida que no se puede usar se descubre solo después de todo el análisis.
- **Ctrl-C** detiene la ejecución sin un mensaje visible, y un SIGTERM la
  detiene sin ningún mensaje.
- **Una segunda entrada con el mismo ID de cuenta** en un archivo de cuentas se
  descarta sin mensaje, así que sus regiones no se analizan.
- **Dos ejecuciones que usan la misma carpeta de salida a la vez** no se
  impiden.

## Costes {#costs}

Por defecto, el descubrimiento llama a la API `GetCostAndUsage` de Cost Explorer. En nuestra
prueba sin conexión hizo dos solicitudes por cuenta. AWS cobra cada solicitud a Cost
Explorer: consulta los
[precios actuales de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` detiene esas llamadas, y el informe entonces no
  tiene datos de facturación con los que comparar.
- `--enable-cost-analysis` hace más llamadas a Cost Explorer, Pricing y
  CloudWatch, incluso con `--no-billing-validation`, y el número depende de tus
  recursos. Cada consulta de precio distinta se hace una vez y luego se
  reutiliza, así que el número de llamadas a Pricing crece con el número de
  tipos y tamaños de recursos distintos, no con el número de recursos.

No verificado contra AWS real: las estimaciones de costes de `--enable-cost-analysis`.

InvenTag reintenta una llamada limitada hasta 10 veces (modo de reintento
standard); `AWS_RETRY_MODE` y `AWS_MAX_ATTEMPTS` cambian este ajuste.

## Rendimiento y límites {#performance-and-limits}

- InvenTag no tiene cifras de rendimiento para cuentas reales, y un análisis
  hace un conjunto de llamadas por servicio y por región.
- Contra moto (dentro del proceso, así que sin tiempo de red),
  `scripts/benchmark_scan.py --scale 60` analizó 10.948 recursos en una región
  con 2.053 llamadas a la API: 1.200 llamadas a `s3:GetBucketLocation` (una por
  bucket), 600 llamadas a `lambda:GetFunctionConfiguration` (una por función),
  150 llamadas a la API Resource Groups Tagging y 103 llamadas más. Para
  cuentas reales, la cifra útil es el número de llamadas.
- De forma predeterminada se analizan cuatro cuentas a la vez
  (`--max-concurrent-accounts`). Cada cuenta tiene 1800 segundos desde que
  empieza su análisis (`--account-processing-timeout`).
- Cuando algunas cuentas fallan, se guardan los resultados de las que
  terminaron. Ejecuta el mismo comando con `--resume` en menos de 24 horas
  (`--resume-max-age-hours`) para analizar solo las demás.
- Los nombres de hoja de Excel se recortan a 31 caracteres, los caracteres que
  Excel no permite pasan a ser `-`, un nombre repetido recibe ` (2)`, y el
  registro nombra cada hoja cambiada.
- Las tablas de Word muestran hasta 50 recursos por servicio de forma
  predeterminada (`max_rows`).
- Cuando una ejecución guarda una instantánea, InvenTag borra las instantáneas de
  `bom_output/state/` con más de 30 días o que superan las 100 más recientes. La
  instantánea recién escrita y la que se usa para comparar nunca se borran.
  Cambia los límites con `--state-retention-days` y `--state-max-snapshots`, o
  consérvalo todo con `none`.
- Con `--enable-network-analysis` o `--enable-security-analysis`, las llamadas
  del análisis se hacen dos veces en una misma ejecución.
- El análisis de red cuenta un recurso que está en varias subredes solo para la
  primera, y cuenta los balanceadores de carga para su VPC pero no para una
  subred.
- El enriquecimiento de atributos de servicio (`enable_service_enrichment` en
  los ajustes de la BOM) no se ejecuta; los informes contienen los campos que
  devuelve el descubrimiento.
- En un informe de plantilla, la columna Name está vacía cuando AWS no devuelve
  ningún campo `Name` ni etiqueta `Name` para el recurso; la columna ID lo
  identifica. Para funciones Lambda, roles de IAM y alias de KMS, un informe de
  plantilla muestra el ID como nombre.

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
- **Una plantilla de configuración puede fijar la carpeta de salida y las
  cuentas y roles que se analizan.** Usa solo plantillas de confianza.
- **Las sesiones de rol asumido no se renuevan**, así que el análisis de una
  cuenta que dure más que la sesión se encuentra con un token caducado.

  No verificado contra AWS real: las sesiones de rol asumido duran una hora.
- **MFA funciona solo mediante perfiles de AWS** (`mfa_serial`), no para
  entradas `role_arn` de un archivo de cuentas.

  No verificado contra un dispositivo MFA real: MFA mediante un perfil de AWS con `mfa_serial`.

## Pruebas y lista de materiales de software {#tests-and-the-software-bill-of-materials}

El conjunto de pruebas y el inventario de dependencias tienen sus propias páginas:
[Pruebas](../security/tests.md) y
[Lista de materiales de software](../security/sbom.md).

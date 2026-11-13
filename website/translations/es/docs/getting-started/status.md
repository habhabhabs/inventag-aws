---
title: Estado de las funciones y limitaciones conocidas
description: Qué funciones de InvenTag funcionan en la versión actual, cuáles son parciales, qué opciones se detienen con un error y los límites, costes y riesgos concretos que conviene conocer antes de depender de ella.
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
| `--service-descriptions` | Las descripciones personalizadas funcionan para los servicios para los que InvenTag no tiene descripción integrada. En los recursos de S3, EC2, RDS, Lambda y VPC, prevalece la descripción integrada salvo que tu entrada indique también un `template`. Consulta [Archivos de configuración](../reference/configuration-files.md#service-descriptions). |
| `--enable-cost-analysis` | Añade una hoja Cost Analysis y las cuatro columnas `forgotten_analysis.*`. Los costes son estimaciones de la API AWS Pricing, no tu factura. Hace muchas llamadas adicionales a Cost Explorer, Pricing y CloudWatch. Consulta [Costes](#costs). |
| `--compliance-standard` | Se detiene con el código de salida 2. Un estándar como SOC 2 no se puede comprobar a partir de un inventario, y una opción que solo imprimiera una etiqueta te induciría a error. Usa una plantilla de política de etiquetas. |
| `--create-google-docs`, `--create-google-sheets` | Solo se han probado con clientes de Google simulados. Consulta [Google Sheets y Docs](../guides/google-sheets-and-docs.md#what-is-not-verified). |
| `--enable-production-safety`, `--security-validation`, `--enforce-read-only` | Se mantienen para que los comandos antiguos sigan funcionando. La protección de solo lectura está siempre activa. |
| `--disable-production-safety` | Se detiene con el código de salida 2. La protección no se puede desactivar. |

```text title="Terminal"
$ inventag --create-google-docs
inventag - WARNING -   - No output format specified. Use --create-word or --create-excel
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

- **Servicios con código de descubrimiento propio (24):** VPC (VPC, subredes,
  grupos de seguridad, gateways de internet y NAT, tablas de rutas, ACL de red,
  direcciones IP elásticas), EC2 (instancias, volúmenes, instantáneas, pares de claves), S3,
  RDS, Lambda, ELB, ELBv2, IAM, CloudFront, Route 53, KMS, CloudWatch, ECS,
  EKS, SNS, SQS, DynamoDB, API Gateway, Glue, WorkMail, CloudFormation, ACM,
  CloudTrail y EventBridge.
- **Todo lo demás** solo puede aparecer si la API Resource Groups Tagging
  lo devuelve. Esa API lista los recursos que tienen, o tuvieron alguna vez, etiquetas, así que
  faltan los recursos sin etiquetar de cualquier otro servicio. Con
  `--fallback-display auto` (el valor predeterminado), esos recursos se muestran solo para
  los servicios que no tienen resultados de su propio código de descubrimiento. Usa
  `--fallback-display always` para mostrarlos todos.
- **No se recopila:** secretos, parámetros, contenido de objetos ni ningún otro dato.
  La protección de solo lectura bloquea esas llamadas.
- **Los servicios globales** (IAM, la lista de buckets de S3, CloudFront, Route 53 y
  los certificados de ACM que usa CloudFront) se leen una vez por cuenta desde
  `us-east-1`, sean cuales sean las regiones que elijas. Su columna de región dice `global`;
  un bucket de S3 conserva su propia región. Consulta [Ejecutar un análisis](../guides/run-a-scan.md).
- **Regiones.** Sin `--account-regions`, InvenTag pregunta a EC2 qué regiones están
  habilitadas en la cuenta. Si esa llamada falla, registra un aviso y analiza solo
  `us-east-1`, `us-west-2`, `eu-west-1` y `ap-southeast-1`. Una región que
  no supera la comprobación de acceso se omite con un aviso, y la ejecución sigue teniendo éxito.

## Cuando una ejecución sale mal {#when-a-run-goes-wrong}

- **Una cuenta falla y las demás funcionan:** la ejecución termina con el código 0. El
  resumen de la ejecución y el informe nombran cada cuenta que falló y el motivo.
  Si fallan todas las cuentas, la ejecución termina con el código 1.
- **No se encuentran recursos, o los filtros los eliminaron todos:** InvenTag no escribe
  ningún informe, registra un aviso y termina con el código 0. Comprueba si el archivo existe
  en tus scripts.
- **Un servicio para el que no tienes permiso:** InvenTag omite esa llamada, registra un
  aviso para el servicio con el motivo y continúa. Los recursos de ese
  servicio aún pueden aparecer si la API Resource Groups Tagging los devuelve.
- **Acceso denegado a Cost Explorer:** la ejecución continúa sin datos de facturación y
  registra un aviso.
- **Una llamada bloqueada por la protección de solo lectura** genera un error que nombra la
  operación. La CLI no hace esas llamadas por sí misma.
- **Una subida fallida a S3** hace que toda la ejecución termine con el código 1, una vez
  escritos los informes en local.
- **Un formato de informe que falla** hace que la ejecución termine con el código 1.

## Costes {#costs}

Por defecto, el descubrimiento llama a la API `GetCostAndUsage` de Cost Explorer. En nuestra
prueba sin conexión hizo dos solicitudes por cuenta. AWS cobra cada solicitud a Cost
Explorer. Consulta los
[precios actuales de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

- `--no-billing-validation` detiene esas llamadas. El informe entonces no tiene datos
  de facturación con los que comparar.
- `--enable-cost-analysis` hace más llamadas a Cost Explorer incluso con
  `--no-billing-validation` (entre cinco y ocho más por cuenta en nuestras pruebas sin conexión, según los recursos encontrados), además de
  llamadas a Pricing y CloudWatch.

Las demás llamadas son gratuitas, pero las cuentas grandes implican muchas solicitudes y posible
limitación (AWS ralentizando tus solicitudes).

## Rendimiento y límites {#performance-and-limits}

- InvenTag no tiene cifras de rendimiento para cuentas reales. Analizar todas las regiones
  de una cuenta grande es lento: un conjunto de llamadas por servicio y por región.
- Las cuentas se analizan de cuatro en cuatro por defecto. Cada cuenta dispone de 1800 segundos
  (30 minutos). Una ejecución no se reanuda; si se detiene, vuelve a iniciarla.
- Los nombres de hoja de Excel se recortan a 31 caracteres. Las tablas de Word muestran hasta 50
  recursos por servicio por defecto (`max_rows`).
- Cuando una ejecución guarda una instantánea, InvenTag elimina las instantáneas de `bom_output/state/`
  con más de 30 días o que superen las 100 más recientes. Guarda una copia si necesitas
  un historial más largo.

## Notas de seguridad {#security-notes}

- **Usa de todos modos una identidad de IAM de solo lectura.** La protección bloquea las llamadas de escritura, y
  tu política de IAM (Identity and Access Management) es una segunda red de seguridad
  independiente. Consulta [Configurar el acceso de solo lectura](../guides/read-only-access.md).
- **Los registros de depuración se redactan** por defecto: los tokens de sesión, las claves y las firmas
  se enmascaran. Aun así, trata los registros de depuración como información sensible.
- **Dos funciones de la biblioteca escriben en AWS** cuando se llaman desde tu propio código
  Python (la CLI no las llama): `CredentialManager.setup_cross_account_roles()`
  crea roles de IAM, y el asistente de S3 puede cambiar las reglas de ciclo de vida de un bucket
  (desactivado por defecto, y se combina con las reglas existentes).

## Pruebas y lista de materiales de software {#tests-and-the-software-bill-of-materials}

El conjunto de pruebas y el inventario de dependencias tienen sus propias páginas:
[Pruebas](../security/tests.md) y
[Lista de materiales de software](../security/sbom.md).

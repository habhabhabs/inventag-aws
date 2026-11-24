---
title: Comprobaciones FinOps
description: Seis comprobaciones FinOps fijas sobre los recursos que encuentra un escaneo, sin ninguna llamada adicional a AWS, y una lectura opcional del gasto del mes pasado por servicio, cuenta vinculada y etiqueta de asignación de costes desde Cost Explorer.
sidebar_position: 10
---

# Comprobaciones FinOps

**Para quién es:** te ocupas del gasto en la nube y quieres una lista de
recursos que revisar, hecha a partir del inventario que ya tienes.

**Qué podrás hacer después de leerlo:** ejecutar las seis comprobaciones
FinOps, leer la hoja `FinOps` y saber lo que las comprobaciones no pueden ver.

## Ejecutar las comprobaciones {#run-the-checks}

```bash
inventag --create-excel --finops-checks
```

La opción está desactivada de forma predeterminada. Con ella, InvenTag ejecuta
seis comprobaciones fijas sobre los recursos que encontró el escaneo y añade
una hoja llamada `FinOps` como última hoja del informe de Excel.

- Las comprobaciones solo leen las filas que el escaneo ya tiene. No hacen
  ninguna llamada adicional a AWS ni necesitan ningún permiso adicional. La
  protección de solo lectura ve las mismas llamadas con y sin la opción.
- Las comprobaciones no cambian nada en ninguna cuenta.
- Los resultados no cambian el código de salida: una ejecución con resultados
  `fail` termina igual que sin ellos.
- Sin la opción, las comprobaciones no se ejecutan: el informe no tiene hoja
  `FinOps`, y las demás hojas y el texto de la consola son los mismos que con
  la opción.

## Las seis comprobaciones {#the-six-checks}

| ID de comprobación | Recursos | Resultado `fail` cuando |
|---|---|---|
| `FIN-001` | Volúmenes EBS | el `State` del volumen es `available` (sin conexión) |
| `FIN-002` | Direcciones IP elásticas | la dirección no tiene `AssociationId` |
| `FIN-003` | Instantáneas EBS de la cuenta escaneada | el `StartTime` de la instantánea es de más de 90 días antes del inicio de la ejecución |
| `FIN-004` | Instancias EC2 | el estado de la instancia es `stopped` |
| `FIN-005` | Balanceadores de carga | ningún grupo de destino de la misma cuenta y región lo nombra (hoja `ELBV2`), o no lista ninguna instancia (balanceadores de carga clásicos, hoja `ELB`) |
| `FIN-006` | Cada recurso en el alcance de la política de etiquetas integrada `finops-cost-allocation` | falta una clave de esa política: `CostCenter`, `Owner`, `Project` o `Environment` |

Los 90 días de `FIN-003` son fijos; ninguna opción los cambia.

`FIN-006` usa la misma comprobación que la política de etiquetas
`finops-cost-allocation` (consulta
[Comprobar etiquetas con una política](check-tag-compliance.md)), pero solo
busca claves que faltan. Una clave cuyo valor la política no permite no es un
resultado de `FIN-006`. Las claves de etiqueta distinguen mayúsculas y
minúsculas: `owner` no cuenta como `Owner`. Las filas que solo vienen de Cost
Explorer (origen `billing`) no se comprueban.

## Resultados {#results}

Cada comprobación da uno de tres resultados para cada recurso:

- `fail`: la comprobación observó lo que dice la tabla. El recurso se lista.
- `not_evaluated`: faltan los datos que la comprobación necesita. El recurso
  se lista con un motivo.
- `pass`: el recurso se cuenta, no se lista.

Un hueco en los datos nunca es un pass. Los motivos son:

| Motivo | Significado |
|---|---|
| `identity_only` | El recurso solo se conoce por la API Resource Groups Tagging, así que el campo que lee la comprobación no está en su fila. |
| `field_missing` | El campo que lee la comprobación no está en la fila. Para `FIN-003`, también cuando la ejecución no tiene hora de inicio. |
| `tags_not_read` | Solo `FIN-006`: falta una clave y el listado de la API Tagging de esa región falló en esta ejecución. Para un recurso global cuenta cualquier listado fallido de la API Tagging de la cuenta. |
| `listing_not_read` | Un listado que la comprobación necesita falló en esta ejecución. Cada comprobación que necesita ese listado tiene una línea para él y su región: un listado `ec2` fallido da cuatro líneas (`FIN-001`, `FIN-003`, `FIN-004`, `FIN-006`). |

## La hoja FinOps {#the-finops-sheet}

La primera línea de la hoja dice: "These are observations from the
inventory. A resource listed here may be intended." (son observaciones del
inventario; un recurso listado aquí puede ser intencionado).

Después vienen los resultados listados, con estas columnas: `Check ID`,
`Check`, `Result`, `Reason`, `Account`, `Region`, `Service`, `Resource Type`,
`Resource ID`, `Name`, `Observed`. Las filas se ordenan por ID de
comprobación, cuenta, región e ID de recurso. `Observed` dice lo que vio la
comprobación, por ejemplo "no attachment", "started 2026-05-02", "state
stopped" o "missing: CostCenter, Owner". No se copia nada más de la respuesta
de la API en la hoja.

Tras los resultados listados viene una tabla con una fila por comprobación y
los recuentos `Fail`, `Not evaluated` y `Pass`.

Un ejemplo, hecho por el generador de la documentación a partir de una cuenta
de AWS simulada:

**Sheets:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `FinOps`

`FinOps` sheet:

> These are observations from the inventory. A ...  

| Check ID | Check | Result | Reason | Account | Region | Service | Resource Type | Resource ID | Name | Observed |
|---|---|---|---|---|---|---|---|---|---|---|
| FIN-001 | EBS volume with no attachment | fail |  | 123456789012 | us-east-1 | EC2 | Volume | vol-57d5df4cfc9884b48 | acme-build-cache | no attachment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | global | IAM | Role | acme-orders-api-role |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | VPC | NetworkAcl | acl-3118daa9d5cc099a7 |  | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-data-lake | acme-data-lake | missing: Project |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-inventory-reports | acme-inventory-reports | missing: CostCenter, Owner, Project, Environment |
| FIN-006 | Cost allocation tag key missing | fail |  | 123456789012 | us-east-1 | S3 | Bucket | acme-new-bucket | acme-new-bucket | missing: CostCenter, Owner, Project, Environment |

Con `--per-account-reports`, el informe de cada cuenta lista solo los
resultados de esa cuenta.

Con `--template` no se escribe ninguna hoja `FinOps`. Las comprobaciones se
ejecutan sobre la instantánea de estado de la ejecución, como el conjunto de
políticas incluido `finops-checks`, y sus resultados se escriben en
`policy_findings_<timestamp>.json` en el directorio de salida, con un resumen de
texto en la consola. Sin `--policy-fail-on` no cambian el código de salida. Si
además se usa `--disable-state-management`, no hay instantánea: una advertencia
dice que no se escribió ningún resultado FinOps.

Estos resultados vienen del conjunto de políticas incluido `finops-checks`, que
son las mismas seis comprobaciones escritas como políticas. De ello se
desprenden dos cosas:

- La hoja `FinOps` de una ejecución sin `--template` es lo que escribió v1.4.3,
  byte a byte (una prueba la compara con un archivo de referencia (golden) hecho
  con v1.4.3). El motor de políticas, que usan `--template` e
  `inventag policy check --set finops-checks`, sigue las reglas escritas del
  lenguaje de políticas y, en unos pocos casos, da una respuesta distinta de la
  hoja. Las pruebas encontraron cinco: un recurso global cuando falló un listado
  de la API de etiquetado de su cuenta (`FIN-006`); un recurso con todas las
  claves presentes en una región cuyo listado de la API de etiquetado falló
  (`FIN-006`); un listado `elb` clásico que falló, que el motor también cuenta
  contra los balanceadores de carga del listado `elbv2` (`FIN-005`); un grupo de
  destino conocido solo por su identidad (`FIN-005`); y el orden de los motivos
  de un balanceador de carga que no tiene ARN mientras su listado `elbv2` falló
  (`FIN-005`). No verificado más allá de esas pruebas: otras diferencias.
- `--policy-fail-on` se aplica también a estos resultados: con `--finops-checks`,
  `--template`, `--policy` y `--policy-fail-on SEVERITY` juntos, un resultado
  `FIN-` que falla con esa gravedad o una superior da el código de salida 7. Las
  comprobaciones incluidas tienen la gravedad `low`. La regla de que los
  resultados no cambian el código de salida vale sin `--policy-fail-on`.

## El resultado `finops_checks` {#the-finops_checks-result}

La línea de comandos solo escribe los resultados como la hoja `FinOps`. En
Python, `CloudBOMGenerator.generate_multi_account_bom()` los devuelve en la
clave `finops_checks`, y un informe JSON escrito con el formato de salida
`json` tiene la misma clave en su `metadata`. La clave contiene:

- `schema_version`: `1`.
- `summary`: una entrada por comprobación, con `policy` (el ID de la
  comprobación), `check`, `fail`, `not_evaluated` y `pass`.
- `findings`: los resultados listados, con `policy`, `result`, `reason`,
  `account`, `region`, `service`, `resource_type`, `resource`, `name` y
  `message` (el texto de `Observed`).

Sin la opción, la clave no está.

## Asignación de costes desde Cost Explorer {#cost-allocation-from-cost-explorer}

`--finops-cost-allocation` es una segunda opción, desactivada de forma
predeterminada e independiente de `--finops-checks` y de
`--enable-cost-analysis`. Lee el gasto del mes pasado desde Cost Explorer para
cada cuenta, con las credenciales propias de esa cuenta, y añade una hoja
llamada `FinOps costs` como última hoja del informe de Excel.

```bash
inventag --create-excel --finops-cost-allocation
```

### Solicitudes {#requests}

Para cada cuenta, en este orden:

| Solicitud | Cuántas |
|---|---|
| `ListCostAllocationTags` para `CostCenter`, `Owner`, `Project` y `Environment` (las claves de la política de etiquetas integrada `finops-cost-allocation`) | 1 |
| `GetCostAndUsage` agrupado por servicio | 1 |
| `GetCostAndUsage` agrupado por cuenta vinculada | 1 |
| `GetCostAndUsage` agrupado por cada una de esas claves que está activa como etiqueta de asignación de costes | 0 a 4 |

Eso son como máximo 7 solicitudes por cuenta. Una clave que
`ListCostAllocationTags` muestra como no activa, o que no lista, no se
consulta; su tabla dice "not active as a cost allocation tag" o "not found as
a cost allocation tag". Si falla el propio `ListCostAllocationTags`, se
consultan las cuatro claves.

Otra página de una respuesta (`NextPageToken`) es una solicitud más. Sale de
las mismas 7, como máximo 3 por agrupación. Una tabla que necesita más páginas
se marca como "incomplete".

Después de que se deniega o se limita una solicitud `GetCostAndUsage`,
InvenTag no hace más solicitudes a Cost Explorer para esa cuenta: las tablas
aún no leídas reciben el mismo estado, y la nota de la ejecución dice que no
se hizo ninguna solicitud más.

Antes del descubrimiento, la ejecución muestra una línea de aviso con el máximo
de solicitudes, por ejemplo: `Cost Explorer: up to 7 request(s) in this run
(billing validation: 0; cost trend: 0; cost allocation: 7). AWS charges for
each.` La auditoría de la protección de solo lectura (`--audit-output`) nunca
cuenta más solicitudes de la opción de las que dice esa línea.

El SDK reintenta una solicitud limitada, y cada reintento es una solicitud más.
AWS cobra cada solicitud a Cost Explorer: consulta los
[precios de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
No verificado contra AWS real: lo que AWS cobra por estas solicitudes, incluidos
los reintentos y `ListCostAllocationTags`.

### La hoja FinOps costs {#the-finops-costs-sheet}

La hoja empieza con una nota: los importes son los que devuelve Cost Explorer,
para cada cuenta, leídos con las credenciales propias de esa cuenta, para el
último mes completo, y no son costes de recursos sueltos. Después hay una fila
por cuenta, agrupación y valor, con las columnas `Account`, `Grouping`,
`Value`, `Amount`, `Currency`, `Metric`, `Period start`, `Period end` y
`Status`.

- El periodo es el mes natural anterior al mes en que empezó la ejecución.
  `Period end` es el primer día del mes de la ejecución.
- La métrica es `UnblendedCost`. Los importes son el texto que devuelve AWS;
  InvenTag no los suma, divide ni redondea.
- En una agrupación por etiqueta, el valor `(no value)` es el gasto sin esa
  clave de etiqueta.
- Una tabla que no se pudo leer tiene una fila con su estado, por ejemplo
  "not read: access denied". Las notas de la ejecución también la nombran, y
  una solicitud denegada tiene una línea `Permissions:`. El resultado del
  escaneo y el código de salida son los mismos que sin la opción.
- Una tabla que se leyó pero no contiene gasto tiene una fila con el estado
  "no spend returned".

Con `--per-account-reports`, el informe de cada cuenta contiene solo las tablas
de esa cuenta. Con `--template` no se hace ninguna solicitud: InvenTag muestra
un aviso y no escribe ninguna hoja `FinOps costs`.

### La clave `finops_costs`, la instantánea y el informe de cambios {#the-finops_costs-key-the-snapshot-and-the-change-report}

- En Python, el resultado de `CloudBOMGenerator.generate_multi_account_bom()` y
  el `metadata` de un informe JSON tienen la clave `finops_costs`:
  `schema_version`, `metric` y, para cada cuenta, el periodo, el número de
  solicitudes, el estado de cada clave de etiqueta y las tablas.
- La instantánea de estado recibe `metadata.tags.cost_allocation`: solo las
  tablas (totales por servicio, cuenta vinculada y valor de etiqueta; sin IDs
  de recursos). La instantánea sigue siendo legible solo por su propietario
  (modo 0600). `--no-cost-in-snapshot` deja las cifras fuera de la
  instantánea; la hoja se sigue escribiendo. Sin `--finops-cost-allocation`,
  esa opción no cambia nada y un aviso lo dice.
- Leída desde una cuenta de administración (pagadora), la tabla por cuenta
  vinculada puede listar todas las cuentas miembro de la organización con su
  gasto, también cuentas que esta ejecución no escaneó, y las tablas por
  etiqueta contienen sus valores de etiqueta (por ejemplo nombres o correos de
  `Owner`) tal como los devuelve AWS. Van a la hoja, a la instantánea y al
  informe de cambios. Usa `--no-cost-in-snapshot` para dejarlos fuera de la
  instantánea. No verificado contra AWS real: lo que contiene la respuesta de
  una cuenta pagadora.
- El informe de cambios recibe un bloque "Cost, previous run to this run"
  cuando esta ejecución leyó la asignación de costes. Muestra cada valor de la
  ejecución anterior y de esta, uno al lado del otro, cuando las dos
  instantáneas tienen meses distintos. Si no, una línea dice por qué no hay
  comparación: la instantánea anterior no tiene cifras, las dos ejecuciones
  leyeron el mismo mes, o se usó `--no-cost-in-snapshot`.

### Qué necesita y qué no está verificado {#what-it-needs-and-what-is-not-verified}

La opción necesita `ce:GetCostAndUsage` y `ce:ListCostAllocationTags`. Las dos
están en la política del repositorio (consulta
[Permisos de IAM](../reference/iam-permissions.md)).

No verificado contra AWS real:

- Las claves de etiqueta muestran gasto solo después de activarlas como
  etiquetas de asignación de costes en la cuenta de facturación (pagadora).
- Una cuenta miembro de una organización puede ver menos que la cuenta
  pagadora, y `ListCostAllocationTags` puede no responder desde una cuenta
  miembro.
- Que las respuestas tengan la forma que usan las pruebas. Las pruebas usan
  respuestas con la forma de las de Cost Explorer, comprobadas contra el
  modelo de servicio de botocore.

## La tendencia de costes de `--enable-cost-analysis` {#the-cost-trend-of---enable-cost-analysis}

`--enable-cost-analysis` es independiente de `--finops-checks` y de
`--finops-cost-allocation`. Además de sus estimaciones de la API AWS Pricing,
lee de Cost Explorer el coste facturado de cada servicio de los dos últimos
meses completos y añade una tabla a la hoja `Cost Analysis`. Las columnas están
en [Hoja Cost Analysis](../reference/outputs.md#cost-analysis-sheet).

- **Por cada cuenta, con las credenciales propias de esa cuenta.** Un escaneo de
  varias cuentas lee la factura de cada cuenta. Antes de v1.5.0 leía una sola
  factura, con las credenciales de la primera cuenta, y dividía la cifra de cada
  servicio entre los recursos de ese servicio.
- **Como máximo 2 solicitudes a Cost Explorer por cada cuenta**, sea cual sea el
  número de servicios: una para los dos meses, y una segunda solo para una página
  más de la respuesta. Esto se suma a como máximo 1 por cada cuenta para la
  validación de facturación. Una solicitud limitada (throttled) se reintenta,
  hasta 10 intentos en total, y cada reintento es una solicitud más. AWS cobra
  cada solicitud; consulta los
  [precios de Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).
  La línea del recuento antes del descubrimiento muestra esta parte como
  `cost trend: N`.
- **Una fila por cada cuenta y servicio, nunca una por cada recurso.** La cifra
  es el total facturado del servicio en la cuenta. No es el coste de un recurso y
  no se reparte entre recursos.
- **Los servicios se encuentran por sus nombres de facturación.** S3, SQS y SNS
  tienen tendencia, y la cifra de EC2 ya no incluye `Amazon EC2 Container
  Registry (ECR)` ni ningún otro servicio cuyo nombre de facturación contenga
  «EC2». La cifra de un servicio es la suma de los nombres de facturación que
  muestra la columna `Billing names counted`. `EC2 - Other` (volúmenes, gateways
  NAT, transferencia de datos) es un nombre de facturación distinto y no está en
  la fila de EC2.
- **Se compara mes con mes.** Se comparan el más antiguo y el más reciente de los
  dos meses completos anteriores a la ejecución, nunca un mes parcial con uno
  completo.
- **Una solicitud fallida es una advertencia.** Una solicitud denegada conserva
  la línea `Permissions:`; una que falla por otro motivo da una advertencia para
  esa cuenta, que entonces no tiene tendencia.

Migración desde versiones anteriores: las entradas de
`cost_analysis["cost_trends"]` del resultado de Python ya no tienen
`resource_id`. Hay una entrada por cada cuenta y servicio, con `account_id`,
`billing_names`, `resource_count`, `previous_month`, `current_month` y `unit` en
su lugar. Las cifras de las ejecuciones de varias cuentas cambian, igual que la
cifra de EC2 y los servicios que ahora tienen tendencia.

No verificado contra AWS real: las facturas de una cuenta real, lo que ven una
cuenta pagadora y una cuenta miembro, y si la respuesta cabe en una página.

## Lo que las comprobaciones no pueden ver {#what-the-checks-cannot-see}

- `FIN-004` no da ninguna duración. El listado de instancias no tiene una hora
  de detención fiable, así que una instancia detenida se lista sin importar
  cuánto tiempo lleva detenida.
- `FIN-005` no lee el estado de los destinos. Un balanceador de carga cuyos
  destinos están todos en mal estado es un pass. Leer el estado de los
  destinos necesitaría una llamada nueva a AWS.
- Un recurso listado aquí puede ser intencionado: por ejemplo, una instancia
  detenida a propósito o una instantánea que guarda una regla de retención.
- Las comprobaciones no muestran importes de dinero.
- No verificado contra AWS real: que los listados traigan los campos que cada
  comprobación necesita en todos los tipos de cuenta.

---
title: Comprobaciones FinOps
description: Seis comprobaciones FinOps fijas sobre los recursos que encuentra un escaneo (volúmenes sin conectar, direcciones sin asociar, instantáneas antiguas, instancias detenidas, balanceadores de carga sin destino, etiquetas de asignación de costes que faltan), sin ninguna llamada adicional a AWS.
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

Con `--template`, las comprobaciones no se ejecutan: InvenTag muestra un aviso
y no escribe ninguna hoja `FinOps`.

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

---
title: Análisis de red y seguridad
description: Qué añaden al informe de Excel las opciones de análisis de red y de grupos de seguridad de InvenTag, qué dejan fuera y cómo revisar VPC y grupos de seguridad.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Análisis de red y seguridad

**Para quién es:** quieres revisar VPC, subredes y grupos de seguridad con
InvenTag.

**Qué sabrás después de leerlo:** qué añaden al informe las opciones de
análisis.

## Qué añaden las opciones {#what-the-flags-add}

InvenTag tiene dos opciones para esto:

- `--enable-network-analysis`: VPC, subredes y cómo se usan.
- `--enable-security-analysis`: grupos de seguridad.

Cada opción añade una hoja al informe de Excel:

- `--enable-network-analysis` añade la hoja `Network Analysis`. Lista cada VPC
  con su bloque CIDR, las direcciones IP totales y disponibles, la utilización
  y el número de subredes, y después una tabla de subredes.
- `--enable-security-analysis` añade la hoja `Security Analysis`. Lista cada
  grupo de seguridad con el recuento de sus reglas, un nivel de riesgo y si
  tiene reglas permisivas, y después una tabla de cada regla.

Límites:

- Una hoja solo se escribe si el análisis encuentra VPC o grupos de seguridad.
- El informe de Word no tiene secciones de red ni de seguridad.
- Las ACL de red no forman parte de la hoja Security Analysis. Aparecen en la
  hoja `VPC`.
- Con `--template`, las opciones **no añaden hojas**: las plantillas de informe
  integradas no tienen esas hojas (lo comprobamos con `--template
  standard-bom`). Usa el diseño predeterminado o un archivo de diseño
  (`--excel-template`), que conserva las secciones `network_analysis` y
  `security_analysis`.
- El nivel de riesgo es una regla sencilla de InvenTag, no una evaluación de
  seguridad.

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

Lo que imprime una ejecución y las primeras filas de cada hoja, de una
ejecución sin conexión contra AWS simulado (datos de ejemplo):

```text title="Salida"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**Hojas:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

Hoja `Network Analysis`, primeras filas:

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**Hojas:** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

Hoja `Security Analysis`, primeras filas:

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

### Qué hace el análisis de red {#what-the-network-analysis-does}

- Una subred cuenta como pública cuando la tabla de rutas que usa (la suya, o la tabla principal de la VPC) tiene una ruta activa
  para `0.0.0.0/0` o `::/0` hacia una puerta de enlace de internet (`igw-`). Una VPC que tiene una puerta de enlace de internet
  pero ninguna ruta así no hace públicas sus subredes. Las hojas no muestran esta propiedad.
- `Total IPs` procede de los bloques CIDR de la VPC. `Available IPs` y `Utilization %` proceden de sus subredes, así que las tres columnas
  no cuadran entre sí, y una VPC sin subredes muestra 0 disponibles. Las direcciones IPv6 no se cuentan.
- `Associated Resources` cuenta los recursos cuyos datos de API nombran la VPC o la subred: instancias EC2, funciones Lambda en una VPC,
  recursos de RDS y ElastiCache. Los balanceadores de carga se cuentan para su VPC, no para una subred. Los grupos de seguridad, las ACL de red, las tablas de rutas y las puertas de enlace
  son la infraestructura propia de la VPC y no se cuentan.

  No verificado contra una prueba sin conexión: que `Associated Resources` cuente ElastiCache.
- Solo lee las VPC y subredes de las regiones que analizas. No comprueba las ACL de red, los grupos de seguridad, `MapPublicIpOnLaunch`,
  Direct Connect, las conexiones VPN, Network Firewall ni las rutas de peering.

### Qué hace el análisis de seguridad {#what-the-security-analysis-does}

- Cada regla recibe un nivel de riesgo a partir de la propia regla. Una regla abierta a `0.0.0.0/0` o `::/0` es **critical** (crítica)
  si permite todos los protocolos, todos los puertos o un rango que contiene 22, 23, 3389, 1433, 3306 o 5432. Por ejemplo, los puertos 20 a 25 son críticos.
  Es **high** (alta) si el rango tiene un puerto por debajo de 1024, y **medium** (media) para cualquier otro puerto. Una regla ICMP abierta a internet es medium.
  Un rango de origen más ancho que `/16` es medium, así que `10.0.0.0/8` es medium. Todo lo demás es low (baja).
- Las reglas de salida son siempre **low**. El tráfico de salida abierto es el valor predeterminado de AWS.
- El nivel de riesgo de un grupo es el más alto de sus reglas.
- Un grupo cuenta como no usado cuando ninguna interfaz de red lo usa, ningún otro grupo lo referencia y no es el grupo `default`.
  Un grupo al que solo hace referencia una plantilla de lanzamiento o un grupo de Auto Scaling parece no usado. Si no se pueden leer las interfaces de red,
  ningún grupo se considera no usado. La hoja no muestra esta propiedad.
- La columna `Has Permissive Rules` dice `Yes` cuando una regla de entrada está abierta a `0.0.0.0/0` o `::/0`. Una regla que hace referencia a otro grupo de seguridad
  o a una lista de prefijos aparece en la lista, pero InvenTag no mira lo que hay detrás de la referencia. Las ACL de red no se analizan.

### Hacer fallar un pipeline por reglas de riesgo {#fail-a-pipeline-on-risky-rules}

`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL` necesita `--enable-security-analysis`. InvenTag mira las reglas de grupos de seguridad abiertas a
`0.0.0.0/0` o `::/0`, de entrada y de salida. Si alguna tiene un nivel igual o superior al umbral, InvenTag escribe los informes, registra cada regla y sale con código 4:

```text
2 security group rule(s) at or above risk level LOW:
  - sg-57691d920ce0e0a5e: outbound All All 0.0.0.0/0 (low)
```

Como las reglas de salida son low, `--risk-threshold LOW` sale con código 4 por el grupo `default` de casi todas las VPC. `MEDIUM` y superiores ignoran las reglas de salida.
Solo cuentan las reglas de grupos de seguridad: las ACL de red y otros recursos nunca provocan el código 4. Los códigos 5 (`--fail-on-account-error`) y 6 (`--fail-if-empty`) tienen prioridad sobre el 4.

### Permisos {#permissions}

Ambos análisis hacen llamadas de solo lectura a EC2 en cada región analizada. Además de las llamadas habituales `ec2:Describe*` para VPC, subredes y grupos de seguridad,
necesitan `ec2:DescribeRouteTables` (subredes públicas) y `ec2:DescribeNetworkInterfaces` (grupos no usados). El archivo de política del repositorio las incluye.
Consulta [Permisos de IAM](../reference/iam-permissions.md). Sin ellas, el análisis continúa y omite ese detalle.

## Más detalle sobre los recursos de red {#more-detail-on-network-resources}

Los recursos de red forman parte de cada análisis normal. Con la plantilla
`standard-bom` aparecen en la hoja **VPC**: VPC, subredes, tablas de rutas,
ACL de red y grupos de seguridad, cada uno con sus etiquetas.

Para ver también su configuración, añade todos los campos que devolvió la API
de AWS:

```yaml
# .inventag/templates/network-review.yaml
format_version: 1
kind: report
name: network-review
description: Every field, for a network review
extends: standard-bom
spec:
  title: Network review
  excel:
    include_all_fields: true
```

```bash
inventag --template network-review --create-excel --account-regions us-east-1
```

La hoja VPC tiene entonces una columna por cada campo que devolvió la API de
AWS. Son detalladas pero no están resumidas. En una ejecución sin conexión
(datos de ejemplo):

La hoja VPC tiene 57 columnas. Las columnas `raw_data.*` de este ejemplo son:

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## Siguientes pasos {#next-steps}

- [Estado de las funciones](../getting-started/status.md)
- [Adaptar una plantilla](../templates/adapt-a-template.md)

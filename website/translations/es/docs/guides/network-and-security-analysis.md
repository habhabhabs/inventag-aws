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

```text title="Terminal"
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

- [Estado de las funciones y limitaciones conocidas](../getting-started/status.md)
- [Adaptar una plantilla](../templates/adapt-a-template.md)

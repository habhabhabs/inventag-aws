---
title: Analyse du réseau et de la sécurité
description: Ce que les options d’analyse du réseau et des groupes de sécurité ajoutent au rapport Excel, ce qu’elles omettent, et comment examiner les VPC et les groupes.
sidebar_position: 5
slug: /architecture/network-analysis
---

# Analyse du réseau et de la sécurité

**À qui s’adresse cette page :** vous voulez examiner des VPC, des sous-réseaux et des groupes de sécurité
avec InvenTag.

**Ce que vous saurez après lecture :** ce que les options d’analyse ajoutent à un rapport.

## Ce que les options ajoutent {#what-the-flags-add}

InvenTag propose deux options pour cela :

- `--enable-network-analysis` : les VPC, les sous-réseaux et leur utilisation.
- `--enable-security-analysis` : les groupes de sécurité.

Chaque option ajoute une feuille au rapport Excel :

- `--enable-network-analysis` ajoute la feuille `Network Analysis`. Elle liste chaque
  VPC avec son bloc CIDR, le nombre total d’adresses IP et celles disponibles, le taux d’utilisation et le
  nombre de sous-réseaux, puis un tableau des sous-réseaux.
- `--enable-security-analysis` ajoute la feuille `Security Analysis`. Elle liste
  chaque groupe de sécurité avec son nombre de règles, un niveau de risque et l’indication de règles
  permissives, puis un tableau de chaque règle.

Limites :

- Une feuille n’est écrite que si l’analyse trouve des VPC ou des groupes de sécurité.
- Le rapport Word n’a pas de sections réseau ni sécurité.
- Les ACL réseau ne font pas partie de la feuille Security Analysis. Elles figurent sur la
  feuille `VPC`.
- Avec `--template`, les options n’ajoutent **aucune feuille** : les modèles de rapport
  intégrés n’ont pas de telles feuilles (nous l’avons vérifié avec `--template standard-bom`).
  Utilisez la mise en page par défaut, ou un fichier de mise en page (`--excel-template`), qui conserve
  les sections `network_analysis` et `security_analysis`.
- Le niveau de risque est une règle simple d’InvenTag, pas une évaluation de sécurité.

```bash
inventag --create-excel --enable-network-analysis --enable-security-analysis
```

Ce qu’affiche une exécution, et les premières lignes de chaque feuille, issus d’une exécution hors ligne
sur un AWS simulé (données d’exemple) :

```text title="Terminal"
inventag - WARNING -   - No account specification method provided. Using default AWS credentials.
Performing network analysis...
Network analysis completed for 7 VPC resources
Performing security analysis...
Security analysis completed for 1 security groups
Data exported to bom_output/multi_account_bom_20261112_090000.xlsx
```

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

Feuille `Network Analysis`, premières lignes :

| VPC ID | VPC Name | CIDR Block | Total IPs | Available IPs | Utilization % | Subnet Count | Associated Resources |
|---|---|---|---|---|---|---|---|
| vpc-b790a8316b5a9b85e | vpc-b790a8316b5a9b85e | 172.31.0.0/16 | 65531 | 24545 | 0.0% | 6 | 1 |

**Feuilles :** `Summary`, `ATHENA`, `DYNAMODB`, `EC2`, `EVENTS`, `IAM`, `KMS`, `LAMBDA`, `S3`, `VPC`, `Network Analysis`, `Security Analysis`

Feuille `Security Analysis`, premières lignes :

| Security Group ID | Group Name | VPC ID | Risk Level | Inbound Rules | Outbound Rules | Associated Resources | Has Permissive Rules | Permissive Rule Details |
|---|---|---|---|---|---|---|---|---|
| sg-46eeda8dc8fa7955d | default | vpc-b790a8316b5a9b85e | low | 0 | 1 | 1 | No |  |

## Plus de détails sur les ressources réseau {#more-detail-on-network-resources}

Les ressources réseau font partie de chaque analyse normale. Avec le modèle `standard-bom`,
elles apparaissent sur la feuille **VPC** : VPC, sous-réseaux, tables de routage,
ACL réseau et groupes de sécurité, chacun avec ses étiquettes.

Pour voir aussi leur configuration, ajoutez tous les champs renvoyés par l’API AWS :

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

La feuille VPC a alors une colonne pour chaque champ renvoyé par l’API AWS. Ces colonnes sont
détaillées mais pas résumées. Dans une exécution hors ligne (données d’exemple) :

La feuille VPC compte 57 colonnes. Les colonnes `raw_data.*` de cet exemple sont :

```text
raw_data.AssignIpv6AddressOnCreation, raw_data.Associations, raw_data.AvailabilityZone, raw_data.AvailabilityZoneId, raw_data.AvailableIpAddressCount, raw_data.CidrBlock, raw_data.CidrBlockAssociationSet, raw_data.DefaultForAz, raw_data.Description, raw_data.DhcpOptionsId, raw_data.Entries, raw_data.GroupId, raw_data.GroupName, raw_data.InstanceTenancy, raw_data.IpPermissions, raw_data.IpPermissionsEgress, raw_data.Ipv6CidrBlockAssociationSet, raw_data.Ipv6Native, raw_data.IsDefault, raw_data.MapPublicIpOnLaunch, raw_data.NetworkAclId, raw_data.OwnerId, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsAAAARecord, raw_data.PrivateDnsNameOptionsOnLaunch.EnableResourceNameDnsARecord, raw_data.PrivateDnsNameOptionsOnLaunch.HostnameType, raw_data.Routes, raw_data.RouteTableId, raw_data.SecurityGroupArn, raw_data.State, raw_data.SubnetArn, raw_data.SubnetId, raw_data.Tags, raw_data.VpcId
```

## Étapes suivantes {#next-steps}

- [État des fonctionnalités et limites connues](../getting-started/status.md)
- [Adapter un modèle](../templates/adapt-a-template.md)

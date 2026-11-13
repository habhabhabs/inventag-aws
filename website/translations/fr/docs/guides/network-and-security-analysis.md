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

### Ce que fait l’analyse réseau {#what-the-network-analysis-does}

- Un sous-réseau compte comme public quand la table de routage qu’il utilise (la sienne, ou la table principale du VPC) a une route active
  pour `0.0.0.0/0` ou `::/0` vers une passerelle Internet (`igw-`). Un VPC qui a une passerelle Internet mais aucune route de ce type
  ne rend pas ses sous-réseaux publics. Les feuilles n’affichent pas cette propriété.
- `Total IPs` vient des blocs CIDR du VPC. `Available IPs` et `Utilization %` viennent de ses sous-réseaux : les trois colonnes ne concordent donc pas,
  et un VPC sans sous-réseau affiche 0 disponible. Les adresses IPv6 ne sont pas comptées.
- `Associated Resources` compte les ressources dont les données d’API nomment le VPC ou le sous-réseau : instances EC2, fonctions Lambda dans un VPC,
  ressources RDS et ElastiCache et équilibreurs de charge. Les groupes de sécurité, les ACL réseau, les tables de routage et les passerelles
  sont la plomberie propre du VPC et ne sont pas comptés.
- Elle ne lit que les VPC et sous-réseaux des régions que vous analysez. Elle ne vérifie pas les ACL réseau, les groupes de sécurité, `MapPublicIpOnLaunch`,
  Direct Connect, les connexions VPN, Network Firewall ni les routes d’appairage.

### Ce que fait l’analyse de sécurité {#what-the-security-analysis-does}

- Chaque règle reçoit un niveau de risque d’après la règle seule. Une règle ouverte à `0.0.0.0/0` ou `::/0` est **critical** (critique)
  si elle autorise tous les protocoles, tous les ports ou une plage qui contient 22, 23, 3389, 1433, 3306 ou 5432. Par exemple, les ports 20 à 25 sont critiques.
  Elle est **high** (élevée) si la plage contient un port inférieur à 1024, et **medium** (moyenne) pour tout autre port. Une règle ICMP ouverte à Internet est medium.
  Une plage source plus large que `/16` est medium : `10.0.0.0/8` est donc medium. Tout le reste est low (faible).
- Les règles sortantes sont toujours **low**. Le trafic sortant ouvert est le réglage par défaut d’AWS.
- Le niveau de risque d’un groupe est le plus élevé de ses règles.
- Un groupe compte comme inutilisé quand aucune interface réseau ne l’utilise, qu’aucun autre groupe n’y fait référence et qu’il n’est pas le groupe `default`.
  Un groupe auquel seul un modèle de lancement ou un groupe Auto Scaling fait référence paraît inutilisé. Si les interfaces réseau ne peuvent pas être lues,
  aucun groupe n’est déclaré inutilisé. La feuille n’affiche pas cette propriété.
- La colonne `Has Permissive Rules` indique `Yes` quand une règle entrante est ouverte à `0.0.0.0/0` ou `::/0`. Une règle qui fait référence à un autre groupe de sécurité
  ou à une liste de préfixes est listée, mais InvenTag ne regarde pas ce qu’il y a derrière la référence. Les ACL réseau ne sont pas analysées.

### Faire échouer un pipeline sur les règles à risque {#fail-a-pipeline-on-risky-rules}

`--risk-threshold LOW|MEDIUM|HIGH|CRITICAL` nécessite `--enable-security-analysis`. InvenTag examine les règles de groupes de sécurité ouvertes à
`0.0.0.0/0` ou `::/0`, entrantes et sortantes. Si l’une a un niveau égal ou supérieur au seuil, InvenTag écrit les rapports, journalise chaque règle et se termine avec le code 4 :

```text
2 security group rule(s) at or above risk level LOW:
  - sg-57691d920ce0e0a5e: outbound All All 0.0.0.0/0 (low)
```

Comme les règles sortantes sont low, `--risk-threshold LOW` se termine avec le code 4 à cause du groupe `default` de presque tous les VPC. `MEDIUM` et au-dessus ignorent les règles sortantes.
Seules les règles de groupes de sécurité comptent : les ACL réseau et les autres ressources ne déclenchent jamais le code 4. Les codes 5 (`--fail-on-account-error`) et 6 (`--fail-if-empty`) l’emportent sur le 4.

### Autorisations {#permissions}

Les deux analyses effectuent des appels EC2 en lecture seule dans chaque région analysée. Outre les appels habituels `ec2:Describe*` pour les VPC, sous-réseaux et groupes de sécurité,
elles ont besoin de `ec2:DescribeRouteTables` (sous-réseaux publics) et de `ec2:DescribeNetworkInterfaces` (groupes inutilisés). Le fichier de politique du dépôt les inclut.
Voir [Autorisations IAM](../reference/iam-permissions.md). Sans elles, l’analyse continue et omet ce détail.

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

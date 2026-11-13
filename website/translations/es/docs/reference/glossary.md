---
title: Glosario
description: Qué significan de los términos de la documentación de InvenTag, del archivo de cuentas y el ARN a la política de etiquetas y la protección de solo lectura.
sidebar_position: 6
---

# Glosario

**Para quién es:** cualquiera que encuentre una palabra desconocida en esta documentación.

La documentación usa cada término de abajo con un solo significado.

| Término | Significado |
|---|---|
| **Archivo de cuentas** | Un archivo YAML o JSON, que se pasa con `--accounts-file`, con la lista de cuentas de AWS que se van a analizar. Consulta [Archivos de configuración](./configuration-files.md#accounts-file). |
| **ARN** | Amazon Resource Name: el ID único que AWS asigna a un recurso, por ejemplo `arn:aws:s3:::acme-app-logs`. |
| **Cuenta de AWS** | Una cuenta de AWS, identificada por un ID de cuenta de 12 dígitos como `123456789012`. |
| **BOM** | Lista de materiales (bill of materials): la lista de recursos que InvenTag escribe en Excel o Word. |
| **Conforme** | Un recurso que tiene todas las etiquetas que exige una política de etiquetas, con valores permitidos. |
| **Plantilla de configuración** | Una plantilla con `kind: config`: qué cuentas y regiones analizar, qué archivos escribir y qué plantilla de informe y política de etiquetas usar. |
| **Cost Explorer** | El servicio de AWS que informa del gasto. InvenTag lo llama para detectar servicios con gasto; AWS cobra por solicitud. |
| **Cadena de credenciales** | El orden en que las herramientas de AWS buscan credenciales: variables de entorno, luego perfiles y luego roles de IAM. |
| **Código de salida** | El número que devuelve un comando al terminar. `0` significa correcto; InvenTag usa `1` para errores, `2` para opciones no válidas o incompatibles, `3` para infracciones de la política de etiquetas, `4` para reglas de grupos de seguridad al nivel de `--risk-threshold` o por encima, `5` para una cuenta que no se pudo analizar por completo (con `--fail-on-account-error`) y `6` cuando no hay nada que informar (con `--fail-if-empty`). Si se aplica más de uno, primero va el 5, luego el 6, después el 3 y por último el 4. Consulta [Códigos de salida](./cli.md#exit-codes). |
| **IAM** | AWS Identity and Access Management: usuarios, roles y las políticas que dicen qué pueden hacer. |
| **IAM Identity Center** | El servicio de AWS para el inicio de sesión único (SSO) en cuentas de AWS. Se llamaba AWS SSO. |
| **Rol de IAM** | Una identidad con permisos que otras identidades pueden asumir durante un tiempo corto. |
| **moto** | Una biblioteca de Python que imita AWS en tu equipo. Las salidas de ejemplo de la documentación proceden de ejecuciones contra moto. |
| **OIDC** | OpenID Connect: permite que un sistema de CI como GitHub Actions obtenga credenciales de AWS de corta duración sin claves almacenadas. |
| **Fuera de alcance** | Un recurso que una política de etiquetas no comprueba, por su configuración de `scope`. |
| **Protección de solo lectura** | La parte de InvenTag que comprueba cada llamada a AWS antes de enviarla y bloquea todo lo que no sea una lectura. Siempre activa. |
| **Región** | Una ubicación geográfica de AWS, escrita como un código como `us-east-1` o `eu-west-1`. |
| **Plantilla de informe** | Una plantilla con `kind: report`: el título, los colores, las columnas, las hojas y las secciones de los archivos de Excel y Word. |
| **Datos de ejemplo** | Salida de ejecuciones de InvenTag contra moto, con cuentas y recursos inventados. Se usa en estas páginas. |
| **Instantánea** | Un archivo JSON en `bom_output/state/` que registra lo que encontró una ejecución, para poder comparar ejecuciones. |
| **Etiqueta** | Una clave y un valor asociados a un recurso de AWS, por ejemplo `Owner=platform`. Las claves distinguen mayúsculas y minúsculas. |
| **Política de etiquetas** | Una plantilla con `kind: tag-policy`: las etiquetas que deben tener los recursos y los valores permitidos. |
| **Plantilla** | Un archivo YAML pequeño que controla una parte de una ejecución: una plantilla de informe, una política de etiquetas o una plantilla de configuración. Consulta [Plantillas](../templates/index.md). |
| **Limitación de solicitudes (throttling)** | Cuando AWS ralentiza o rechaza solicitudes porque llegan demasiadas a la vez. |

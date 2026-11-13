---
title: Qué es InvenTag
description: Qué hace InvenTag en una ejecución (encontrar recursos de AWS, revisar etiquetas, escribir informes en Excel y Word), qué escribe y qué no es.
sidebar_position: 1
---

# Qué es InvenTag

**Para quién es:** cualquiera que esté decidiendo si InvenTag encaja en su trabajo.

**Qué sabrás después de leerlo:** qué hace una ejecución, qué cambia (solo
archivos de tu disco) y dónde están sus límites.

## Tres preguntas, un informe {#three-questions-one-report}

InvenTag responde tres preguntas sobre tus cuentas de AWS:

1. **¿Qué hay?** Una lista de recursos de todas las cuentas y regiones.
2. **¿Está bien etiquetado?** Columnas de etiquetas en el informe y, con una
   [plantilla de política de etiquetas](../templates/index.md), una comprobación de
   las etiquetas obligatorias y los valores permitidos.
3. **¿Qué cambió desde la última vez?** Cada ejecución guarda una instantánea para poder
   comparar ejecuciones. Consulta [Seguir los cambios entre ejecuciones](../guides/track-changes.md).

La respuesta es una lista de materiales (BOM): un libro de Excel, un documento de Word
o ambos.

## Cómo funciona una ejecución {#how-a-run-works}

```text
your AWS credentials
        |
        v
  1. find resources   --> List/Describe/Get calls per service,
        |                 the Resource Groups Tagging API, Cost Explorer
        v
  2. tidy and enrich  --> service names, IDs, tags
        |
        v
  3. check tags       --> only when a tag policy is active
        |
        v
  4. write files      --> bom_output/*.xlsx, *.docx, state/ snapshot
```

1. **Credenciales.** InvenTag usa la cadena de credenciales normal de AWS: un perfil,
   variables de entorno, una sesión de IAM Identity Center (SSO) o un rol de IAM.
   También puede asumir un rol en otras cuentas.
2. **Descubrimiento.** Para cada cuenta y región llama a interfaces de programación
   de aplicaciones (API) de AWS de solo lectura. Por defecto también llama a
   `GetCostAndUsage` de Cost Explorer para detectar los servicios con gasto. AWS cobra
   las solicitudes a la API de Cost Explorer; `--no-billing-validation` desactiva esas llamadas.
3. **Procesamiento.** Normaliza los nombres e ID de los servicios y recopila las etiquetas.
4. **Salida.** Escribe archivos en la carpeta de salida (`bom_output/` por defecto)
   y una instantánea en `bom_output/state/`.

## Qué cambia {#what-it-changes}

Solo archivos de tu disco. InvenTag lee tus cuentas de AWS; nunca las
modifica.

Una **protección de solo lectura** revisa cada llamada a AWS antes de enviarla. Se
bloquean las llamadas que no son de lectura (`List`, `Describe`, `Get` y similares), y también
las lecturas que devolverían secretos o contenido de archivos, como leer el valor de un
secreto o descargar un objeto de S3. No puedes desactivar la protección.

Aun así, dale a InvenTag una identidad de IAM de solo lectura. Dos redes de seguridad independientes
son mejor que una: [Configurar el acceso de solo lectura](../guides/read-only-access.md).

## Qué no es {#what-it-is-not}

- **No es una herramienta de cumplimiento normativo.** InvenTag puede reunir evidencias, como un
  inventario y la cobertura de etiquetas. No evalúa ni certifica el cumplimiento de
  SOC 2, PCI DSS, HIPAA, RGPD ni ningún otro marco.
- **No es una herramienta de gestión de costes.** Lista recursos y etiquetas, y no
  sigue tu factura. La opción `--enable-cost-analysis` añade una hoja Cost
  Analysis con costes mensuales estimados a partir de la API AWS Pricing. Son
  solo estimaciones, no tu factura.
- **No está afiliado a AWS.**
- **No es completo.** Tiene código de descubrimiento propio para 24 servicios de AWS, no para
  todos, y nunca se ha probado con una cuenta real de AWS.
  [Estado de las funciones y limitaciones conocidas](./status.md) enumera los límites.

## Siguientes pasos {#next-steps}

- [Instalar InvenTag](./installation.md)
- [Generar tu primer informe](./quick-start.md)

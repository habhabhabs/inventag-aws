---
title: Contribuir a InvenTag
description: Prepara un entorno de desarrollo para InvenTag, ejecuta las pruebas y los linters, compila el sitio de documentación y abre una solicitud de cambios.
sidebar_position: 1
---

# Contribuir a InvenTag

**Para quién es:** quieres corregir un error, añadir una función o mejorar la
documentación.

**Qué podrás hacer después de leerlo:** preparar el código, ejecutar las
comprobaciones que usa el proyecto y abrir una solicitud de cambios (pull
request) fácil de revisar.

## Antes de empezar {#before-you-start}

1. Busca un [problema (issue)](https://github.com/habhabhabs/inventag-aws/issues)
   existente. Si no hay ninguno, abre uno y describe el cambio.
2. Para un cambio grande, espera la respuesta de un responsable del proyecto
   antes de escribir mucho código.

## Preparación {#set-up}

```bash
git clone https://github.com/habhabhabs/inventag-aws.git
cd inventag-aws
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # includes moto
pip install -e .          # optional: gives you the `inventag` command
git checkout -b fix/short-description
```

Prefijos de rama: `feat/`, `fix/`, `docs/`, `refactor/`, `test/`.

## Ejecutar las comprobaciones {#run-the-checks}

```bash
black --check scripts/ inventag/
flake8 scripts/ inventag/ --count --select=E9,F63,F7,F82 --show-source --statistics
python -m pytest -q
```

CI ejecuta los mismos comandos `black --check` y `flake8`, y después las
pruebas en Python 3.11, 3.12, 3.13, 3.14 y 3.15. La suite completa
(`python -m pytest -q`) tarda unos minutos, pasa en `main` (con las 9 pruebas de
rendimiento excluidas) y no necesita ninguna cuenta de AWS: las pruebas usan moto
o clientes simulados con credenciales falsas. Un cambio debe mantenerla en verde. Ejecuta las pruebas
de rendimiento solo cuando se pida: `python -m pytest -m performance`.
Ejecuta `pip-audit -r requirements.txt` cuando cambies una dependencia; CI
falla ante cualquier aviso nuevo.

**Nunca ejecutes las pruebas contra una cuenta real de AWS por accidente.**
Elimina `AWS_PROFILE` y las claves reales del entorno, o usa moto.

## Trabajar con plantillas {#work-on-templates}

- Las plantillas integradas están en `inventag/templating/builtin/`. Cada una
  necesita una prueba en `tests/integration/templating/` que la genere.
- El formato de plantilla se describe una sola vez, en
  `inventag/templating/schema.py`. Después de cambiarlo, regenera la
  referencia de la documentación: `python -m inventag.templating.reference --write`.
  Una prueba unitaria falla si lo olvidas.
- Las salidas de ejemplo de las páginas de la documentación proceden de
  `scripts/docs/generate_example_outputs.py`, que ejecuta la CLI real contra
  moto. Después de un cambio de comportamiento, ejecuta `pip install pillow` y
  `python scripts/docs/generate_example_outputs.py`, y confirma el resultado.
  `--check` te indica si las páginas están desactualizadas. Las imágenes
  necesitan LibreOffice (`soffice`) y `pdftoppm`.

## Trabajar con la documentación {#work-on-the-docs}

La documentación son archivos Markdown en `docs/`, publicados con Docusaurus
desde `website/`.

```bash
cd website
npm ci
npm run build          # fails on broken links and missing SEO metadata
npm run check:links    # checks links in the built site
npm run start          # local preview at http://localhost:3000/inventag-aws/
```

Reglas de redacción:

- Cada página tiene un `title` y un `description` únicos en su front matter y
  exactamente un encabezado `#`.
- Empieza indicando para quién es la página y qué podrá hacer el lector.
- Frases cortas, voz activa, palabras sencillas. Explica cualquier jerga.
- Cada comando, opción y salida debe coincidir con el código. Ejecútalo antes
  de escribirlo y etiqueta la salida de ejemplo como datos de ejemplo.
- Sin cifras inventadas, sin superlativos, sin afirmaciones de cumplimiento ni
  de certificación.
- Encabezados en orden, tablas con filas de encabezado, texto alternativo en
  las imágenes y ningún significado transmitido solo con emojis o con color.

La barra lateral se genera a partir de las carpetas y del `_category_.json` de
cada carpeta.

## Confirmar y abrir una solicitud de cambios {#commit-and-open-a-pull-request}

Usa [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(templates): add landscape option for Word reports
fix(discovery): include EC2 instances in comprehensive discovery
docs: explain tag policy scopes
```

En la solicitud de cambios, indica qué cambió, cómo lo probaste y qué
documentación actualizaste. Actualiza el [Estado de las funciones](../getting-started/status.md)
cuando corrijas o añadas una función.

## Siguientes pasos {#next-steps}

- [Cómo encaja el código](./architecture.md)
- [Seguridad](../security/index.md)

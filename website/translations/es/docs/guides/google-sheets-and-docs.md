---
title: Salida a Google Sheets y Docs
description: Cómo escribir el inventario de InvenTag en una hoja de cálculo de Google Sheets y en un Google Doc, cómo iniciar sesión, quién puede abrir los archivos y qué no se ha verificado con Google real.
sidebar_position: 9
---

# Salida a Google Sheets y Docs

**Para quién es:** quieres el inventario en Google Drive en lugar de, o además
de, un archivo de Excel o Word.

**Qué sabrás después de leerlo:** cómo instalar las bibliotecas de Google, cómo
iniciar sesión, qué opciones usar, quién puede abrir los archivos y qué no se
ha verificado.

## Qué obtienes {#what-you-get}

- `--create-google-sheets` escribe el mismo libro que `--create-excel` (mismas
  hojas, mismo orden de filas, mismas plantillas) como una hoja de cálculo de
  Google Sheets.
- `--create-google-docs` escribe el mismo informe que `--create-word` como un
  Google Doc.
- InvenTag genera primero los informes de Excel y Word y los copia, de modo que
  un `--template` cambia los archivos de Google exactamente igual que los
  locales.
- La ejecución imprime la URL de cada archivo.

## Instala el complemento de Google {#install-the-google-add-on}

Escribir en Google requiere algunos paquetes de Python adicionales (las
bibliotecas de inicio de sesión y de API de Google). La mayoría de las personas
nunca usa la salida a Google, así que estos paquetes no se instalan con
InvenTag por defecto. Los añades una vez con este comando:

```bash title="Terminal"
pip install "inventag-aws[google]"
```

Léelo como "instala InvenTag, más su complemento de Google". Lo que va entre
corchetes es el nombre del complemento. No es un marcador de posición, así que
escríbelo exactamente como se muestra, con las comillas (zsh, el shell
predeterminado de macOS, las necesita).

- **Ya tienes InvenTag.** Ejecuta el mismo comando. pip conserva tu InvenTag y
  solo añade los paquetes de Google.
- **Lo instalaste con pipx.** Ejecuta `pipx install "inventag-aws[google]"` o
  `pipx inject inventag-aws google-api-python-client google-auth google-auth-oauthlib`
  para añadir los paquetes al InvenTag que ya tienes.
- **Usas un entorno virtual.** Actívalo primero, para que los paquetes queden
  junto a InvenTag.

No necesitas el complemento para Excel, Word ni nada más. Si usas una opción de
Google sin él, InvenTag se detiene con el código de salida 2, indica qué
paquete falta e imprime este comando.

## Inicia sesión {#sign-in}

Elige una:

| Forma | Opción | Cuándo usarla |
|---|---|---|
| Clave de cuenta de servicio | `--google-credentials key.json` | Ejecuciones programadas y CI |
| Tu propia cuenta de Google | `--google-oauth-client client_secret.json` | Una ejecución en tu portátil. Se abre un navegador una vez y el token se guarda en `~/.config/inventag/google-token.json`, legible solo por ti. |
| Credenciales predeterminadas de la aplicación | ninguna | Ejecutaste `gcloud auth application-default login` |

Habilita las API de Google Sheets, Google Docs y Google Drive en el proyecto de
Google Cloud de las credenciales.

El alcance es `drive.file`: InvenTag solo puede tocar los archivos que creó.
Con `--google-folder-id` pide el alcance completo de Drive, porque tiene que
colocar un archivo en una carpeta que ya existe.

## Quién puede abrir los archivos {#who-can-open-the-files}

Los archivos son **privados** para la cuenta que los crea. No se comparte nada
a menos que lo pidas.

```bash title="Terminal"
inventag --create-google-sheets --create-google-docs \
  --google-credentials key.json \
  --google-share-with you@example.com \
  --google-share-with team@example.com --google-share-role commenter \
  --google-folder-id 1AbCdEfGh \
  --google-title "AWS inventory, May"
```

- `--google-share-with EMAIL` se puede repetir. `--google-share-role` establece
  `reader` (por defecto), `commenter` o `writer` para todos ellos.
- `--google-share-anyone` hace que los archivos sean legibles para cualquiera
  que tenga el enlace. Úsalo solo con datos que publicarías.
- Una cuenta de servicio es propietaria de lo que crea, en su propio Drive,
  donde tú no puedes abrirlo. Si inicias sesión con una cuenta de servicio y no
  indicas ni `--google-share-with` ni `--google-folder-id`, InvenTag te avisa de
  ello.
- `--google-share-with`, `--google-share-role`, `--google-share-anyone`,
  `--google-folder-id` y `--google-title` sin `--create-google-sheets` o
  `--create-google-docs` se detienen con el código de salida 2.

## Las credenciales nunca se registran {#credentials-are-never-logged}

La ruta del archivo de clave no se imprime, y los secretos que parecen claves
privadas de Google, tokens de acceso, tokens de actualización o secretos de
cliente se enmascaran en cada línea del registro, incluso con `--debug`. Los
mensajes de error de las bibliotecas de Google se reducen al tipo de error,
porque pueden citar el archivo de clave.

## Límites {#limits}

- Una celda de Google Sheets admite hasta 50.000 caracteres y una hoja de
  cálculo hasta 10 millones de celdas. Un inventario muy grande puede
  superarlos; la ejecución falla entonces con el error de Google.
- Las tablas del informe de Word muestran hasta 50 recursos por servicio por
  defecto (`max_rows`), y lo mismo ocurre con el Google Doc.
- Los valores de las celdas se escriben como texto, de modo que un valor de
  etiqueta que empieza por `=` no se ejecuta como fórmula.

## Qué no se ha verificado {#what-is-not-verified}

Todas las pruebas usan clientes de Google simulados. **Ninguna prueba se ha
ejecutado contra las API reales de Google**, porque eso requiere una cuenta de
Google. En concreto, las posiciones que InvenTag calcula al rellenar las tablas
de un Google Doc se comprueban contra las reglas de la API de Docs tal como las
interpretamos, no contra el servicio real. Prueba primero con una cuenta
pequeña y comunica cualquier problema con el diseño del Doc como una incidencia
(issue).

## Siguientes pasos {#where-to-next}

- [Ejecutar un análisis](./run-a-scan.md)
- [Referencia de la CLI](../reference/cli.md#output)
- [Plantillas de informe](../templates/index.md)

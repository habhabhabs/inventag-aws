---
title: Salida a Google Sheets y Docs
description: "Escribe el inventario de InvenTag en Google Sheets y Google Docs: inicio de sesión, quién abre los archivos, cómo probarlo con tu propia cuenta de Google y qué no se ha verificado con Google real."
sidebar_position: 9
---

# Salida a Google Sheets y Docs

**Para quién es:** quieres el inventario en Google Drive en lugar de, o además
de, un archivo de Excel o Word.

**Qué sabrás después de leerlo:** cómo instalar las bibliotecas de Google, cómo
iniciar sesión, qué opciones usar, quién puede abrir los archivos, cómo probar la salida con tu propia cuenta de Google y qué no se
ha verificado.

## Qué obtienes {#what-you-get}

- `--create-google-sheets` escribe el mismo libro que `--create-excel` (mismas
  hojas, mismo orden de filas) como una hoja de cálculo de
  Google Sheets.
- `--create-google-docs` escribe el mismo informe que `--create-word` como un
  Google Doc.
- InvenTag genera primero los informes de Excel y Word y los copia. Con
  `--template`, InvenTag no escribe ningún archivo de Google: registra que se omite el formato y la ejecución termina con el código 0.
- La ejecución imprime la URL de cada archivo, por ejemplo `Google Sheet: https://docs.google.com/spreadsheets/d/...` y `Google Doc: https://docs.google.com/document/d/...`.
- Con `--per-account-reports`, InvenTag crea un par de archivos por cuenta. El título termina con ` - ` y el ID de la cuenta, y las líneas de URL son `Google Sheet: [123456789012] https://...` y `Google Doc: [123456789012] https://...`.
- Si una ejecución no encuentra recursos, no crea ningún archivo de Google.

No verificado contra Google real: que los archivos se parezcan a los informes de Excel y Word y que las URL tengan esta forma.

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

No verificado contra pip y pipx: los comandos de instalación del complemento de Google.

## Inicia sesión {#sign-in}

Elige una:

| Forma | Opción | Cuándo usarla |
|---|---|---|
| Clave de cuenta de servicio | `--google-credentials key.json` | Ejecuciones programadas y CI |
| Tu propia cuenta de Google | `--google-oauth-client client_secret.json` | Una ejecución en tu portátil. Se abre un navegador una vez y el token se guarda en `~/.config/inventag/google-token.json`, legible solo por ti. |
| Credenciales predeterminadas de la aplicación | ninguna | Ejecutaste `gcloud auth application-default login` |

Habilita las API de Google Sheets, Google Docs y Google Drive en el proyecto de
Google Cloud de las credenciales.

InvenTag lee el archivo de clave o el archivo de cliente OAuth antes de analizar AWS, así que un archivo incorrecto detiene la ejecución de inmediato con el código de salida 2 y un mensaje que empieza por `inventag: error: Google:`.

El alcance es `drive.file`: InvenTag solo puede tocar los archivos que creó.
Con `--google-folder-id` pide el alcance completo de Drive, porque tiene que
colocar un archivo en una carpeta que ya existe.

No verificado contra Google real: el inicio de sesión en el navegador, el token guardado, las credenciales predeterminadas de la aplicación y las API que hay que habilitar.

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

No verificado contra Google real: qué permite el alcance `drive.file`, que los archivos nuevos sigan siendo privados y el uso compartido.

## Las credenciales nunca se registran {#credentials-are-never-logged}

La ruta del archivo de clave no se imprime, y los secretos que parecen claves
privadas de Google, tokens de acceso, tokens de actualización o secretos de
cliente se enmascaran en cada línea del registro, incluso con `--debug`. Los
mensajes de error de las bibliotecas de Google se reducen al tipo de error,
porque pueden citar el archivo de clave.

## Límites {#limits}

- Una celda de Google Sheets admite hasta 50.000 caracteres. InvenTag corta el texto más largo en 49.000 caracteres. Una hoja de cálculo admite hasta 10 millones de celdas y una hoja hasta 18.278 columnas.

  No verificado contra Google real: los límites de celdas, tamaño y columnas.
- InvenTag cuenta las celdas antes de llamar a Google. Si el informe es demasiado grande, no crea nada y lo dice, y la ejecución termina con el código 1. Los archivos de Excel y Word se escriben igualmente. Por ejemplo:
  `The report has 12,000,000 cells; a Google spreadsheet allows 10,000,000. No
  spreadsheet was created. Send fewer resources (filters or an account subset)
  or use the Excel report.`
- InvenTag envía una hoja grande en varias solicitudes, cada una con 2000 filas como máximo y alrededor de 1 millón de caracteres.
- Si Google responde «429 too many requests», InvenTag registra `Google rate limit
  reached; waiting 5 seconds` y lo intenta de nuevo. Espera 5, 10, 20, 40 y después 60 segundos antes del último intento.

  No verificado contra Google real: el tamaño de las solicitudes y que las esperas tras un 429 sean suficientemente largas.
- Si una llamada falla después de crear el archivo, la ejecución termina con el código 1 y el mensaje da la URL del archivo a medio escribir: `The spreadsheet was already
  created and may be incomplete: <url> (delete it in Google Drive).` Lo mismo vale para un Google Doc. Borra ese archivo y vuelve a ejecutar.
- Las tablas del informe de Word muestran hasta 50 recursos por servicio por
  defecto (`max_rows_per_service` en una plantilla de informe, `max_rows` en un archivo de diseño), y lo mismo ocurre con el Google Doc.
- Los valores de las celdas se escriben como texto, de modo que un valor de
  etiqueta que empieza por `=` no se ejecuta como fórmula.

No verificado contra Google real: el texto que empieza por `=` se guarda como texto.

## Qué no se ha verificado {#what-is-not-verified}

La mayoría de las pruebas usan clientes de Google simulados. **No hemos registrado ninguna ejecución con las API reales de Google**, porque eso requiere una cuenta de Google. En particular, las posiciones que InvenTag calcula al rellenar las tablas de un Google Doc se comprueban con las reglas de la API de Docs tal como las entendemos, no con el servicio real. Prueba primero con una cuenta pequeña y notifica como problema (issue) cualquier fallo en el diseño del Doc. Cada sección anterior que depende de Google indica qué no se ha verificado.

## Compruébalo con tu propia cuenta de Google {#check-it-against-your-own-google-account}

El repositorio tiene un script que hace la prueba con Google real por ti. Construye un entorno ficticio con moto (una simulación de AWS), así que no necesita una cuenta de AWS y solo toca Google. Ejecuta InvenTag con `--create-google-sheets` y `--create-google-docs`, vuelve a leer los archivos desde Google y los compara con los archivos de Excel y Word creados en la misma ejecución. Imprime una tabla PASS o FAIL, las dos URL y `RESULT: PASS` o `RESULT: FAIL`. El código de salida es 0 si pasa.

Ejecútalo desde una copia del repositorio.

1. Instala las bibliotecas de Google y moto:

   ```bash title="Terminal"
   pip install "inventag-aws[google]"
   pip install moto
   ```

2. En el proyecto de Google Cloud de tus credenciales, habilita la API de Google Sheets, la API de Google Docs y la API de Google Drive. Si alguna está desactivada, Google responde HTTP 403 y el script nombra la API que debes habilitar.
3. Crea un cliente OAuth de tipo «Desktop app», descárgalo como `client_secret.json` y ejecuta:

   ```bash title="Terminal"
   python scripts/google_live_test.py --google-oauth-client client_secret.json --large
   ```

   Se abre un navegador una sola vez. Si la aplicación está en estado «Testing», añade tu cuenta en OAuth consent screen, Test users.

No verificado contra Google Cloud: los pasos de la consola para habilitar las API, crear el cliente OAuth y añadir usuarios de prueba.

Para usar una clave de cuenta de servicio, pasa `--google-credentials key.json`. La cuenta de servicio es la propietaria de los archivos en su propio Drive, así que añade `--share-with you@example.com` si quieres abrirlos.

| Opción | Qué hace |
|---|---|
| `--large` | Prueba también una hoja de 20.000 filas y una tabla de 300 filas en el Doc. Cuenta las llamadas a la API e inyecta dos respuestas «429» para demostrar el reintento. |
| `--share-with EMAIL` | Comparte los archivos (reader) con esta dirección y comprueba que solo esa dirección y el propietario pueden abrirlos. Repítela para más. |
| `--keep` | Deja los archivos en Drive. De forma predeterminada, el script mueve a la papelera de Drive todos los archivos que creó al final. |
| `--folder-id ID` | Crea también un par de archivos en esta carpeta de Drive. Esto necesita el alcance completo de Drive. Con `--google-oauth-client`, borra antes `~/.config/inventag/google-token.json`, para que vuelva a pedirlo. |

Sin opción de inicio de sesión, el script usa las credenciales predeterminadas de la aplicación (ADC). Google bloquea el cliente de inicio de sesión de `gcloud` para los alcances de Drive, Docs y Sheets, así que aquí también necesitas tu propio archivo de cliente OAuth. Ejecuta `python
scripts/google_live_test.py --help` para ver el comando exacto de `gcloud`. No hemos verificado esa vía. Es preferible el cliente OAuth.

El script comprueba esto:

- La hoja de cálculo y el Doc existen y coinciden con la URL impresa.
- Los nombres y el orden de las hojas, las filas y las columnas, y cada celda coinciden con el archivo de Excel.
- El texto que empieza por `=` vuelve como texto, no como fórmula.
- El texto largo, con acentos y CJK, y una hoja vacía se conservan.
- La fila de encabezado está en negrita y con color, y las filas superiores están inmovilizadas.
- Los encabezados y cada celda de tabla del Doc coinciden con el archivo de Word.
- Ambos archivos son privados para la cuenta (y para las direcciones de `--share-with`).

Si lo ejecutas, envíanos la tabla final. Cambiaremos esta página solo después de un resultado correcto en una cuenta real.

## Siguientes pasos {#where-to-next}

- [Ejecutar un análisis](./run-a-scan.md)
- [Referencia de la CLI](../reference/cli.md#output)
- [Plantillas de informe](../templates/index.md)

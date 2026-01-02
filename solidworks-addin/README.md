# TinyMRP SolidWorks Add-in

Add-in para SolidWorks que reproduce la UI del macro de TinyMRP (MODELS/DRAWINGS, carpeta de salida, botones BOM/Freeze/Unfreeze y flags "Overwrite"/"Top level only") y conecta con los endpoints de TinyMRP para autenticar, reservar PN y lanzar docpacks.

## Características

- **Autenticación persistente** contra TinyMRP con token (`/login?include_auth_token=1`), almacenamiento en `%AppData%/TinyMRP/addin_state.json` y reuso automático en sesiones posteriores.
- **UI de trabajo** en el task pane: listas de MODELS y DRAWINGS, carpeta de salida basada en `FILES_LOCAL_ROOT`, botones de BOM/Freeze/Unfreeze y banderas `Overwrite`/`Top level only`.
- **Opciones dinámicas** leídas desde `GET /api/docpacks/options` para poblar tipos de archivo y procesos.
- **Generación de paquetes** vía `POST /api/docpacks/build`, guardando en `FILES_LOCAL_ROOT` (ej. `C:\CADEXPORT\docpacks`) y mostrando el enlace HTTP armado con `FILES_URL_PREFIX`.
- **Reserva de PN** contra el nuevo endpoint (configurable, por defecto `/api/pn/reserve`); al recibir el PN se renombra la configuración activa y se actualizan propiedades personalizadas `PN`/`REV` antes de exportar.

## Estructura

- `TinyMRP.SolidWorksAddin.sln` — solución VS.
- `TinyMRP.SolidWorksAddin.csproj` — proyecto .NET Framework 4.8 con WinForms y referencias a `SolidWorks.Interop.*` (se busca en `$(ProgramFiles)\SOLIDWORKS Corp\SOLIDWORKS\api\redist`).
- `SwAddin.cs` — clase `ISwAddin` con registro COM, task pane y bootstrap del cliente.
- `Services/` — `TinyMrpClient` (HTTP, CSRF, tokens, docpacks, reserva de PN), `SolidWorksExportService` (propiedades PN/REV, freeze/unfreeze, renombrado), `TinyMrpTokenStore` (persistencia en disco).
- `UI/MainPaneControl.cs` — task pane con la UI del macro y los controles de exportación/docpack.
- `App.config` — valores predeterminados de `TinyMrpBaseUrl`, `FILES_LOCAL_ROOT`, `FILES_URL_PREFIX` y endpoint de reserva.

## Configuración

1. Ajusta `App.config` con la URL de TinyMRP, `FILES_LOCAL_ROOT` (p. ej. `C:\CADEXPORT`) y `FILES_URL_PREFIX` (p. ej. `http://localhost:5001/Deliverables`).
2. Asegúrate de que las DLLs de SolidWorks interop estén en `$(ProgramFiles)\SOLIDWORKS Corp\SOLIDWORKS\api\redist` o modifica la propiedad `SolidWorksApiDir` en el `.csproj`.
3. Compila en **x64** y registra el add-in (`regasm /codebase TinyMRP.SolidWorksAddin.dll`) si SolidWorks no lo registra automáticamente.

## Uso

1. Carga el add-in en SolidWorks y abre el task pane "TinyMRP".
2. Introduce tus credenciales de TinyMRP y pulsa **Login**.
3. Usa **Reservar PN** para obtener un PN/REV; el add-in renombra la configuración activa y actualiza propiedades personalizadas.
4. Selecciona tipos de archivo/procesos (cargados desde `/api/docpacks/options`) y activa las banderas deseadas (`Overwrite`, `Top level only`, Excel BOM, PDF binder, etc.).
5. Pulsa **BOM** para invocar `/api/docpacks/build`; el archivo se guarda en `FILES_LOCAL_ROOT\docpacks` y el panel muestra el enlace HTTP usando `FILES_URL_PREFIX`.
6. Usa **Freeze/Unfreeze** para alternar el estado de solo lectura del documento activo.

## Notas

- El token de autenticación y las rutas se guardan en `%AppData%/TinyMRP/addin_state.json` para reutilizar la sesión.
- Las llamadas POST incluyen cabeceras CSRF (`X-CSRFToken`) usando el token de la página de login.
- El endpoint de reserva de PN es configurable mediante `ReservePnEndpoint` en `App.config`.

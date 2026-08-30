#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy-SocialLens.ps1 - Script de despliegue automatico de SocialLens

.DESCRIPTION
    Descarga la maquina virtual de SocialLens desde Google Drive, verifica
    su integridad, la descomprime (con Expand-Archive, nativo de
    PowerShell) y la importa en VMware Workstation (usando ovftool si
    esta disponible, o abriendo VMware para importacion manual si no).

.NOTES
    Autor: Anderson Steven - TFM SocialLens
    Requiere: VMware Workstation (no requiere instalar 7-Zip)
#>

# --------------------------------------------------------------------
# CONFIGURACION
# --------------------------------------------------------------------
$GoogleDriveFileId = "1JdBNU0cNlBpFBHKk3k1MjVZkGOA614ut"
$ArchiveFileName    = "SocialLensOva1.0.zip"
$VmName             = "SocialLens"
$DestDir            = Join-Path $env:USERPROFILE "Downloads\SocialLens-VM"
$ExpectedSha256     = "767DF439690B3623AD883130AEC5A05421C4FBF3CB3DBB61BD277F5FD7131D2E"

$OvfFileName = "Social-Lens.ovf"

# --------------------------------------------------------------------
# FUNCIONES AUXILIARES
# --------------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Find-OvfTool {
    $candidates = @(
        "C:\Program Files\VMware\VMware OVF Tool\ovftool.exe",
        "C:\Program Files (x86)\VMware\VMware OVF Tool\ovftool.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    $cmd = Get-Command ovftool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Find-VMwareExe {
    $candidates = @(
        "C:\Program Files (x86)\VMware\VMware Workstation\vmware.exe",
        "C:\Program Files\VMware\VMware Workstation\vmware.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Find-VmrunExe {
    <#
    vmrun es la herramienta de linea de comandos que viene incluida de
    serie con VMware Workstation (a diferencia de ovftool, que es una
    descarga aparte). Permite encender una VM directamente sin abrir
    la interfaz grafica manualmente primero.
    #>
    $candidates = @(
        "C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
        "C:\Program Files\VMware\VMware Workstation\vmrun.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    $cmd = Get-Command vmrun.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Invoke-DownloadWithProgress {
    <#
    Descarga un archivo mostrando progreso real: porcentaje, velocidad y
    tiempo estimado restante, usando la barra de progreso nativa de
    PowerShell (Write-Progress). Invoke-WebRequest por si solo no ofrece
    esta informacion en descargas grandes.
    #>
    param(
        [string]$Uri,
        [string]$OutFile,
        $WebSession
    )

    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.CookieContainer = $WebSession.Cookies
    $request.Method = "GET"
    $request.Timeout = 60000

    $response = $request.GetResponse()
    $totalBytes = $response.ContentLength
    $responseStream = $response.GetResponseStream()
    $fileStream = [System.IO.File]::Create($OutFile)

    $buffer = New-Object byte[] 1MB
    $totalRead = 0L
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $lastUpdate = [System.Diagnostics.Stopwatch]::StartNew()

    try {
        while (($read = $responseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $fileStream.Write($buffer, 0, $read)
            $totalRead += $read

            # Actualizar la barra como mucho 5 veces por segundo (evita parpadeos)
            if ($lastUpdate.ElapsedMilliseconds -gt 200) {
                $elapsedSec  = [math]::Max($stopwatch.Elapsed.TotalSeconds, 0.1)
                $speedMBps   = [math]::Round(($totalRead / 1MB) / $elapsedSec, 2)
                $readMB      = [math]::Round($totalRead / 1MB, 1)

                if ($totalBytes -gt 0) {
                    $totalMB     = [math]::Round($totalBytes / 1MB, 1)
                    $percent     = [math]::Min(100, [math]::Round(($totalRead / $totalBytes) * 100, 1))
                    $remainingMB = [math]::Max(0, $totalMB - $readMB)
                    $etaSec      = if ($speedMBps -gt 0) { [math]::Round($remainingMB / $speedMBps) } else { -1 }
                    $etaText     = if ($etaSec -ge 0) { "{0:mm}m {0:ss}s restantes" -f ([timespan]::FromSeconds($etaSec)) } else { "calculando..." }

                    Write-Progress -Activity "Descargando SocialLens (Google Drive)" `
                        -Status "$readMB MB / $totalMB MB  -  $speedMBps MB/s  -  $etaText" `
                        -PercentComplete $percent
                } else {
                    Write-Progress -Activity "Descargando SocialLens (Google Drive)" `
                        -Status "$readMB MB descargados  -  $speedMBps MB/s"
                }
                $lastUpdate.Restart()
            }
        }
    } finally {
        Write-Progress -Activity "Descargando SocialLens (Google Drive)" -Completed
        $fileStream.Close()
        $responseStream.Close()
        $response.Close()
    }
}

function Get-GoogleDriveFile {
    <#
    Descarga un archivo publico de Google Drive por su ID, sorteando la
    pantalla de advertencia para archivos grandes ("Google Drive can't
    scan this file for viruses"). Esa advertencia es una pagina HTML con
    un formulario que apunta a drive.usercontent.google.com e incluye un
    "uuid" de un solo uso que hay que extraer y reenviar en la URL real.
    #>
    param(
        [string]$FileId,
        [string]$OutFile
    )

    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $baseUri = "https://drive.google.com/uc?export=download&id=$FileId"

    $response = Invoke-WebRequest -Uri $baseUri -WebSession $session -UseBasicParsing

    if ($response.Content -match 'name="uuid"\s+value="([^"]+)"') {
        $uuid = $matches[1]
        $downloadUri = "https://drive.usercontent.google.com/download?id=$FileId&export=download&confirm=t&uuid=$uuid"
        Invoke-DownloadWithProgress -Uri $downloadUri -OutFile $OutFile -WebSession $session
    } else {
        # Archivo pequeno: la primera peticion ya devolvio el contenido real.
        Invoke-WebRequest -Uri $baseUri -WebSession $session -OutFile $OutFile -UseBasicParsing
    }
}

# --------------------------------------------------------------------
# 1. PREPARAR DIRECTORIO DE DESTINO
# --------------------------------------------------------------------
Write-Step "Preparando directorio de destino: $DestDir"
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
Set-Location $DestDir

# --------------------------------------------------------------------
# 2. DESCARGAR EL ARCHIVO DESDE GOOGLE DRIVE
# --------------------------------------------------------------------
Write-Step "Descargando SocialLens desde Google Drive..."
$archivePath = Join-Path $DestDir $ArchiveFileName

if (Test-Path $archivePath) {
    Write-Host "  El archivo ya existe, se omite la descarga: $ArchiveFileName" -ForegroundColor DarkGray
} else {
    try {
        Get-GoogleDriveFile -FileId $GoogleDriveFileId -OutFile $archivePath
    } catch {
        Write-Error "No se pudo descargar el archivo desde Google Drive. Comprueba tu conexion."
        exit 1
    }
}
Write-Host "Descarga completada." -ForegroundColor Green

# --------------------------------------------------------------------
# 3. VERIFICAR INTEGRIDAD DEL ARCHIVO DESCARGADO
# --------------------------------------------------------------------
Write-Step "Verificando integridad..."
if ($ExpectedSha256 -ne "PON_AQUI_EL_HASH_SHA256_REAL") {
    $actualSha256 = (Get-FileHash $archivePath -Algorithm SHA256).Hash
    if ($actualSha256 -ne $ExpectedSha256) {
        Write-Error "El checksum no coincide. La descarga puede estar corrupta o incompleta."
        Write-Host "Esperado: $ExpectedSha256"
        Write-Host "Obtenido: $actualSha256"
        exit 1
    }
    Write-Host "Checksum verificado correctamente." -ForegroundColor Green
} else {
    Write-Warning "Verificacion de checksum omitida (no configurada)."
}

# --------------------------------------------------------------------
# 4. DESCOMPRIMIR (con Expand-Archive, nativo de PowerShell)
# --------------------------------------------------------------------
Write-Step "Extrayendo archivos (esto puede tardar varios minutos)..."
try {
    Expand-Archive -Path $archivePath -DestinationPath $DestDir -Force
} catch {
    Write-Error "Fallo al extraer los archivos. Comprueba que la descarga no este corrupta."
    Write-Host $_.Exception.Message
    exit 1
}
Write-Host "Extraccion completada." -ForegroundColor Green

# --------------------------------------------------------------------
# 5. IMPORTAR LA VM
# --------------------------------------------------------------------
Write-Step "Importando la maquina virtual..."

# El archivo comprimido puede extraerse directamente en $DestDir o dentro
# de una subcarpeta (segun como se generase el .zip), asi que se busca
# el .ovf recursivamente en vez de asumir una ruta fija.
$ovfFile = Get-ChildItem -Path $DestDir -Filter $OvfFileName -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$ovfTool = Find-OvfTool

if (-not $ovfFile) {
    Write-Error "No se encontro el fichero $OvfFileName tras la extraccion. Revisa el contenido de $DestDir."
    exit 1
}
$ovfPath = $ovfFile.FullName
Write-Host "  Fichero .ovf encontrado en: $ovfPath" -ForegroundColor Green

if ($ovfTool) {
    Write-Host "  ovftool encontrado, importando automaticamente..." -ForegroundColor Green
    $vmxOutput = Join-Path $DestDir "$VmName.vmx"
    & $ovfTool $ovfPath $vmxOutput

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "VM importada correctamente en: $vmxOutput" -ForegroundColor Green

        # ----------------------------------------------------------------
        # Abrir VMware con la VM y encenderla automaticamente
        # ----------------------------------------------------------------
        Write-Step "Abriendo y encendiendo la maquina virtual..."
        $vmwareExe = Find-VMwareExe
        $vmrunExe  = Find-VmrunExe

        if ($vmrunExe -and (Test-Path $vmxOutput)) {
            # vmrun start abre VMware (si no esta abierto) y enciende la VM directamente.
            & $vmrunExe -T ws start "$vmxOutput" gui
            if ($LASTEXITCODE -eq 0) {
                Write-Host "SocialLens se ha encendido correctamente." -ForegroundColor Green
            } else {
                Write-Warning "No se pudo encender la VM automaticamente con vmrun."
                if ($vmwareExe) {
                    Write-Host "Abriendo VMware Workstation con la VM cargada..."
                    Start-Process $vmwareExe -ArgumentList "`"$vmxOutput`""
                }
            }
        } elseif ($vmwareExe) {
            Write-Host "No se encontro 'vmrun'. Se abrira VMware con la VM cargada; enciendela manualmente con el boton Play."
            Start-Process $vmwareExe -ArgumentList "`"$vmxOutput`""
        } else {
            Write-Warning "No se encontro VMware Workstation instalado."
            Write-Host "Abre manualmente el fichero: $vmxOutput"
        }
    } else {
        Write-Warning "ovftool encontro un problema durante la importacion. Revisa el mensaje anterior."
    }
} else {
    Write-Warning "No se encontro 'ovftool' instalado."
    Write-Host "Puedes descargarlo (requiere cuenta gratuita de Broadcom) desde:"
    Write-Host "  https://developer.broadcom.com/tools/open-virtualization-format-ovf-tool/latest"
    Write-Host ""
    Write-Host "Mientras tanto, se abrira VMware Workstation para que importes la VM manualmente (2-3 clics)."

    $vmwareExe = Find-VMwareExe
    if ($vmwareExe) {
        Start-Process $vmwareExe -ArgumentList "`"$ovfPath`""
    } else {
        Write-Warning "Tampoco se encontro VMware Workstation instalado. Instalalo desde https://www.vmware.com/products/workstation-pro.html"
        Write-Host "Despues, abre manualmente el fichero: $ovfPath"
    }
}

Write-Host ""
Write-Host "=== Proceso finalizado ===" -ForegroundColor Cyan

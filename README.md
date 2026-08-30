# SocialLens

**Distribución Linux OSINT orientada a la investigación de redes sociales**

Trabajo de Fin de Máster — Anderson Steven

<img width="1376" height="768" alt="wallpaperSocialLens" src="https://github.com/user-attachments/assets/129365df-1699-445d-ac44-eedd49309932" />

---

## Qué es SocialLens

SocialLens es una distribución Linux basada en Ubuntu 22.04 LTS, remasterizada con [Cubic](https://github.com/PJ-Singh-001/Cubic), que integra un conjunto curado de herramientas OSINT (*Open Source Intelligence*) especializadas en la investigación de identidades y actividad en redes sociales.

El proyecto no se limita a empaquetar herramientas de terceros: incluye un **desarrollo propio**, el *SocialLens Correlator*, que orquesta varias herramientas de reconocimiento de identidad, fusiona sus resultados y calcula una puntuación de confianza sobre si distintos perfiles pertenecen a la misma persona.

## Despliegue rápido (Windows + VMware)

La forma más rápida de tener SocialLens funcionando es mediante el script de despliegue automático, que descarga la máquina virtual ya instalada, verifica su integridad y la importa en VMware Workstation.

### Requisitos previos
- Windows 10/11
- [VMware Workstation Pro](https://www.vmware.com/products/workstation-pro.html) instalado
- PowerShell 5.1 o superior (viene de serie en Windows)

### Pasos

1. Descarga [`scripts/Deploy-SocialLens.ps1`](scripts/Deploy-SocialLens.ps1) de este repositorio
2. Abre PowerShell y permite la ejecución del script para esta sesión:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
3. Ejecuta el script:
   ```powershell
   .\Deploy-SocialLens.ps1
   ```
4. El script descargará la VM (~5.8 GB) desde Google Drive, verificará su checksum SHA256, la descomprimirá y abrirá VMware Workstation con la máquina lista para importar.
   - Si tienes `ovftool` instalado, la importación (y el arranque) se completa automáticamente.
   - Si no lo tienes, VMware se abrirá con el asistente de importación — solo hay que confirmar 2-3 pasos.

### Descarga manual (alternativa)

Si prefieres no usar el script, puedes descargar los archivos directamente:

- **Máquina virtual (OVA/OVF, ~5.8 GB)**: [Google Drive](https://drive.google.com/file/d/1JdBNU0cNlBpFBHKk3k1MjVZkGOA614ut/view?usp=sharing)
- **ISO de instalación (~4.4 GB)**: [Google Drive](https://drive.google.com/file/d/1RXu8TlnyOmJNM8i5VcS0JmhaxtYf9DO0/view?usp=sharing)

La ISO es útil si prefieres instalar SocialLens desde cero en vez de importar la VM ya configurada (por ejemplo, en un USB físico o con hardware de VM distinto).

### Credenciales de acceso por defecto

La máquina virtual distribuida (OVA) incluye un usuario ya creado:

| Usuario | Contraseña |
|---|---|
| `socialuser` | `sociallens` |

Se recomienda cambiar la contraseña tras el primer inicio de sesión si vas a usar la distribución más allá de una prueba puntual.

## Contenido de este repositorio

```
Social-Lens/
├── src/correlator/       # Desarrollo propio: el correlacionador de identidades
│   ├── correlator.py     # Punto de entrada (CLI)
│   ├── runners.py        # Orquesta Sherlock, Maigret, Holehe e Ignorant
│   └── scoring.py        # Deduplicación, comparación visual y puntuación
├── scripts/
│   ├── slmenu             # Menú lanzador de las herramientas OSINT preinstaladas
│   └── Deploy-SocialLens.ps1  # Script de despliegue automático (Windows)
├── config/
│   └── policies.json     # Configuración de Firefox (marcadores, extensiones, tema)
└── docs/                 # Documentación y capturas adicionales
```

## Herramientas OSINT incluidas en la distro

| Categoría | Herramientas |
|---|---|
| Búsqueda de usernames | Sherlock, Maigret, Social-Analyzer |
| Email y teléfono | Holehe, Ignorant |
| Instagram | Instaloader, Toutatis, Osintgram |
| Organizaciones / dominios | theHarvester, CrossLinked, git-hound |
| Reddit / TikTok / Snapchat | URS, tiktok-hashtag-analysis, snapchat-map-scraper |
| Metadatos | ExifTool, socid_extractor |

Además, Firefox viene preconfigurado con más de 50 marcadores organizados por categoría (búsqueda de imágenes, motores OSINT, redes sociales, comunidades) y 5 extensiones orientadas a investigación, junto con tema oscuro activado por defecto.

## SocialLens Correlator

El desarrollo central del proyecto. Acepta como entrada un username, un email y/o un teléfono, dispara las herramientas correspondientes, fusiona los resultados eliminando duplicados y calcula una puntuación de confianza (0-100).

```bash
python3 correlator.py --username johndoe92
python3 correlator.py --username johndoe92 --email john.doe@example.com
```

## slmenu

Menú interactivo en terminal que permite lanzar cualquiera de las herramientas OSINT preinstaladas sin necesidad de recordar su sintaxis exacta ni las rutas de sus entornos virtuales.

```bash
slmenu
```
<img width="2256" height="1242" alt="image" src="https://github.com/user-attachments/assets/12fa6f59-2f58-4be2-8ebc-680dcbeb284b" />

## Licencia

Este proyecto se distribuye bajo licencia MIT. Ver [LICENSE](LICENSE).

## Marco ético y legal

Todas las herramientas y recursos incluidos en SocialLens operan exclusivamente sobre información de acceso público. El diseño del proyecto excluyó explícitamente herramientas orientadas a la vulneración de privacidad, la vigilancia encubierta o el acceso no autorizado a contenido privado. El uso de esta distribución debe ajustarse en todo momento a la normativa de protección de datos aplicable (RGPD) y a los términos de servicio de las plataformas consultadas.

"""
runners.py — SocialLens Correlator
Módulo responsable de ejecutar las herramientas OSINT externas
(Sherlock, Maigret, Holehe, Ignorant) y normalizar su salida
a un formato común que el resto del programa pueda consumir.

Cada función devuelve una lista de diccionarios con esta forma:
{
    "platform": str,     # nombre de la plataforma/sitio
    "url": str | None,   # URL del perfil, si la herramienta la da
    "source": str,        # qué herramienta lo encontró
    "vector": str         # "username" | "email" | "phone"
}
"""

import subprocess
import re
import json
import os
import tempfile
import requests


# -----------------------------
# SHERLOCK (vector: username)
# -----------------------------
def run_sherlock(username: str, timeout: int = 90) -> list[dict]:
    """
    Ejecuta sherlock-project sobre un username y parsea la salida estándar.
    Sherlock imprime líneas del tipo: [+] SiteName: https://site.com/user

    Se usa --folderoutput apuntando a un directorio temporal para que el
    archivo <username>.txt que Sherlock genera por defecto no ensucie el
    directorio de trabajo del correlacionador; se descarta al terminar,
    ya que el resultado real se obtiene parseando stdout.
    """
    results = []
    workdir = tempfile.mkdtemp(prefix="sherlock_")
    try:
        proc = subprocess.run(
            ["sherlock", username, "--print-found", "--no-color", "--timeout", "30",
             "--folderoutput", workdir],
            capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        print("[!] sherlock no está instalado o no está en el PATH.")
        return results
    except subprocess.TimeoutExpired:
        print("[!] sherlock ha superado el tiempo límite, se usan los resultados parciales.")
        output = ""

    pattern = re.compile(r"\[\+\]\s*(.+?):\s*(https?://\S+)")
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            platform, url = match.group(1).strip(), match.group(2).strip()
            results.append({
                "platform": platform,
                "url": url,
                "source": "sherlock",
                "vector": "username"
            })
    return results


# -----------------------------
# MAIGRET (vector: username)
# -----------------------------
def run_maigret(username: str, timeout: int = 180) -> list[dict]:
    """
    Ejecuta maigret y parsea directamente su salida de texto estándar,
    igual que hacemos con Sherlock. Se abandona el enfoque de leer el
    reporte --json simple porque el nombre exacto del fichero de reporte
    varía entre versiones de Maigret, lo que hacía que el parser no
    encontrara resultados aunque la herramienta sí los hubiera hallado.

    Maigret imprime líneas del tipo:
      [+] SiteName: https://site.com/user
    seguidas opcionalmente de líneas de metadatos con prefijo " ├─"/" └─"
    que aquí se ignoran (no son una plataforma nueva).
    """
    results = []
    try:
        proc = subprocess.run(
            ["maigret", username, "--timeout", "15", "--no-color", "--no-progressbar"],
            capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        print("[!] maigret no está instalado o no está en el PATH.")
        return results
    except subprocess.TimeoutExpired:
        print("[!] maigret ha superado el tiempo límite, se usan los resultados parciales.")
        output = ""

    pattern = re.compile(r"^\[\+\]\s*(.+?):\s*(https?://\S+)")
    for line in output.splitlines():
        match = pattern.search(line.strip())
        if match:
            platform, url = match.group(1).strip(), match.group(2).strip()
            results.append({
                "platform": platform,
                "url": url,
                "source": "maigret",
                "vector": "username"
            })
    return results


# -----------------------------
# HOLEHE (vector: email)
# -----------------------------
def run_holehe(email: str, timeout: int = 90) -> list[dict]:
    """
    Ejecuta holehe sobre un email. Parsea líneas "[+] Plataforma"
    que indican que el email está registrado en esa plataforma.
    Se descartan líneas de cabecera/resumen genéricas (p. ej. "Email",
    "Twitter is trying...") que no representan una plataforma real.
    """
    results = []
    try:
        proc = subprocess.run(
            ["holehe", email, "--only-used", "--no-color"],
            capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        print("[!] holehe no está instalado o no está en el PATH.")
        return results
    except subprocess.TimeoutExpired:
        print("[!] holehe ha superado el tiempo límite, se usan los resultados parciales.")
        output = ""

    # Palabras de cabecera/resumen que holehe puede imprimir con el mismo
    # prefijo "[+]" pero que no son nombres de plataforma reales.
    ignore_words = {"email", "phone", "websites", "twitter", "results", "found"}

    pattern = re.compile(r"\[\+\]\s*([A-Za-z0-9_.\-]+)")
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            platform = match.group(1).strip()
            if platform.lower() in ignore_words:
                continue
            results.append({
                "platform": platform,
                "url": None,
                "source": "holehe",
                "vector": "email"
            })
    return results


# -----------------------------
# IGNORANT (vector: phone)
# -----------------------------
def run_ignorant(country_code: str, phone: str, timeout: int = 60) -> list[dict]:
    """
    Ejecuta ignorant sobre un número de teléfono (código de país sin '+').
    Parsea líneas "[+] Plataforma" que indican que el número está registrado.
    """
    results = []
    try:
        proc = subprocess.run(
            ["ignorant", country_code, phone, "--only-used", "--no-color", "--no-clear"],
            capture_output=True, text=True, timeout=timeout
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        print("[!] ignorant no está instalado o no está en el PATH.")
        return results
    except subprocess.TimeoutExpired:
        print("[!] ignorant ha superado el tiempo límite, se usan los resultados parciales.")
        output = ""

    # Palabras de cabecera/resumen que ignorant puede imprimir con el mismo
    # prefijo "[+]" pero que no son nombres de plataforma reales.
    ignore_words = {"phone", "email", "results", "found"}

    pattern = re.compile(r"\[\+\]\s*([A-Za-z0-9_.\-]+)")
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            platform = match.group(1).strip()
            if platform.lower() in ignore_words:
                continue
            results.append({
                "platform": platform,
                "url": None,
                "source": "ignorant",
                "vector": "phone"
            })
    return results


# -----------------------------
# Utilidad: descarga de imágenes (para comparación visual opcional)
# -----------------------------
def download_image(url: str, dest_path: str, timeout: int = 15) -> bool:
    """Descarga una imagen desde una URL a dest_path. Devuelve True si tuvo éxito."""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                f.write(resp.content)
            return True
    except requests.RequestException as e:
        print(f"[!] No se pudo descargar la imagen {url}: {e}")
    return False

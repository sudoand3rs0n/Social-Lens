"""
scoring.py — SocialLens Correlator
Módulo responsable de:
  1. Fusionar y deduplicar resultados provenientes de varias herramientas.
  2. Comparar imágenes de perfil mediante hash perceptual (opcional).
  3. Calcular una puntuación de confianza (0-100) sobre si los perfiles
     encontrados pertenecen a la misma identidad.
"""

from PIL import Image
import imagehash


# -----------------------------
# Fusión y deduplicación
# -----------------------------
def merge_results(*result_lists: list[dict]) -> list[dict]:
    """
    Une varias listas de resultados (de distintas herramientas/vectores)
    en una sola, fusionando entradas que correspondan a la misma
    plataforma (mismo nombre, normalizado a minúsculas) y acumulando
    las fuentes que la detectaron.
    """
    merged: dict[str, dict] = {}

    for result_list in result_lists:
        for entry in result_list:
            key = entry["platform"].strip().lower()
            if key not in merged:
                merged[key] = {
                    "platform": entry["platform"],
                    "url": entry.get("url"),
                    "sources": {entry["source"]},
                    "vectors": {entry["vector"]},
                }
            else:
                merged[key]["sources"].add(entry["source"])
                merged[key]["vectors"].add(entry["vector"])
                # si una fuente nueva sí trae URL y la que teníamos no, la completamos
                if not merged[key]["url"] and entry.get("url"):
                    merged[key]["url"] = entry["url"]

    # convertir sets a listas para que sea serializable a JSON
    final = []
    for item in merged.values():
        item["sources"] = sorted(item["sources"])
        item["vectors"] = sorted(item["vectors"])
        final.append(item)

    return final


# -----------------------------
# Comparación visual de imágenes (hash perceptual)
# -----------------------------
def compare_images(image_paths: list[str], max_distance: int = 8) -> list[dict]:
    """
    Calcula el hash perceptual (phash) de cada imagen en image_paths
    y compara todas contra todas. Devuelve las parejas cuya distancia
    de Hamming sea <= max_distance (es decir, visualmente similares).

    max_distance=8 es un umbral habitual para phash de 64 bits: valores
    bajos (0-5) indican casi idénticas, hasta ~10 puede indicar la misma
    imagen recomprimida o levemente recortada.
    """
    hashes = {}
    for path in image_paths:
        try:
            hashes[path] = imagehash.phash(Image.open(path))
        except (FileNotFoundError, OSError) as e:
            print(f"[!] No se pudo procesar la imagen {path}: {e}")

    matches = []
    paths = list(hashes.keys())
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            distance = hashes[paths[i]] - hashes[paths[j]]
            if distance <= max_distance:
                matches.append({
                    "image_a": paths[i],
                    "image_b": paths[j],
                    "hamming_distance": int(distance)
                })
    return matches


# -----------------------------
# Motor de puntuación de confianza
# -----------------------------
def calculate_confidence(merged_profiles: list[dict], image_matches: list[dict] | None = None) -> dict:
    """
    Calcula una puntuación de confianza (0-100) de que los perfiles
    encontrados pertenezcan a la misma identidad, en base a:

      - Número total de plataformas encontradas (más = más señal)
      - Diversidad de vectores usados (username + email + phone
        apuntando a resultados coincidentes es una señal fuerte)
      - Coincidencias visuales de imagen de perfil (si se proporcionan)

    Esto es una heurística orientativa, no una prueba definitiva:
    se documenta así en la memoria del TFM.
    """
    if not merged_profiles:
        return {"score": 0, "explanation": "No se encontraron perfiles."}

    n_platforms = len(merged_profiles)
    all_vectors = set()
    for p in merged_profiles:
        all_vectors.update(p["vectors"])

    # Puntos base por cantidad de plataformas (tope en 50 puntos)
    platform_score = min(n_platforms * 4, 50)

    # Puntos por diversidad de vectores (username/email/phone): hasta 30 puntos
    vector_score = min(len(all_vectors) * 10, 30)

    # Puntos por coincidencias visuales: hasta 20 puntos
    image_score = 0
    if image_matches:
        image_score = min(len(image_matches) * 10, 20)

    total = platform_score + vector_score + image_score
    total = min(total, 100)

    explanation = (
        f"{n_platforms} plataformas encontradas, "
        f"{len(all_vectors)} vector(es) de entrada distintos usados "
        f"({', '.join(sorted(all_vectors))})"
    )
    if image_matches:
        explanation += f", {len(image_matches)} coincidencia(s) visual(es) de imagen"

    return {
        "score": total,
        "platform_score": platform_score,
        "vector_score": vector_score,
        "image_score": image_score,
        "explanation": explanation
    }

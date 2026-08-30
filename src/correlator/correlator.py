#!/usr/bin/env python3
"""
correlator.py — SocialLens Correlator
Punto de entrada del correlacionador de identidades de SocialLens.

Acepta como entrada un username, un email y/o un teléfono (cualquier
combinación), dispara las herramientas OSINT correspondientes, fusiona
los resultados, calcula una puntuación de confianza y guarda un
informe en JSON.

Ejemplos de uso:
  python3 correlator.py --username johndoe92
  python3 correlator.py --username johndoe92 --email john.doe@gmail.com
  python3 correlator.py --username johndoe92 --email john.doe@gmail.com \
                   --phone 612345678 --country-code 34
  python3 correlator.py --username johndoe92 --images foto1.jpg foto2.jpg
"""

import argparse
import json
import sys
from datetime import datetime, timezone

from runners import run_sherlock, run_maigret, run_holehe, run_ignorant
from scoring import merge_results, calculate_confidence, compare_images

try:
    import pyfiglet
    _HAS_PYFIGLET = True
except ImportError:
    _HAS_PYFIGLET = False


def print_banner():
    """Imprime el banner ASCII de bienvenida de SocialLens Correlator."""
    if _HAS_PYFIGLET:
        print(pyfiglet.figlet_format("SocialLens", font="small"))
        print(pyfiglet.figlet_format("CORRELATOR", font="slant"))
    else:
        # Fallback si pyfiglet no está instalado: banner simple sin dependencias.
        print("=" * 60)
        print("  SocialLens — CORRELATOR")
        print("  Correlacionador de identidades OSINT")
        print("=" * 60)
    print("  Correlacionador de identidades — TFM SocialLens")
    print("  Desarrollado por Anderson Steven\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SocialLens Correlator — orquesta herramientas OSINT y "
                    "correlaciona identidades a partir de username, email y/o teléfono."
    )
    parser.add_argument("--username", help="Username a investigar (dispara Sherlock y Maigret).")
    parser.add_argument("--email", help="Email a investigar (dispara Holehe).")
    parser.add_argument("--phone", help="Número de teléfono, sin prefijo (dispara Ignorant).")
    parser.add_argument("--country-code", default="34",
                        help="Código de país para el teléfono, sin '+'. Por defecto 34 (España).")
    parser.add_argument("--images", nargs="+", default=[],
                        help="Rutas locales a imágenes de perfil para comparación visual (opcional).")
    parser.add_argument("--output", default=None,
                        help="Ruta del fichero JSON de salida. Por defecto se genera "
                            "automáticamente a partir de la entrada principal.")
    return parser


def main():
    print_banner()
    args = build_parser().parse_args()

    if not any([args.username, args.email, args.phone]):
        print("[!] Debes proporcionar al menos --username, --email o --phone.")
        sys.exit(1)

    sherlock_results, maigret_results = [], []
    holehe_results, ignorant_results = [], []

    if args.username:
        print(f"[*] Buscando username '{args.username}' con Sherlock...")
        sherlock_results = run_sherlock(args.username)
        print(f"    → {len(sherlock_results)} plataformas encontradas.")

        print(f"[*] Buscando username '{args.username}' con Maigret...")
        maigret_results = run_maigret(args.username)
        print(f"    → {len(maigret_results)} plataformas encontradas.")

    if args.email:
        print(f"[*] Comprobando email '{args.email}' con Holehe...")
        holehe_results = run_holehe(args.email)
        print(f"    → {len(holehe_results)} servicios donde el email está registrado.")

    if args.phone:
        print(f"[*] Comprobando teléfono '{args.phone}' con Ignorant...")
        ignorant_results = run_ignorant(args.country_code, args.phone)
        print(f"    → {len(ignorant_results)} servicios donde el teléfono está registrado.")

    print("[*] Fusionando y deduplicando resultados...")
    merged = merge_results(sherlock_results, maigret_results, holehe_results, ignorant_results)

    image_matches = []
    if len(args.images) >= 2:
        print(f"[*] Comparando {len(args.images)} imágenes por hash perceptual...")
        image_matches = compare_images(args.images)
        print(f"    → {len(image_matches)} coincidencia(s) visual(es) encontrada(s).")

    print("[*] Calculando puntuación de confianza...")
    confidence = calculate_confidence(merged, image_matches)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "username": args.username,
            "email": args.email,
            "phone": args.phone,
            "images_provided": args.images,
        },
        "profiles_found": merged,
        "image_matches": image_matches,
        "confidence": confidence,
    }

    output_path = args.output or f"correlator_report_{args.username or args.email or args.phone}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # ---- Resumen en consola ----
    print("\n" + "=" * 60)
    print(f"  Plataformas encontradas: {len(merged)}")
    for p in merged:
        sources = "+".join(p["sources"])
        url_txt = f" — {p['url']}" if p["url"] else ""
        print(f"    [{sources}] {p['platform']}{url_txt}")
    if image_matches:
        print(f"\n  Coincidencias visuales: {len(image_matches)}")
    print(f"\n  Confidence Score: {confidence['score']}/100")
    print(f"  {confidence['explanation']}")
    print("=" * 60)
    print(f"\n[+] Informe guardado en: {output_path}\n")


if __name__ == "__main__":
    main()

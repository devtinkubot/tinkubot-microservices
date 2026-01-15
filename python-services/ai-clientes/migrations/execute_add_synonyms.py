"""
Script para agregar sinónimos TI/Web a Supabase.

Este script inserta los sinónimos directamente usando el cliente de Supabase,
lo cual es más seguro que ejecutar SQL raw y permite mejor control de errores.
"""

import asyncio
import os
import sys
from pathlib import Path

# Agregar el path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client


# Sinónimos para DESARROLLADOR
DEVELOPER_SYNONYMS = [
    # Ingeniería de software / TI
    'ingeniero en sistemas',
    'ingeniero de sistemas',
    'ingeniero de computación',
    'ingeniero en computación',
    'ingeniero informático',
    'ingeniero informatica',
    'systems engineer',
    'software engineer',
    'ingeniero de desarrollo',
    'ingeniero de software developer',

    # Desarrollo web específico
    'desarrollador web',
    'desarrollador de software',
    'programador web',
    'web developer',
    'web dev',
    'full stack developer',
    'fullstack',
    'full-stack',
    'backend developer',
    'frontend developer',
    'backend',
    'frontend',

    # Servicios web (páginas, sitios, etc)
    'pagina web',
    'paginas web',
    'página web',
    'páginas web',
    'sitio web',
    'sitios web',
    'sitios',
    'web',
    'desarrollo de sitios web',
    'desarrollo de paginas web',
    'desarrollo de páginas web',
    'creacion de paginas web',
    'creación de páginas web',
    'crear pagina web',
    'crear página web',
    'construir pagina web',
    'construir página web',
    'montar pagina web',
    'montar página web',

    # E-commerce y aplicaciones
    'aplicación web',
    'aplicacion web',
    'aplicaciones web',
    'app web',
    'apps web',
    'ecommerce',
    'e-commerce',
    'tienda online',
    'tienda en linea',
    'tienda electrónica',
    'blog',
    'blogs',

    # Software general
    'software',
    'desarrollo de software',
    'programación',
    'programacion',
    'sistema',
    'sistemas',
    'aplicación',
    'aplicacion',
    'aplicaciones',
    'base de datos',
    'bases de datos',
    'api',
    'apis',
    'integración',
    'integracion',
    'integraciones',

    # Consultoría TI
    'consultoría informática',
    'consultoria informatica',
    'consultor de sistemas',
    'consultor ti',
    'consultor it'
]

# Sinónimos para DISEÑADOR WEB
WEB_DESIGNER_SYNONYMS = [
    'diseñador web',
    'disenador web',
    'diseño web',
    'diseño de paginas web',
    'diseño de páginas web',
    'diseño de sitios web',
    'web designer',
    'web design',
    'diseño ui',
    'diseño ux',
    'diseño ui/ux',
    'diseñador ui',
    'diseñador ux',
    'diseñador ui/ux',
    'diseñadora web',
    'diseñadora ui',
    'diseñadora ux',
    'maquetacion web',
    'maquetación web',
    'maquetador web',
    'diseño de interfaces',
    'diseño de experiencia de usuario',
    'diseño grafico web',
    'diseño gráfico web'
]


def main():
    """Función principal para insertar los sinónimos."""

    # Obtener credenciales de Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ Error: No se encontraron las variables SUPABASE_URL y SUPABASE_SERVICE_KEY")
        return 1

    print(f"📦 Conectando a Supabase: {supabase_url}")

    # Crear cliente de Supabase
    supabase = create_client(supabase_url, supabase_key)

    # Verificar estado actual de la tabla
    print("\n📊 Estado actual de service_synonyms:")

    try:
        # Contar sinónimos antes de la ejecución
        result = supabase.table("service_synonyms").select("canonical_profession", "synonym").execute()

        before_count = len(result.data)
        print(f"   Total sinónimos actuales: {before_count}")

        # Contar sinónimos de 'desarrollador' antes
        dev_before = supabase.table("service_synonyms").select("*").eq("canonical_profession", "desarrollador").execute()
        print(f"   Sinónimos de 'desarrollador': {len(dev_before.data)}")

        # Contar sinónimos de 'diseñador web' antes
        designer_before = supabase.table("service_synonyms").select("*").eq("canonical_profession", "diseñador web").execute()
        print(f"   Sinónimos de 'diseñador web': {len(designer_before.data)}")

        # Insertar sinónimos de DESARROLLADOR
        print(f"\n🚀 Insertando {len(DEVELOPER_SYNONYMS)} sinónimos para 'desarrollador'...")

        dev_inserted = 0
        dev_skipped = 0

        for synonym in DEVELOPER_SYNONYMS:
            try:
                # Verificar si ya existe
                existing = supabase.table("service_synonyms").select("*").eq("synonym", synonym).execute()

                if existing.data:
                    dev_skipped += 1
                    print(f"   ⊘ '{synonym}' - ya existe, omitiendo")
                else:
                    # Insertar nuevo sinónimo
                    supabase.table("service_synonyms").insert({
                        "canonical_profession": "desarrollador",
                        "synonym": synonym,
                        "active": True
                    }).execute()
                    dev_inserted += 1
                    print(f"   ✅ '{synonym}' - insertado")

            except Exception as e:
                print(f"   ❌ '{synonym}' - error: {e}")

        print(f"\n   Resumen 'desarrollador': {dev_inserted} insertados, {dev_skipped} omitidos")

        # Insertar sinónimos de DISEÑADOR WEB
        print(f"\n🚀 Insertando {len(WEB_DESIGNER_SYNONYMS)} sinónimos para 'diseñador web'...")

        designer_inserted = 0
        designer_skipped = 0

        for synonym in WEB_DESIGNER_SYNONYMS:
            try:
                # Verificar si ya existe
                existing = supabase.table("service_synonyms").select("*").eq("synonym", synonym).execute()

                if existing.data:
                    designer_skipped += 1
                    print(f"   ⊘ '{synonym}' - ya existe, omitiendo")
                else:
                    # Insertar nuevo sinónimo
                    supabase.table("service_synonyms").insert({
                        "canonical_profession": "diseñador web",
                        "synonym": synonym,
                        "active": True
                    }).execute()
                    designer_inserted += 1
                    print(f"   ✅ '{synonym}' - insertado")

            except Exception as e:
                print(f"   ❌ '{synonym}' - error: {e}")

        print(f"\n   Resumen 'diseñador web': {designer_inserted} insertados, {designer_skipped} omitidos")

        # Verificar resultados después de la ejecución
        print("\n📊 Estado después de la ejecución:")

        result_after = supabase.table("service_synonyms").select("canonical_profession", "synonym").execute()
        after_count = len(result_after.data)
        total_new = after_count - before_count
        print(f"   Total sinónimos: {after_count} (+{total_new} nuevos)")

        # Verificar sinónimos de 'desarrollador'
        dev_after = supabase.table("service_synonyms").select("*").eq("canonical_profession", "desarrollador").execute()
        dev_new = len(dev_after.data) - len(dev_before.data)
        print(f"   Sinónimos de 'desarrollador': {len(dev_after.data)} (+{dev_new} nuevos)")

        # Verificar sinónimos de 'diseñador web'
        designer_after = supabase.table("service_synonyms").select("*").eq("canonical_profession", "diseñador web").execute()
        designer_new = len(designer_after.data) - len(designer_before.data)
        print(f"   Sinónimos de 'diseñador web': {len(designer_after.data)} (+{designer_new} nuevos)")

        # Verificar sinónimos específicos
        print("\n🔍 Verificando sinónimos específicos:")

        test_synonyms = [
            'ingeniero en sistemas',
            'pagina web',
            'desarrollador web',
            'web developer'
        ]

        for synonym in test_synonyms:
            result = supabase.table("service_synonyms").select("*").eq("synonym", synonym).execute()
            if result.data:
                canonical = result.data[0]['canonical_profession']
                print(f"   ✅ '{synonym}' → '{canonical}'")
            else:
                print(f"   ⚠️  '{synonym}' → NO ENCONTRADO")

        print("\n✅ Proceso completado exitosamente")
        print(f"   Total sinónimos nuevos insertados: {dev_inserted + designer_inserted}")
        print(f"   Total sinónimos omitidos (ya existían): {dev_skipped + designer_skipped}")

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

"""
Descarga datos de Inside Airbnb para ciudades españolas
y genera prices.json con medianas de precio por zona,
tipo de propiedad y número de habitaciones.
"""

import requests
import pandas as pd
import json
import io
import gzip
from datetime import datetime

CIUDADES = {
    "Barcelona": "https://data.insideairbnb.com/spain/catalonia/barcelona/",
    "Madrid": "https://data.insideairbnb.com/spain/comunidad-de-madrid/madrid/",
    "Mallorca": "https://data.insideairbnb.com/spain/islas-baleares/mallorca/",
    "Menorca": "https://data.insideairbnb.com/spain/islas-baleares/menorca/",
    "Ibiza": "https://data.insideairbnb.com/spain/islas-baleares/ibiza/",
    "Sevilla": "https://data.insideairbnb.com/spain/andaluc%C3%ADa/sevilla/",
    "Valencia": "https://data.insideairbnb.com/spain/comunitat-valenciana/valencia/",
    "Euskadi": "https://data.insideairbnb.com/spain/euskadi/euskadi/",
    "Girona": "https://data.insideairbnb.com/spain/catalonia/girona/",
    "Malaga": "https://data.insideairbnb.com/spain/andaluc%C3%ADa/malaga/",
}

ROOM_TYPE_MAP = {
    "Entire home/apt": "apartamento",
    "Private room": "habitacion",
    "Hotel room": "habitacion",
    "Shared room": "habitacion",
}

def get_latest_listings_url(city_base_url):
    try:
        import re
        page = requests.get("https://insideairbnb.com/get-the-data/", timeout=15)
        pattern = city_base_url.replace("https://data.insideairbnb.com", "")
        pattern = re.escape(pattern)
        urls = re.findall(
            r'https://data\.insideairbnb\.com' + pattern + r'\d{4}-\d{2}-\d{2}/data/listings\.csv\.gz',
            page.text
        )
        if urls:
            return sorted(urls)[-1]
        return None
    except Exception as e:
        print(f"  Error buscando URL: {e}")
        return None

def limpiar_precio(precio_str):
    if pd.isna(precio_str):
        return None
    precio_str = str(precio_str).replace('$', '').replace(',', '').strip()
    try:
        valor = float(precio_str)
        return valor if 0 < valor < 10000 else None
    except:
        return None

def inferir_tipo(row):
    room = row.get('room_type', '')
    beds = row.get('bedrooms', 1)
    tipo_airbnb = row.get('property_type', '')
    base = ROOM_TYPE_MAP.get(room, 'apartamento')
    if base == 'apartamento':
        tipo_lower = str(tipo_airbnb).lower()
        if any(w in tipo_lower for w in ['villa', 'chalet', 'house', 'casa', 'cottage', 'bungalow']):
            if pd.notna(beds) and beds >= 3:
                return 'villa'
            return 'casa'
        return 'apartamento'
    return base

def procesar_ciudad(ciudad_nombre, csv_url):
    print(f"  Descargando {ciudad_nombre}...")
    try:
        resp = requests.get(csv_url, timeout=60)
        resp.raise_for_status()
        with gzip.open(io.BytesIO(resp.content)) as f:
            df = pd.read_csv(f, low_memory=False)
        print(f"  {len(df)} alojamientos encontrados")
        df['precio_limpio'] = df['price'].apply(limpiar_precio)
        df = df.dropna(subset=['precio_limpio'])
        df['tipo'] = df.apply(inferir_tipo, axis=1)
        df['beds_norm'] = pd.to_numeric(df.get('bedrooms', 1), errors='coerce').fillna(1).clip(1, 4).astype(int)
        resultado = {}
        for tipo in ['apartamento', 'casa', 'habitacion', 'villa']:
            resultado[tipo] = {}
            for beds in [1, 2, 3, 4]:
                subset = df[(df['tipo'] == tipo) & (df['beds_norm'] == beds)]['precio_limpio']
                if len(subset) >= 5:
                    resultado[tipo][str(beds)] = round(float(subset.median()), 0)
                else:
                    fallback = df[df['tipo'] == tipo]['precio_limpio']
                    if len(fallback) >= 3:
                        base = float(fallback.median())
                        mults = {1: 1.0, 2: 1.25, 3: 1.5, 4: 1.8}
                        resultado[tipo][str(beds)] = round(base * mults[beds], 0)
        return resultado
    except Exception as e:
        print(f"  Error procesando {ciudad_nombre}: {e}")
        return None

def main():
    print(f"=== Actualizando precios — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    prices = {
        "actualizado": datetime.now().strftime("%Y-%m-%d"),
        "fuente": "Inside Airbnb (insideairbnb.com)",
        "ciudades": {}
    }
    for ciudad, base_url in CIUDADES.items():
        print(f"\n📍 {ciudad}")
        csv_url = get_latest_listings_url(base_url)
        if not csv_url:
            print(f"  No se encontró dataset, usando valores existentes")
            continue
        datos = procesar_ciudad(ciudad, csv_url)
        if datos:
            prices["ciudades"][ciudad] = datos
            print(f"  ✓ {ciudad} procesada")
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
    print(f"\n✅ prices.json actualizado con {len(prices['ciudades'])} ciudades")

if __name__ == "__main__":
    main()

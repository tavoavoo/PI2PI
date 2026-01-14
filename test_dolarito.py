import time
import sys
import os

# Truco para importar tus módulos desde la carpeta raíz
sys.path.append(os.getcwd())

try:
    from views.dashboard_modules.scrapers import DolaritoScraper, BinanceP2PScraper
    print("✅ Módulos importados correctamente.\n")
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("Asegúrate de ejecutar este archivo desde la carpeta raíz del proyecto.")
    sys.exit()

def test_dolarito_vivo():
    print("--- 🧪 TEST 1: DOLARITO (PRECIOS EN VIVO) ---")
    scraper = DolaritoScraper()
    
    start = time.time()
    print("⏳ Solicitando datos a Dolarito (vía Requests/Soup)...")
    
    # Aquí probamos la función que reemplazamos
    datos = scraper.obtener_precios_vivo()
    
    end = time.time()
    tiempo = end - start
    
    if datos:
        print(f"✅ ¡ÉXITO! Tiempo de respuesta: {tiempo:.2f} segundos")
        print(f"💵 BLUE: {datos.get('blue')}")
        print(f"📉 MEP:  {datos.get('mep')}")
        print(f"📈 CCL:  {datos.get('ccl')} <--- (Lo importante)")
        
        if datos.get('ccl') and datos.get('ccl')[0] > 0:
            print("✅ El CCL llegó correctamente.")
        else:
            print("⚠️ El CCL llegó vacío o en 0.")
    else:
        print("❌ FALLO: No se recibieron datos (retornó None).")
    print("-" * 40 + "\n")

def test_binance_radar():
    print("--- 🧪 TEST 2: BINANCE (RADAR DE PRESIÓN) ---")
    scraper = BinanceP2PScraper()
    
    start = time.time()
    print("⏳ Escaneando Order Book de Binance P2P...")
    
    data = scraper.get_order_book_pressure()
    
    end = time.time()
    tiempo = end - start
    
    if data:
        print(f"✅ ¡ÉXITO! Tiempo de respuesta: {tiempo:.2f} segundos")
        print(f"🟢 Compradores (Volumen): {data['volumen_demanda']:,.2f} USDT")
        print(f"🔴 Vendedores (Volumen):  {data['volumen_oferta']:,.2f} USDT")
        print(f"🏷️ Mejor Precio Compra:   $ {data['precio_compra']}")
        print(f"🏷️ Mejor Precio Venta:    $ {data['precio_venta']}")
        print(f"↔️ Spread Pág 1:          $ {data['spread']:.2f}")
    else:
        print("❌ FALLO: Binance no respondió o cambió la API.")
    print("-" * 40 + "\n")

if __name__ == "__main__":
    print("INICIANDO PROTOCOLO DE PRUEBA DE MOTORES...\n")
    test_dolarito_vivo()
    test_binance_radar()
    print("🏁 PRUEBA FINALIZADA.")
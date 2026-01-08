import requests
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

class BinanceClient:
    """
    Cliente BLINDADO para API Binance P2P.
    Implementa lógica manual de firma y parseo contable estricto (Maker/Taker).
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.p2p_url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

    def fetch_history_incremental(self, api_key, api_secret, db_cursor):
        """
        Trae historial con PAGINACIÓN AUTOMÁTICA y ventana de seguridad de 7 DÍAS.
        Esto asegura que no queden huecos si no abres la app por un par de días.
        """
        # 1. Obtener IDs ya existentes para no duplicar
        db_cursor.execute("SELECT order_id FROM operaciones WHERE order_id IS NOT NULL")
        existing_ids = set(str(row[0]) for row in db_cursor.fetchall())

        all_orders = []
        endpoint = "/sapi/v1/c2c/orderMatch/listUserOrderHistory"

        # --- CAMBIO CLAVE: 7 DÍAS ---
        # 7 días es el equilibrio perfecto: Rápido como 24h, seguro como 30 días.
        end_ts = int(time.time() * 1000)
        start_ts = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

        # 2. Hacemos 2 viajes INDEPENDIENTES (Buy y Sell)
        for trade_type in ["BUY", "SELL"]:
            current_page = 1
            while True: # Bucle infinito hasta que se rompa (break)
                try:
                    tipo_visual = "Compra" if trade_type == "BUY" else "Venta"
                    
                    params = {
                        "timestamp": int(time.time() * 1000),
                        "startTimestamp": start_ts, 
                        "endTimestamp": end_ts,
                        "tradeType": trade_type,
                        "rows": 100, # Pedimos el bloque máximo
                        "page": current_page, 
                        "recvWindow": 20000 
                    }

                    # Firma
                    query_string = urlencode(sorted(params.items()))
                    signature = hmac.new(
                        api_secret.encode('utf-8'), 
                        query_string.encode('utf-8'), 
                        hashlib.sha256
                    ).hexdigest()
                    
                    full_url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                    headers = {"X-MBX-APIKEY": api_key}

                    # Disparo
                    # print(f"📡 {trade_type} Pág {current_page}...") # Descomentar para debug
                    response = requests.get(full_url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        raw_list = data.get("data", [])
                        
                        if not raw_list:
                            break # Se acabaron los datos
                        
                        # Parseamos este lote
                        parsed_list = self._parse_orders(raw_list, tipo_visual, existing_ids)
                        all_orders.extend(parsed_list)
                        
                        # Si trajo menos de 100, es la última página.
                        if len(raw_list) < 100:
                            break
                        
                        # Si trajo 100, seguimos a la siguiente página
                        current_page += 1
                        time.sleep(0.1) 
                        
                    else:
                        print(f"⚠️ Error Binance {trade_type}: {response.text}")
                        break 

                except Exception as e:
                    print(f"❌ Error crítico obteniendo {trade_type}: {e}")
                    break

        # 3. Ordenamos todo por fecha
        all_orders.sort(key=lambda x: x['fecha'])
        return all_orders

    def _parse_orders(self, orders, tipo, existing_ids):
            """
            Lógica Contable Exacta (Corrección Definitiva V3):
            - COMPRA: Stock = Amount - Fee (Lo que entra al bolsillo).
            - VENTA:  Stock = Amount + Fee (Lo que sale de la billetera).
            """
            parsed = []
            
            for order in orders:
                order_id = str(order.get("orderNumber"))
                
                # Filtros básicos
                if order_id in existing_ids: continue
                if order.get("orderStatus") != "COMPLETED": continue

                # --- DATOS GENERALES ---
                ts = order.get("createTime", 0)
                fecha = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                fiat_total = float(order.get("totalPrice", 0))
                moneda = order.get("fiat", "ARS")
                cotizacion = float(order.get("unitPrice", 0)) # Precio pactado limpio
                
                # --- LÓGICA DE ROL Y MONTO NETO ---
                # Variables crudas
                raw_amount = float(order.get("amount", 0))          # Monto tradeado (lo que recibe/envía el cliente)
                raw_comm = float(order.get("commission", 0))        # Comisión estándar
                raw_taker_comm = float(order.get("takerCommission", 0)) # Comisión Taker
                
                # Determinación de Rol
                # Si hay comisión Taker explícita, usamos esa. Si no, la estándar.
                if raw_taker_comm > 0 or float(order.get("takerCommissionRate", 0)) > 0:
                    rol = "Taker"
                    fee_usdt = raw_taker_comm
                else:
                    rol = "Maker"
                    fee_usdt = raw_comm

                # --- LÓGICA MAESTRA DE STOCK (CORREGIDA) ---
                
                if tipo == "Compra":
                    # COMPRA: Te depositan el monto MENOS la comisión.
                    # Ejemplo: Compras 100, Fee 0.1 -> Entran 99.9
                    usdt_real = raw_amount - fee_usdt
                else:
                    # VENTA: De tu billetera sale el monto al cliente MÁS la comisión.
                    # Ejemplo: Vendes 19.38, Fee 0.03 -> Binance te descuenta 19.41
                    usdt_real = raw_amount + fee_usdt

                # Redondeo de seguridad para evitar decimales flotantes infinitos
                usdt_real = round(usdt_real, 8)

                # --- DETECTOR DE BANCO (Para sugerir) ---
                metodo_bruto = order.get("payMethodName", "")
                banco_detectado = "Por Clasificar"
                
                # Mapeo simple
                if "Brubank" in metodo_bruto: banco_detectado = "Brubank"
                elif "MercadoPago" in metodo_bruto: banco_detectado = "MercadoPago"
                elif "Lemon" in metodo_bruto: banco_detectado = "Lemon Cash"
                elif "Uala" in metodo_bruto: banco_detectado = "Ualá"
                elif "Galicia" in metodo_bruto: banco_detectado = "Galicia"
                elif "Prex" in metodo_bruto: banco_detectado = "Prex"
                elif "Santander" in metodo_bruto: banco_detectado = "Santander"
                elif "BBVA" in metodo_bruto: banco_detectado = "BBVA"

                nick = order.get("counterPartNickName", "Desconocido")

                parsed.append({
                    'fecha': fecha,
                    'nick': nick,
                    'tipo': tipo,
                    'fiat': fiat_total,
                    'usdt_nominal': usdt_real,  # Dato corregido (Impacto Real)
                    'cot': cotizacion,          
                    'fee': fee_usdt,
                    'moneda': moneda,
                    'order_id': order_id,
                    'rol': rol,
                    'stock_impact': usdt_real,  # Impacto en stock
                    'banco_api': banco_detectado
                })
                
            return parsed

    # --- MÉTODOS DE SCRAPING (Sin cambios) ---
    def fetch_p2p_depth(self, trade_type, fiat, asset, rows=20, db_connection=None):
        payload = {
            "asset": asset, "fiat": fiat, "merchantCheck": False, "page": 1,
            "payTypes": [], "publisherType": None, "rows": rows, "tradeType": trade_type
        }
        try:
            r = requests.post(self.p2p_url, json=payload, timeout=5)
            if r.status_code == 200:
                data = r.json()
                ads = data.get("data", [])
                if db_connection:
                    try:
                        cursor = db_connection.cursor()
                        cursor.execute("SELECT nickname FROM p2p_blacklist")
                        blacklist = set(row[0] for row in cursor.fetchall())
                        ads = [ad for ad in ads if ad.get("advertiser", {}).get("nickName") not in blacklist]
                    except: pass
                return sorted([float(ad.get("adv", {}).get("price", 0)) for ad in ads if ad.get("adv")], reverse=(trade_type == "SELL"))
            return []
        except: return []

    def fetch_p2p_price(self, trade_type, fiat, asset, amount):
        prices = self.fetch_p2p_depth(trade_type, fiat, asset, rows=1)
        return prices[0] if prices else 0.0

    def fetch_funding_balance(self, api_key, api_secret):
        endpoint = "/sapi/v1/asset/get-funding-asset"
        try:
            params = {"asset": "USDT", "timestamp": int(time.time() * 1000), "recvWindow": 10000}
            query = urlencode(sorted(params.items()))
            signature = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
            url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
            headers = {"X-MBX-APIKEY": api_key}
            r = requests.post(url, headers=headers, timeout=5)
            if r.status_code == 200: return float(r.json().get("free", 0))
        except: pass
        return 0.0
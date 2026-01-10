import requests
import hmac
import hashlib
import time
from datetime import datetime
from urllib.parse import urlencode

class BinanceClient:
    """
    Cliente P2P V4 (Soporte Multipage + Fecha de Inicio Rígida).
    """
    
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.p2p_url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

    def fetch_history_incremental(self, api_key, api_secret, db_cursor):
        """
        Trae historial de Binance.
        CONFIGURADO: Solo trae operaciones desde el 08/12/2025 en adelante.
        """
        # 1. Obtener IDs ya existentes para no procesarlos de nuevo
        db_cursor.execute("SELECT order_id FROM operaciones WHERE order_id IS NOT NULL")
        existing_ids = set(str(row[0]) for row in db_cursor.fetchall())

        all_orders = []
        endpoint = "/sapi/v1/c2c/orderMatch/listUserOrderHistory"
        
        # --- FECHA DE INICIO RÍGIDA: 08 DE DICIEMBRE 2025 ---
        fecha_inicio_negocio = datetime(2025, 12, 8) 
        start_ts = int(fecha_inicio_negocio.timestamp() * 1000)
        
        # Fecha fin: Ahora mismo
        end_ts = int(time.time() * 1000)

        for trade_type in ["BUY", "SELL"]:
            current_page = 1
            while True: 
                try:
                    tipo_visual = "Compra" if trade_type == "BUY" else "Venta"
                    timestamp_seguro = int((time.time() - 2) * 1000)
                    
                    params = {
                        "timestamp": timestamp_seguro, 
                        "startTimestamp": start_ts, # <--- AQUI SE APLICA EL FILTRO
                        "endTimestamp": end_ts, 
                        "tradeType": trade_type,
                        "rows": 100, 
                        "page": current_page, 
                        "recvWindow": 20000 
                    }
                    
                    query_string = urlencode(sorted(params.items()))
                    signature = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
                    full_url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
                    
                    headers = {"X-MBX-APIKEY": api_key}
                    response = requests.get(full_url, headers=headers, timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        raw_list = data.get("data", [])
                        
                        if not raw_list: break 
                        
                        # Parseamos y filtramos lo que ya existe
                        parsed_list = self._parse_orders(raw_list, tipo_visual, existing_ids)
                        all_orders.extend(parsed_list)
                        
                        if len(raw_list) < 100: break # Fin de páginas
                        current_page += 1
                        time.sleep(0.1) 
                    else: break 
                except: break
                
        all_orders.sort(key=lambda x: x['fecha'])
        return all_orders

    def _parse_orders(self, orders, tipo, existing_ids):
        parsed = []
        for order in orders:
            order_id = str(order.get("orderNumber"))
            
            # FILTRO DE SEGURIDAD 1: Si ya existe en DB, ignorar
            if order_id in existing_ids: continue
            
            # FILTRO DE ESTADO: Solo completadas
            if order.get("orderStatus") != "COMPLETED": continue
            
            ts = order.get("createTime", 0)
            fecha = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
            
            fiat_total = float(order.get("totalPrice", 0))
            moneda = order.get("fiat", "ARS")
            cotizacion = float(order.get("unitPrice", 0))
            
            raw_amount = float(order.get("amount", 0))          
            raw_comm = float(order.get("commission", 0))        
            raw_taker_comm = float(order.get("takerCommission", 0)) 
            
            if raw_taker_comm > 0 or float(order.get("takerCommissionRate", 0)) > 0:
                rol = "Taker"; fee_usdt = raw_taker_comm
            else:
                rol = "Maker"; fee_usdt = raw_comm
                
            if tipo == "Compra": usdt_real = raw_amount - fee_usdt
            else: usdt_real = raw_amount + fee_usdt
            
            usdt_real = round(usdt_real, 8)
            
            metodo_bruto = order.get("payMethodName", "")
            banco_detectado = "Por Clasificar"
            
            # Detector básico de banco (Ayuda inicial)
            if "Brubank" in metodo_bruto: banco_detectado = "Brubank"
            elif "MercadoPago" in metodo_bruto: banco_detectado = "MercadoPago"
            elif "Lemon" in metodo_bruto: banco_detectado = "Lemon Cash"
            elif "Uala" in metodo_bruto: banco_detectado = "Ualá"
            elif "Galicia" in metodo_bruto: banco_detectado = "Galicia"
            elif "Prex" in metodo_bruto: banco_detectado = "Prex"
            elif "Santander" in metodo_bruto: banco_detectado = "Santander"
            elif "BBVA" in metodo_bruto: banco_detectado = "BBVA"
            elif "Nacion" in metodo_bruto or "Nación" in metodo_bruto: banco_detectado = "Banco Nacion"
            
            nick = order.get("counterPartNickName", "Desconocido")
            
            parsed.append({
                'fecha': fecha, 'nick': nick, 'tipo': tipo, 
                'fiat': fiat_total, 'usdt_nominal': usdt_real, 
                'cot': cotizacion, 'fee': fee_usdt, 'moneda': moneda, 
                'order_id': order_id, 'rol': rol, 'stock_impact': usdt_real, 
                'banco_api': banco_detectado
            })
        return parsed

    def fetch_p2p_depth(self, trade_type, fiat, asset, page=1, rows=20, db_connection=None):
        payload = {
            "asset": asset, "fiat": fiat, 
            "merchantCheck": False, 
            "publisherType": "merchant",
            "page": page,
            "payTypes": [], 
            "rows": rows, 
            "tradeType": trade_type
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
            timestamp_seguro = int((time.time() - 2) * 1000)
            params = {"asset": "USDT", "timestamp": timestamp_seguro, "recvWindow": 10000}
            query = urlencode(sorted(params.items()))
            signature = hmac.new(api_secret.encode('utf-8'), query.encode('utf-8'), hashlib.sha256).hexdigest()
            url = f"{self.base_url}{endpoint}?{query}&signature={signature}"
            headers = {"X-MBX-APIKEY": api_key}
            r = requests.post(url, headers=headers, timeout=5)
            if r.status_code == 200: return float(r.json().get("free", 0))
        except: pass
        return 0.0
import time
from datetime import datetime

class DashboardLogic:
    def __init__(self, api_client, db_cursor, db_connection):
        self.api = api_client
        self.cursor = db_cursor
        self.conn = db_connection
        self.ultimo_registro_db = 0

    def ejecutar_escaneo(self, ak, ask, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, mep_val, blue_val, ccl_val, mep_pct, blue_pct, ccl_pct, ccl_tipo="VIVO"):
        try:
            # 1. CAPTURA DE PUNTAS
            
            # A) TRAEMOS LOS VENDEDORES (Para tu estrategia de VENTA)
            # - Tu quieres Vender en Fila 8.
            # - Fila 8 está en Página 1. UNA sola llamada basta.
            # - API "BUY" = Advertisers Selling = Competencia para tu Venta.
            try:
                asks_page1 = self.api.fetch_p2p_depth("BUY", "ARS", "USDT", page=1, rows=20, db_connection=self.conn)
                asks_total = asks_page1
            except: asks_total = []

            # B) TRAEMOS LOS COMPRADORES (Para tu estrategia de COMPRA)
            # - Tu quieres Comprar en Fila 24.
            # - Fila 24 está en Página 2. Necesitamos llamada doble.
            # - API "SELL" = Advertisers Buying = Competencia para tu Compra.
            try:
                bids_page1 = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", page=1, rows=20, db_connection=self.conn)
                bids_page2 = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", page=2, rows=20, db_connection=self.conn)
                bids_total = bids_page1 + bids_page2 # Lista combinada (40 resultados)
            except: bids_total = []
            
            # 2. DEFINICIÓN DE PUNTOS ESTRATÉGICOS
            
            # --- MEJOR VENTA (Tú vendes USDT) ---
            # Objetivo: Fila 8 (Indice 7) de la lista ASKS.
            idx_tu_venta = 7 
            if len(asks_total) > idx_tu_venta:
                market_ask_p2p5 = asks_total[idx_tu_venta]
            else:
                market_ask_p2p5 = asks_total[-1] if asks_total else 0.0

            # --- MEJOR COMPRA (Tú compras USDT) ---
            # Objetivo: Fila 24 (Indice 23) de la lista BIDS.
            idx_tu_compra = 23
            if len(bids_total) > idx_tu_compra:
                market_bid_p2p5 = bids_total[idx_tu_compra]
            else:
                # Si no hay 24, agarramos el último de la página 2
                market_bid_p2p5 = bids_total[-1] if bids_total else 0.0
            
            # Referencias Visuales (Puntas Fila 1)
            market_ask_1 = asks_total[0] if asks_total else 0.0
            market_bid_1 = bids_total[0] if bids_total else 0.0
            market_ask_2 = asks_total[1] if len(asks_total) > 1 else market_ask_1
            
            # ... (El resto del código de Gaps, Historial y Profits sigue IDÉNTICO) ...
            
            # 3. DATOS DE CUENTA
            real_stock = "---"
            if ak and ask:
                try: 
                    val = self.api.fetch_funding_balance(ak, ask)
                    real_stock = f"{val:.2f}"
                except: pass
            
            # 4. GAPS
            gap_vivo = 0.0
            if mep_val > 0 and market_ask_2 > 0: gap_vivo = ((market_ask_2 / mep_val) - 1) * 100
            
            gap_ccl = 0.0
            if ccl_val > 0 and market_ask_p2p5 > 0: 
                gap_ccl = ((market_ask_2 / ccl_val) - 1) * 100

            canje_vivo = 0.0
            if mep_val > 0 and ccl_val > 0:
                canje_vivo = ((ccl_val / mep_val) - 1) * 100
            
            # 5. HISTORIAL
            tiempo_actual = time.time()
            if market_ask_p2p5 > 0 and ccl_val > 0:
                if (tiempo_actual - self.ultimo_registro_db) >= 60:
                    try:
                        ahora = datetime.now()
                        f_fecha = ahora.strftime('%Y-%m-%d')
                        f_hora = ahora.strftime('%H:%M:%S')
                        
                        query = "INSERT INTO p2p_history (fecha, hora, usdt_buy_p5, usdt_sell_p5, mep, ccl, gap_ccl, ccl_tipo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                        datos = (f_fecha, f_hora, market_bid_p2p5, market_ask_p2p5, mep_val, ccl_val, gap_ccl, ccl_tipo)
                        self.cursor.execute(query, datos)
                        self.conn.commit()
                        self.ultimo_registro_db = tiempo_actual 
                    except: pass

            # 6. PROFIT
            profit_c_buy = 0.0
            if market_ask_1 > 0 and market_ask_p2p5 > 0:
                costo_compra = market_ask_1 * (1 + taker_fee)
                ingreso_venta = market_ask_p2p5 * (1 - maker_fee)
                profit_c_buy = ((ingreso_venta / costo_compra) - 1) * 100

            profit_c_sell = 0.0
            if market_bid_1 > 0 and ppp > 0:
                ingreso_venta = market_bid_1 * (1 - taker_fee)
                profit_c_sell = ((ingreso_venta / ppp) - 1) * 100
            elif market_bid_1 > 0 and ppp == 0:
                profit_c_sell = -999.0

            return {
                "status": "success",
                "data": (blue_val, mep_val, ccl_val, 
                         market_ask_1, market_ask_p2p5, market_bid_1, market_bid_p2p5, 
                         real_stock, gap_vivo, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, 
                         mep_pct, blue_pct, ccl_pct, gap_ccl, canje_vivo,
                        profit_c_buy, profit_c_sell, ccl_tipo)
            }
        except Exception as e:
            return {"status": "error", "msg": str(e)}
import time
from datetime import datetime

class DashboardLogic:
    def __init__(self, api_client, db_cursor, db_connection):
        self.api = api_client
        self.cursor = db_cursor
        self.conn = db_connection
        self.ultimo_registro_db = 0

    # AGREGAMOS ccl_tipo AL FINAL DE LOS ARGUMENTOS
    def ejecutar_escaneo(self, ak, ask, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, mep_val, blue_val, ccl_val, mep_pct, blue_pct, ccl_pct, ccl_tipo="VIVO"):
        try:
            # 1. CAPTURA DE PUNTAS
            try:
                bids_response = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", rows=20, db_connection=self.conn)
                asks_response = self.api.fetch_p2p_depth("BUY", "ARS", "USDT", rows=20, db_connection=self.conn)
            except:
                bids_response = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", db_connection=self.conn)
                asks_response = self.api.fetch_p2p_depth("BUY", "ARS", "USDT", db_connection=self.conn)
            
            # 2. DEFINICIÓN DE PUNTOS
            market_ask_1 = asks_response[0] if asks_response else 0.0
            market_bid_1 = bids_response[0] if bids_response else 0.0
            
            market_ask_2 = asks_response[1] if len(asks_response) > 1 else market_ask_1
            
            market_ask_p2p5 = asks_response[14] if len(asks_response) > 14 else (asks_response[-1] if asks_response else 0.0)
            market_bid_p2p5 = bids_response[14] if len(bids_response) > 14 else (bids_response[-1] if bids_response else 0.0)
            
            # 3. DATOS DE CUENTA
            real_stock = "---"
            if ak and ask:
                try: 
                    val = self.api.fetch_funding_balance(ak, ask)
                    real_stock = f"{val:.2f}"
                except: pass
            
            # 4. CÁLCULO DE GAPS (USDT)
            gap_vivo = 0.0
            if mep_val > 0 and market_ask_2 > 0: gap_vivo = ((market_ask_2 / mep_val) - 1) * 100
            
            # GAP REAL (TU PRECIO vs CCL)
            gap_ccl = 0.0
            if ccl_val > 0 and market_ask_p2p5 > 0: # Usamos p2p5 (tu venta promedio) o ask_2 según prefieras
                # Usaremos ask_2 para ser más reactivos al mercado inmediato, o p2p5 para ser conservadores.
                # Estandarizamos en ask_2 (competencia directa)
                gap_ccl = ((market_ask_2 / ccl_val) - 1) * 100

            canje_vivo = 0.0
            if mep_val > 0 and ccl_val > 0:
                canje_vivo = ((ccl_val / mep_val) - 1) * 100
            
            # 5. REGISTRO HISTÓRICO (CADA 1 MIN)
            # Solo guardamos si tenemos datos válidos
            tiempo_actual = time.time()
            if market_ask_p2p5 > 0 and ccl_val > 0:
                if (tiempo_actual - self.ultimo_registro_db) >= 60:
                    try:
                        ahora = datetime.now()
                        f_fecha = ahora.strftime('%Y-%m-%d')
                        f_hora = ahora.strftime('%H:%M:%S')
                        
                        # Intentamos guardar con la columna nueva ccl_tipo
                        # Si la columna no existe (porque no actualizaste DB), fallará silenciosamente el INSERT nuevo
                        # y podríamos hacer un fallback, pero mejor actualizamos la DB en el paso 4.
                        query = """
                            INSERT INTO p2p_history (fecha, hora, usdt_buy_p5, usdt_sell_p5, mep, ccl, gap_ccl, ccl_tipo)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        datos = (f_fecha, f_hora, market_bid_p2p5, market_ask_p2p5, mep_val, ccl_val, gap_ccl, ccl_tipo)
                        self.cursor.execute(query, datos)
                        self.conn.commit()
                        self.ultimo_registro_db = tiempo_actual 
                    except Exception as e:
                        # Si falla (ej: falta columna), intentamos el insert viejo
                        try:
                            query_old = "INSERT INTO p2p_history (fecha, hora, usdt_buy_p5, usdt_sell_p5, mep, ccl, gap_ccl) VALUES (?, ?, ?, ?, ?, ?, ?)"
                            datos_old = (f_fecha, f_hora, market_bid_p2p5, market_ask_p2p5, mep_val, ccl_val, gap_ccl)
                            self.cursor.execute(query_old, datos_old)
                            self.conn.commit()
                            self.ultimo_registro_db = tiempo_actual
                        except:
                            print(f"⚠️ No se pudo grabar historial: {e}")

            # Estrategias
            profit_c_buy = 0.0
            if len(asks_response) > 14 and market_ask_1 > 0 and market_ask_p2p5 > 0:
                costo_compra = market_ask_1 * (1 + taker_fee)
                ingreso_venta = market_ask_p2p5 * (1 - maker_fee)
                profit_c_buy = ((ingreso_venta / costo_compra) - 1) * 100

            profit_c_sell = 0.0
            if market_bid_1 > 0 and ppp > 0:
                ingreso_venta = market_bid_1 * (1 - taker_fee)
                profit_c_sell = ((ingreso_venta / ppp) - 1) * 100
            elif market_bid_1 > 0 and ppp == 0:
                profit_c_sell = -999.0

            # 6. RETORNO (Agregamos ccl_tipo al final)
            return {
                "status": "success",
                "data": (blue_val, mep_val, ccl_val, 
                         market_ask_1, market_ask_p2p5, market_bid_1, market_bid_p2p5, 
                         real_stock, gap_vivo, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, 
                         mep_pct, blue_pct, ccl_pct, gap_ccl, canje_vivo,
                        profit_c_buy, profit_c_sell, ccl_tipo) # <--- NUEVO
            }
        except Exception as e:
            return {"status": "error", "msg": str(e)}
import time
from datetime import datetime
from datetime import datetime, time as dt_time

class DashboardLogic:
    def __init__(self, api_client, db_cursor, db_connection):
        self.api = api_client
        self.cursor = db_cursor
        self.conn = db_connection
        self.ultimo_registro_db = 0
        self.precio_cierre_usdt = None
        self.fecha_ultimo_cierre = None

    def ejecutar_escaneo(self, ak, ask, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, mep_val, blue_val, ccl_val, mep_pct, blue_pct, ccl_pct):
        try:
            # 1. CAPTURA NORMAL
            try:
                bids_response = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", rows=20, db_connection=self.conn)
                asks_response = self.api.fetch_p2p_depth("BUY", "ARS", "USDT", rows=20, db_connection=self.conn)
            except:
                bids_response = self.api.fetch_p2p_depth("SELL", "ARS", "USDT", db_connection=self.conn)
                asks_response = self.api.fetch_p2p_depth("BUY", "ARS", "USDT", db_connection=self.conn)
            
            # 2. DEFINICIÓN DE PUNTOS CON CIERRE SINCRONIZADO
            market_bid_1 = bids_response[0] if bids_response else 0.0
            
            # ✨ CAMBIO CLAVE: Usar función de cierre sincronizado
            market_ask_1 = asks_response[0] if asks_response else 0.0  # Para operaciones inmediatas
            market_ask_2 = self.obtener_precio_usdt_con_cierre(asks_response)  # CON LÓGICA DE CIERRE
            
            # Fila 15 con seguridad
            market_ask_p2p5 = asks_response[14] if len(asks_response) > 14 else (asks_response[-1] if asks_response else 0.0)
            market_bid_p2p5 = bids_response[14] if len(bids_response) > 14 else (bids_response[-1] if bids_response else 0.0)
            
            # 3. DATOS DE CUENTA
            real_stock = "---"
            if ak and ask:
                try: 
                    val = self.api.fetch_funding_balance(ak, ask)
                    real_stock = f"{val:.2f}"
                except: pass
            
            # 4. CÁLCULO DE GAPS (Ahora usa market_ask_2 con cierre sincronizado)
            gap_vivo = 0.0
            if mep_val > 0 and market_ask_2 > 0: 
                gap_vivo = ((market_ask_2 / mep_val) - 1) * 100
            
            gap_ccl = 0.0
            if ccl_val > 0 and market_ask_2 > 0: 
                gap_ccl = ((market_ask_2 / ccl_val) - 1) * 100

            # CANJE PURO (CCL vs MEP)
            canje_vivo = 0.0
            if mep_val > 0 and ccl_val > 0:
                canje_vivo = ((ccl_val / mep_val) - 1) * 100
            
            # 5. REGISTRO HISTÓRICO (CADA 1 MIN) - Ahora guarda con cierre sincronizado
            tiempo_actual = time.time()
            if market_ask_2 > 0 and ccl_val > 0:
                if (tiempo_actual - self.ultimo_registro_db) >= 60:
                    try:
                        ahora = datetime.now()
                        f_fecha = ahora.strftime('%Y-%m-%d')
                        f_hora = ahora.strftime('%H:%M:%S')
                        
                        # ✨ GUARDAR CON INDICADOR DE CIERRE
                        hora_actual = ahora.time()
                        es_cierre = dt_time(17, 30) <= hora_actual <= dt_time(18, 15)
                        
                        query = """
                            INSERT INTO p2p_history (fecha, hora, usdt_buy_p5, usdt_sell_p5, mep, ccl, gap_ccl)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                        datos = (f_fecha, f_hora, market_bid_p2p5, market_ask_2, mep_val, ccl_val, gap_ccl)
                        self.cursor.execute(query, datos)
                        self.conn.commit()
                        self.ultimo_registro_db = tiempo_actual
                        
                        if es_cierre:
                            print(f"📊 [REGISTRO CIERRE] {f_fecha} {f_hora} - USDT: ${market_ask_2:.2f} | CCL: ${ccl_val:.2f}")
                        
                    except Exception as e:
                        print(f"⚠️ No se pudo grabar historial: {e}")
            
            # 6. PROFIT CALCULATIONS (sin cambios)
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

            # 7. RETORNO (market_ask_2 ahora tiene lógica de cierre)
            return {
                "status": "success",
                "data": (blue_val, mep_val, ccl_val, 
                         market_ask_1, market_ask_p2p5, market_bid_1, market_bid_p2p5, 
                         real_stock, gap_vivo, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, saldo_usd_fiat, 
                         mep_pct, blue_pct, ccl_pct, gap_ccl, canje_vivo,
                         profit_c_buy, profit_c_sell)
            }
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    def obtener_precio_usdt_con_cierre(self, asks_response):
            """
            🕐 LÓGICA DE CIERRE DIARIO SINCRONIZADO CON CCL
            
            Horarios:
            - Antes de 17:30: Usa precio en tiempo real
            - 17:30 - 18:15: Toma snapshot y lo congela hasta el próximo día hábil
            - Después de 18:15: Usa el snapshot congelado
            - Fines de semana: Usa snapshot del viernes
            
            Args:
                asks_response: Lista de precios USDT P2P en tiempo real
                
            Returns:
                float: Precio USDT (real o congelado según horario)
            """
            ahora = datetime.now()
            hora_actual = ahora.time()
            dia_semana = ahora.weekday()  # 0=Lun, 4=Vie, 5=Sáb, 6=Dom
            fecha_hoy = ahora.strftime("%Y-%m-%d")
            
            # Definir ventanas horarias
            HORA_CIERRE_INICIO = dt_time(17, 30)  # 17:30
            HORA_CIERRE_FIN = dt_time(18, 15)     # 18:15
            
            # =========================================================================
            # CASO 1: FIN DE SEMANA (Sábado o Domingo)
            # =========================================================================
            if dia_semana >= 5:  # Sábado (5) o Domingo (6)
                if self.precio_cierre_usdt is not None:
                    print(f"📌 [FIN DE SEMANA] Usando cierre del viernes: ${self.precio_cierre_usdt:.2f}")
                    return self.precio_cierre_usdt
                else:
                    # Si no hay cierre guardado, usar el precio actual (primer inicio)
                    precio_actual = asks_response[1] if len(asks_response) > 1 else asks_response[0]
                    return precio_actual
            
            # =========================================================================
            # CASO 2: DÍA HÁBIL - ANTES DEL CIERRE (Antes de 17:30)
            # =========================================================================
            if hora_actual < HORA_CIERRE_INICIO:
                precio_actual = asks_response[1] if len(asks_response) > 1 else asks_response[0]
                print(f"⏰ [PRE-CIERRE] Precio en vivo: ${precio_actual:.2f} (cierra a las 17:30)")
                return precio_actual
            
            # =========================================================================
            # CASO 3: VENTANA DE CIERRE (17:30 - 18:15)
            # =========================================================================
            if HORA_CIERRE_INICIO <= hora_actual <= HORA_CIERRE_FIN:
                precio_actual = asks_response[1] if len(asks_response) > 1 else asks_response[0]
                
                # Si es un nuevo día, o no tenemos cierre del día actual, tomar snapshot
                if self.fecha_ultimo_cierre != fecha_hoy:
                    self.precio_cierre_usdt = precio_actual
                    self.fecha_ultimo_cierre = fecha_hoy
                    
                    # Guardar en BD para persistencia
                    try:
                        self.cursor.execute("""
                            INSERT OR REPLACE INTO config (key, value) 
                            VALUES ('ultimo_cierre_usdt', ?), ('fecha_ultimo_cierre', ?)
                        """, (str(precio_actual), fecha_hoy))
                        self.conn.commit()
                    except:
                        pass
                    
                    print(f"📸 [SNAPSHOT] Precio de cierre capturado: ${precio_actual:.2f}")
                
                return self.precio_cierre_usdt
            
            # =========================================================================
            # CASO 4: DESPUÉS DEL CIERRE (Después de 18:15)
            # =========================================================================
            if hora_actual > HORA_CIERRE_FIN:
                # Si tenemos cierre del día actual, usarlo
                if self.fecha_ultimo_cierre == fecha_hoy and self.precio_cierre_usdt is not None:
                    print(f"🔒 [POST-CIERRE] Usando precio congelado: ${self.precio_cierre_usdt:.2f}")
                    return self.precio_cierre_usdt
                else:
                    # Si no hay cierre (ej: primer día), cargar de BD o usar actual
                    self._cargar_ultimo_cierre_desde_bd()
                    
                    if self.precio_cierre_usdt is not None:
                        return self.precio_cierre_usdt
                    else:
                        # Fallback: usar precio actual
                        precio_actual = asks_response[1] if len(asks_response) > 1 else asks_response[0]
                        return precio_actual
            
            # Fallback final
            precio_actual = asks_response[1] if len(asks_response) > 1 else asks_response[0]
            return precio_actual
        
    def _cargar_ultimo_cierre_desde_bd(self):
        """
        Carga el último cierre guardado desde la BD (para persistencia entre sesiones)
        """
        try:
            self.cursor.execute("SELECT value FROM config WHERE key='ultimo_cierre_usdt'")
            res_precio = self.cursor.fetchone()
            
            self.cursor.execute("SELECT value FROM config WHERE key='fecha_ultimo_cierre'")
            res_fecha = self.cursor.fetchone()
            
            if res_precio and res_fecha:
                self.precio_cierre_usdt = float(res_precio[0])
                self.fecha_ultimo_cierre = res_fecha[0]
                print(f"💾 [CARGADO] Cierre anterior: ${self.precio_cierre_usdt:.2f} ({self.fecha_ultimo_cierre})")
        except Exception as e:
            print(f"⚠️ Error cargando cierre desde BD: {e}")
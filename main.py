import sys
import os
import subprocess

# ==============================================================================
# ☢️ PARCHE ANTIVENTANAS (VERSIÓN EQUILIBRADA)
# ==============================================================================
if sys.platform == "win32":
    _original_popen = subprocess.Popen

    def _silent_popen(*args, **kwargs):
        CREATE_NO_WINDOW = 0x08000000
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= CREATE_NO_WINDOW
        return _original_popen(*args, **kwargs)

    subprocess.Popen = _silent_popen
# ==============================================================================
import sqlite3
# --- PARCHE DE RUTA ---
basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(basedir)

import customtkinter as ctk
import sqlite3
from datetime import datetime

# MÓDULOS
from database.db_manager import DBManager
from api.binance_api import BinanceClient
from utils.ui_components import CustomDialog

# VISTAS
from views.dashboard import DashboardView
from views.history import HistorialView
from views.treasury import TesoreriaView
from views.reports import ReportesView
from views.new_op import NuevaOperacionView

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class P2PManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("P2P Manager - V12.0 Persistente") # Actualizamos versión
        self.after(0, lambda: self.state('zoomed'))
        
        # --- INICIALIZACIÓN ---
        self.db = DBManager()
            
        try:
            self.db.cursor.execute("""
                CREATE TABLE IF NOT EXISTS p2p_blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT UNIQUE NOT NULL,
                    fecha_baneo TEXT NOT NULL,
                    motivo TEXT
                )
            """)
            self.db.conn.commit()
        except Exception as e:
            print(f"⚠️ Error creando tabla blacklist: {e}")
        self.conn = self.db.conn
        self.cursor = self.db.cursor
        self.api_client = BinanceClient()
        self.db.setup_blacklist_table()

        try:
            # Esto busca cualquier operación huérfana (NULL) y la marca como activa (0)
            self.cursor.execute("UPDATE operaciones SET archivado = 0 WHERE archivado IS NULL")
            self.conn.commit()
        except Exception as e:
            print(f"Sanidad DB check: {e}")
            self.STOCK_USDT = 0.0

        # Variables Globales
        self.STOCK_USDT = 0.0
        self.COMISION_VENTA = 0.0016
        self.load_config()
        self._migrar_tabla_cierres_si_necesario()
        # --- GUI SETUP ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        ctk.CTkLabel(self.sidebar, text="P2P MANAGER", font=("Arial", 22, "bold")).grid(row=0, column=0, padx=20, pady=30)
        
        self.btns = {}
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="#121212")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        # Agregamos NuevaOperacionView al final de la lista
        for F in (DashboardView, TesoreriaView, HistorialView, ReportesView, NuevaOperacionView):
            page_name = F.__name__
            frame = F(parent=self.main_container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            if hasattr(frame, 'update_view'): frame.update_view() 
            
        # Menú Lateral
        self.add_menu_btn("Dashboard", "DashboardView", 1)
        self.add_menu_btn("Historial", "HistorialView", 2)
        self.add_menu_btn("Tesorería", "TesoreriaView", 3)
        self.add_menu_btn("Reportes", "ReportesView", 4)
        
        ctk.CTkButton(self.sidebar, text="CERRAR TURNO", fg_color="#cf3030", hover_color="#8a1c1c", 
                      command=self.reporte_cierre_sesion).grid(row=9, column=0, padx=20, pady=30, sticky="ew")
        
        self.show_frame("DashboardView")

    # --- LÓGICA CORE ---
    def load_config(self):
        try:
            # MAKER (Tu tasa Bronce: 0.16%)
            self.cursor.execute("SELECT value FROM config WHERE key='comision_maker'")
            res = self.cursor.fetchone()
            self.COMISION_MAKER = float(res[0]) if res else 0.0016 
            
            # TAKER (Tasa Estándar: 0.07%)
            self.cursor.execute("SELECT value FROM config WHERE key='taker_fee'")
            res_t = self.cursor.fetchone()
            self.COMISION_TAKER = float(res_t[0]) if res_t else 0.0007 

            # STOCK
            self.cursor.execute("SELECT value FROM config WHERE key='stock_usdt'")
            res_s = self.cursor.fetchone()
            self.STOCK_USDT = float(res_s[0]) if res_s else 0.0
        except: pass

    def _migrar_tabla_cierres_si_necesario(self):
            """
            Actualiza la tabla 'cierres' para soportar el tracking de stock.
            Solo se ejecuta una vez (al iniciar la app).
            """
            try:
                self.cursor.execute("ALTER TABLE cierres ADD COLUMN stock_cierre_usdt REAL DEFAULT 0")
                self.cursor.execute("ALTER TABLE cierres ADD COLUMN costo_cierre_ars REAL DEFAULT 0")
                self.conn.commit()
                print("✅ Tabla 'cierres' actualizada con tracking de stock")
            except sqlite3.OperationalError:
                pass
            except Exception as e:
                print(f"⚠️ Error migración cierres: {e}")
    def fetch_binance_history(self, ak, ask):
        return self.api_client.fetch_history_incremental(ak, ask, self.cursor)

    def fetch_p2p_price(self, trade_type, fiat, asset, amount):
        return self.api_client.fetch_p2p_price(trade_type, fiat, asset, amount)

    def fetch_funding_balance(self, ak, ask):
        return self.api_client.fetch_funding_balance(ak, ask)

    def obtener_saldo_total_ars(self):
        try:
            self.cursor.execute("SELECT SUM(saldo) FROM cuentas WHERE moneda='ARS'")
            total = self.cursor.fetchone()[0]
            return total if total else 0.0
        except: return 0.0

    def obtener_ppp(self, moneda):
        try:
            # 1. RECUPERAR EL ANCLAJE (El "Polvo" o Stock Residual)
            self.cursor.execute("SELECT value FROM config WHERE key='anchor_fiat'")
            res_af = self.cursor.fetchone()
            anchor_fiat = float(res_af[0]) if res_af else 0.0

            self.cursor.execute("SELECT value FROM config WHERE key='anchor_usdt'")
            res_au = self.cursor.fetchone()
            anchor_usdt = float(res_au[0]) if res_au else 0.0

            # 2. TRAER LAS COMPRAS NUEVAS DEL TURNO ACTUAL
            self.cursor.execute("SELECT monto_usdt, cotizacion, rol FROM operaciones WHERE tipo='Compra' AND moneda=? AND archivado=0", (moneda,))
            compras = self.cursor.fetchall()
            
            new_fiat_ajustado = 0.0
            new_usdt_total = 0.0

            # 3. CÁLCULO DINÁMICO (Costo Real de Ciclo)
            for usdt, precio_base, rol in compras:
                rol_str = str(rol).strip().title() if rol else "Maker"

                # A. Tasa de Entrada (IDA): Lo que pagaste al comprar
                tasa_ida = self.COMISION_MAKER if rol_str == "Maker" else self.COMISION_TAKER
                
                # B. Tasa de Salida (VUELTA): Lo que pagarás al vender (Asumimos Maker)
                tasa_vuelta = self.COMISION_MAKER 
                
                # Costo total porcentual del ciclo
                pct_ciclo = tasa_ida + tasa_vuelta
                
                # Precio de Equilibrio (Break-even)
                # Ejemplo: Precio * (1 + 0.0016 + 0.0016)
                precio_ajustado = precio_base * (1 + pct_ciclo)
                
                # Acumulamos
                gasto_orden = usdt * precio_ajustado
                new_fiat_ajustado += gasto_orden
                new_usdt_total += usdt

            # 4. CÁLCULO PONDERADO FINAL
            total_fiat = anchor_fiat + new_fiat_ajustado
            total_usdt = anchor_usdt + new_usdt_total

            if total_usdt > 0: 
                return total_fiat / total_usdt
            return 0.0
            
        except Exception as e:
            print(f"Error calculando PPP: {e}")
            return 0.0

# --- CÁLCULO DE GANANCIA REAL (CORREGIDO) ---
    def calc_ganancia_rango_ars(self, desde_fecha, hasta_fecha, moneda):
        try:
            # PASO 1: RECUPERAR INVENTARIO INICIAL
            self.cursor.execute(
                """
                SELECT stock_cierre_usdt, costo_cierre_ars 
                FROM cierres 
                WHERE fecha_cierre < ? 
                ORDER BY fecha_cierre DESC 
                LIMIT 1
                """,
                (desde_fecha,)
            )
            
            cierre_previo = self.cursor.fetchone()
            
            if cierre_previo:
                stock_inicial_usdt = cierre_previo[0] if cierre_previo[0] else 0.0
                costo_inicial_ars = cierre_previo[1] if cierre_previo[1] else 0.0
            else:
                stock_inicial_usdt = 0.0
                costo_inicial_ars = 0.0
            
            # PASO 2: CALCULAR FLUJO DE CAJA DEL PERÍODO
            query = """
                SELECT tipo, monto_ars, monto_usdt 
                FROM operaciones 
                WHERE moneda=? 
                AND fecha >= ? 
                AND fecha <= ?
                AND tipo IN ('Compra', 'Venta')
            """
            self.cursor.execute(query, (moneda, desde_fecha, hasta_fecha))
            movimientos = self.cursor.fetchall()

            flujo_ars = 0.0
            compras_ars = 0.0
            compras_usdt = 0.0
            ventas_usdt = 0.0

            for tipo, ars, usdt_neto in movimientos:
                if tipo == 'Venta':
                    flujo_ars += ars
                    ventas_usdt += usdt_neto
                elif tipo == 'Compra':
                    flujo_ars -= ars
                    compras_ars += ars
                    compras_usdt += usdt_neto

            # PASO 3: CALCULAR STOCK FINAL Y SU COSTO
            stock_final_usdt = stock_inicial_usdt + compras_usdt - ventas_usdt
            
            # --- [CORRECCIÓN APLICADA AQUÍ] ---
            if compras_usdt > 0:
                # Si hubo compras, ponderamos con lo nuevo
                costo_total = costo_inicial_ars + compras_ars
                stock_total = stock_inicial_usdt + compras_usdt
                precio_promedio = costo_total / stock_total if stock_total > 0 else 0
                costo_final_ars = stock_final_usdt * precio_promedio
            else:
                # Si NO hubo compras, mantenemos el precio anterior O usamos el PPP global
                if stock_inicial_usdt > 0:
                    precio_referencia = costo_inicial_ars / stock_inicial_usdt
                else:
                    # AQUÍ ESTABA EL ERROR: Antes ponía 0.0
                    # Ahora buscamos el PPP Global como respaldo
                    precio_referencia = self.obtener_ppp(moneda)
                
                # Calculamos el costo del inventario final (que puede ser negativo si vendiste sin stock)
                costo_final_ars = stock_final_usdt * precio_referencia

            # PASO 4: GANANCIA REALIZADA + NO REALIZADA
            variacion_inventario = costo_final_ars - costo_inicial_ars
            ganancia_total = flujo_ars + variacion_inventario

            return ganancia_total

        except Exception as e:
            print(f"❌ Error calculando ganancia: {e}")
            return 0.0

    # --- ESTA ES LA FUNCIÓN BLINDADA (Persistencia Real) ---
    def calc_ganancia_sesion_ars(self, dummy_arg, moneda):
        # Ignoramos 'dummy_arg' (fecha inicio vieja) y buscamos la REAL en la BD
        ultimo_cierre = self.obtener_ultimo_cierre()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculamos desde el ÚLTIMO CIERRE hasta AHORA MISMO
        # Esto hace que el turno sea eterno hasta que decidas cerrarlo.
        return self.calc_ganancia_rango_ars(ultimo_cierre, ahora, moneda)

    def obtener_ultimo_cierre(self):
        try:
            self.cursor.execute("SELECT MAX(fecha_cierre) FROM cierres")
            res = self.cursor.fetchone()
            # Si nunca hubo cierre, empezamos desde el año 2000
            return res[0] if res and res[0] else "2000-01-01 00:00:00"
        except: return "2000-01-01 00:00:00"

    def reporte_cierre_sesion(self):
        # Muestra desde cuándo está abierto el turno actual
        inicio = self.obtener_ultimo_cierre()
        self.ask_confirm("Cerrar Turno", f"¿Confirmar cierre de caja?\n(Turno iniciado: {inicio})", self.do_cierre_sesion)
    
    def do_cierre_sesion(self):
        """
        Cierre de turno MEJORADO con snapshot de inventario.
        Guarda el stock remanente y su costo para el próximo turno.
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 1. Capturamos el estado actual del inventario
            stock_actual = self.STOCK_USDT
            ppp_actual = self.obtener_ppp("ARS")
            costo_stock = stock_actual * ppp_actual
            
            # 2. Guardamos el cierre CON la foto del inventario
            self.cursor.execute(
                """
                INSERT INTO cierres (fecha_cierre, stock_cierre_usdt, costo_cierre_ars) 
                VALUES (?, ?, ?)
                """,
                (now, stock_actual, costo_stock)
            )
            
            self.conn.commit()
            self.refresh_all_views()
            
            # 3. Mostramos resumen visual
            msg = f"📦 Stock Remanente: {stock_actual:.2f} USDT\n"
            msg += f"💰 Costo Promedio: ${ppp_actual:,.2f}\n"
            msg += f"📊 Valor Total: ${costo_stock:,.2f}\n\n"
            msg += "Este inventario se arrastrará al próximo turno."
            
            self.show_info("Turno Cerrado", msg)
            
        except Exception as e:
            self.show_error("Error", f"No se pudo cerrar el turno:\n{str(e)}")

    def reiniciar_ppp(self):
        try:
            # 1. ANALISIS PREVIO (Lógica de Anclaje)
            # Antes de borrar la historia, calculamos cuánto vale tu stock actual
            ppp_actual = self.obtener_ppp("ARS")
            stock_actual = self.STOCK_USDT

            # Si el stock es negativo o cero, el anclaje es 0 (Empezamos limpios)
            if stock_actual <= 0:
                anchor_fiat = 0.0
                anchor_usdt = 0.0
            else:
                # Si hay stock, calculamos su "Costo Histórico" para arrastrarlo
                anchor_fiat = stock_actual * ppp_actual
                anchor_usdt = stock_actual

            # 2. GUARDADO DEL ANCLAJE EN CONFIG (Persistencia)
            self.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('anchor_fiat', ?)", (str(anchor_fiat),))
            self.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('anchor_usdt', ?)", (str(anchor_usdt),))
            
            # 3. ARCHIVADO (Limpieza de operaciones visuales)
            self.cursor.execute("UPDATE operaciones SET archivado = 1 WHERE tipo='Compra'")
            self.conn.commit()
            
            self.refresh_all_views()
            
            # Mensaje inteligente
            msg_stock = f"Stock remanente: {anchor_usdt:.2f} USDT"
            msg_ppp = f"Precio Base: {ppp_actual:.2f}"
            self.show_info("Ciclo Reiniciado con Anclaje", f"{msg_stock}\n{msg_ppp}\n\nLas nuevas compras se promediarán con este remanente.")
            
        except Exception as e:
            self.show_error("Error", str(e))
    def recalcular_ppp_vivo(self):
        """
        Borra el anclaje histórico y recalcula el PPP basándose 
        EXCLUSIVAMENTE en las operaciones activas.
        """
        self.ask_confirm(
            "Recalcular PPP", 
            "¿Querés resetear el anclaje y recalcular el PPP?\n\nEsto ignorará el historial antiguo y tomará solo las compras ACTIVAS usando la nueva lógica Bronce (Dinámica).", 
            self._do_recalculo_ppp
        )

    def _do_recalculo_ppp(self):
        try:
            # 1. Ponemos el Anclaje (memoria vieja) a CERO
            self.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('anchor_fiat', '0.0')")
            self.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('anchor_usdt', '0.0')")
            self.conn.commit()

            # 2. Refrescamos todo. 
            # Como el anclaje es 0, la función obtener_ppp() calculará pura y exclusivamente
            # con las órdenes que están en la tabla 'operaciones' con archivado=0.
            self.refresh_all_views()
            
            # Mostramos el nuevo valor para confirmar
            nuevo_ppp = self.obtener_ppp("ARS")
            self.show_info("Recálculo Exitoso", f"El PPP se ha normalizado.\nNuevo valor: {nuevo_ppp:.2f} ARS")

        except Exception as e:
            self.show_error("Error", str(e))
    def show_view(self, view_name):
            """Muestra la vista solicitada y oculta las demás."""
            view = self.frames.get(view_name)
            if view:
                view.tkraise()
            else:
                print(f"Error: La vista {view_name} no existe.")
    def refresh_all_views(self):
        for f in self.frames.values():
            if hasattr(f, 'update_view'): f.update_view()

    # --- UI HELPERS ---
    def add_menu_btn(self, text, view_name, r):
        b = ctk.CTkButton(self.sidebar, text=text, height=40, corner_radius=8, anchor="w", fg_color="transparent", text_color="gray90", hover_color="#333", command=lambda: self.show_frame(view_name))
        b.grid(row=r, column=0, padx=10, pady=5, sticky="ew")
        self.btns[view_name] = b

    def show_frame(self, page_name):
        for name, btn in self.btns.items():
            btn.configure(fg_color="transparent", text_color="gray90")
        if page_name in self.btns:
            self.btns[page_name].configure(fg_color="#1f538d", text_color="white")
        frame = self.frames[page_name]
        frame.tkraise()
        if hasattr(frame, 'update_view'): frame.update_view()

    def show_info(self, t, m): CustomDialog(self, t, m, "info")
    def show_error(self, t, m): CustomDialog(self, t, m, "error")
    def ask_confirm(self, t, m, cb): CustomDialog(self, t, m, "confirm", cb)
    
    def show_view(self, view_name):
        """Muestra una vista específica sin pasar por el menú lateral."""
        view = self.frames.get(view_name)
        if view:
            view.tkraise()
            # Si la vista necesita actualizarse al abrir, lo hacemos
            if hasattr(view, 'update_view'):
                view.update_view()
        else:
            print(f"Error: La vista {view_name} no existe en self.frames")
if __name__ == "__main__":
    app = P2PManagerApp()
    app.mainloop()



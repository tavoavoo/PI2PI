import customtkinter as ctk
import threading
import time
import sqlite3
from datetime import datetime
from utils.ui_components import CustomDialog, ModernModal

# IMPORTS DE TUS MÓDULOS
from views.dashboard_modules.scrapers import DolaritoScraper
from views.dashboard_modules.logic import DashboardLogic
from views.dashboard_modules.historical_analyzer import HistoricalAnalyzer
from views.dashboard_modules.ccl_manager import CCLManager
from views.dashboard_modules.historical_widgets import HistoricalTimelineWidget

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # INICIALIZAR LOS MÓDULOS
        self.ccl_manager = CCLManager(self.controller.conn)
        self.scraper_engine = DolaritoScraper()
        self.logic_engine = DashboardLogic(self.controller.api_client, self.controller.cursor, self.controller.conn)
        self.historical_analyzer = HistoricalAnalyzer(self.controller.conn)
        self.ccl_status = "VIVO"

        # TABLA DE BASE DE DATOS
        try:
            self.controller.cursor.execute("""
                CREATE TABLE IF NOT EXISTS p2p_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT, hora TEXT, usdt_buy_p5 REAL, usdt_sell_p5 REAL,
                    mep REAL, ccl REAL, gap_ccl REAL,
                    ccl_tipo TEXT DEFAULT 'VIVO'
                )
            """)
            self.controller.conn.commit()
        except Exception as e:
            print(f"⚠️ Error verificando bóveda: {e}")

        self.historical_gaps = [] 
        self.is_scanning = False 
        self.datos_historicos_cache = []
        
        self.current_usdt_price = 0.0
        self.cached_mep = 0.0; self.cached_mep_pct = "0,00%"
        self.cached_blue = 0.0; self.cached_blue_pct = "0,00%"
        self.cached_ccl = 0.0; self.cached_ccl_pct = "0,00%"
        
        # --- HEADER ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(5,2))

        ctk.CTkLabel(
            header, 
            text="TABLERO DE MANDO", 
            font=("Arial", 22, "bold"), 
            text_color="#3498db"
        ).pack(side="left")

        # --- FASE 1: BARRA DE ESTADO (Compacta y Alineada) ---
        self.patrimonio_frame = ctk.CTkFrame(self, fg_color="transparent", height=45)
        self.patrimonio_frame.pack(fill="x", padx=20, pady=(0, 10)) # Un poco de aire abajo
        
        # Función auxiliar para crear celdas idénticas (Título + Valor)
        def crear_celda(parent, titulo, color_val):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(side="left", fill="y", expand=True) # expand=True distribuye el espacio
            
            ctk.CTkLabel(frame, text=titulo, font=("Arial", 13, "bold"), text_color="gray").pack(side="left", padx=(0, 5))
            lbl = ctk.CTkLabel(frame, text="---", font=("Arial", 16, "bold"), text_color=color_val)
            lbl.pack(side="left")
            return lbl

        def crear_separador(parent):
            sep = ctk.CTkFrame(parent, width=2, height=18, fg_color="#333")
            sep.pack(side="left", pady=10)

        # 1. LIQUIDEZ
        self.lbl_total_ars = crear_celda(self.patrimonio_frame, "LIQUIDEZ:", "#2cc985")
        crear_separador(self.patrimonio_frame)

        # 2. STOCK
        self.lbl_total_usdt = crear_celda(self.patrimonio_frame, "STOCK USDT:", "#e3a319")
        crear_separador(self.patrimonio_frame)

        # 3. PPP + BOTÓN (Celda especial)
        frame_ppp = ctk.CTkFrame(self.patrimonio_frame, fg_color="transparent")
        frame_ppp.pack(side="left", fill="y", expand=True)
        
        ctk.CTkLabel(frame_ppp, text="PPP:", font=("Arial", 13, "bold"), text_color="gray").pack(side="left", padx=(0, 5))
        self.lbl_ppp_radar = ctk.CTkLabel(frame_ppp, text="$ ---", font=("Arial", 15, "bold"), text_color="white")
        self.lbl_ppp_radar.pack(side="left")
        
        ctk.CTkButton(frame_ppp, text="⟳", width=25, height=25, fg_color="transparent", hover_color="#333", 
                      font=("Arial", 16), text_color="#c0392b", command=self.confirmar_reset_ppp).pack(side="left", padx=(5, 0))

        crear_separador(self.patrimonio_frame)

        # 4. PATRIMONIO
        self.lbl_equity = crear_celda(self.patrimonio_frame, "PATRIMONIO:", "#3498db")

        # --- FASE 2: CANJE MEP/CCL (Compacto) ---
        self.timeline_frame = ctk.CTkFrame(self, fg_color="#0f0f0f", border_width=1, border_color="#333")
        self.timeline_frame.pack(fill="x", padx=20, pady=(5,3))
        
        timeline_header = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        timeline_header.pack(fill="x", padx=10, pady=(5,2))
        ctk.CTkLabel(timeline_header, text="CANJE MEP/CCL", font=("Arial", 11, "bold"), text_color="#888").pack(side="left")
        
        timeline_grid = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        timeline_grid.pack(fill="x", padx=5, pady=(0,5))
        timeline_grid.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        self.market_widgets = [] 
        
        for i in range(5):
            f = ctk.CTkFrame(timeline_grid, fg_color="#1a1a1a", corner_radius=6, border_width=1, border_color="#333")
            f.grid(row=0, column=i, padx=3, pady=2, sticky="ew")
            lbl_dia = ctk.CTkLabel(f, text="---", font=("Arial", 11, "bold"), text_color="gray")
            lbl_dia.pack(pady=(4,0))
            lbl_gap = ctk.CTkLabel(f, text="---%", font=("Arial", 24, "bold"), text_color="white")
            lbl_gap.pack(pady=(0,4))
            self.market_widgets.append((f, lbl_dia, lbl_gap))

        # --- FASE 3: MERCADO (WIDGET EXTERNO) ---
        # Esto llama al diseño nuevo (Stats Izquierda | Cards Derecha)
        self.historical_timeline = HistoricalTimelineWidget(self, self.historical_analyzer)
        self.historical_timeline.pack(fill="x", padx=20, pady=(3,5))

        # --- FASE 4: GESTIÓN Y DECISIÓN ---
        self.radar_frame = ctk.CTkFrame(self, fg_color="#101010", border_width=1, border_color="#333")
        self.radar_frame.pack(fill="x", padx=20, pady=(5,8))
        
        top_ctrl = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        top_ctrl.pack(fill="x", padx=10, pady=(5,3))
        ctk.CTkLabel(top_ctrl, text="MATRIZ DE DECISIÓN", font=("Arial", 11, "bold"), text_color="#888").pack(side="left")
        self.lbl_scanner_status = ctk.CTkLabel(top_ctrl, text="Iniciando...", text_color="gray", font=("Consolas", 10))
        self.lbl_scanner_status.pack(side="right", padx=10)

        # Precios de mercado
        self.cards_frame = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=10, pady=(0,5))
        self.cards_frame.grid_columnconfigure((0,1,2,3,4), weight=1, uniform="x")
        
        self.card_blue = self.mk_dolarito_card(0, "BLUE")
        self.card_mep = self.mk_dolarito_card(1, "MEP")
        self.card_ccl = self.mk_dolarito_card(2, "CCL")
        self.card_p2p_bid = self.mk_dolarito_card(3, "MEJOR COMPRA")
        self.card_p2p_ask = self.mk_dolarito_card(4, "MEJOR VENTA")

        # CLIMA DE MERCADO
        self.clima_frame = ctk.CTkFrame(self.radar_frame, fg_color="#1a1a1a", corner_radius=8, border_width=2, border_color="#3498db")
        self.clima_frame.pack(fill="x", padx=10, pady=(5,8))
        
        clima_grid = ctk.CTkFrame(self.clima_frame, fg_color="transparent")
        clima_grid.pack(fill="x", padx=15, pady=10)
        clima_grid.grid_columnconfigure((0,1), weight=1)
        
        situacion_box = ctk.CTkFrame(clima_grid, fg_color="#0d0d0d", corner_radius=6)
        situacion_box.grid(row=0, column=0, padx=(0,5), sticky="nsew")
        ctk.CTkLabel(situacion_box, text="TU SITUACIÓN", font=("Arial", 10, "bold"), text_color="gray").pack(pady=(8,2))
        self.lbl_buy_action = ctk.CTkLabel(situacion_box, text="---", font=("Arial", 18, "bold"), text_color="white")
        self.lbl_buy_action.pack(pady=3)
        self.lbl_buy_detail = ctk.CTkLabel(situacion_box, text="...", font=("Arial", 11), text_color="gray")
        self.lbl_buy_detail.pack(pady=(0,8))
        
        mercado_box = ctk.CTkFrame(clima_grid, fg_color="#0d0d0d", corner_radius=6)
        mercado_box.grid(row=0, column=1, padx=(5,0), sticky="nsew")
        ctk.CTkLabel(mercado_box, text="CLIMA DE MERCADO", font=("Arial", 10, "bold"), text_color="gray").pack(pady=(8,2))
        self.lbl_sell_action = ctk.CTkLabel(mercado_box, text="---", font=("Arial", 20, "bold"), text_color="white")
        self.lbl_sell_action.pack(pady=3)
        self.lbl_sell_detail = ctk.CTkLabel(mercado_box, text="...", font=("Arial", 12), text_color="gray")
        self.lbl_sell_detail.pack(pady=(0,8))

        # --- FASE 5: EJECUCIÓN Y HERRAMIENTAS ---
        exec_frame = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        exec_frame.pack(fill="x", padx=10, pady=(0,8))
        exec_frame.grid_columnconfigure((0,1,2,3), weight=1)

        self.strat_a = self.mk_strategy_card_compact(exec_frame, 0, "MAKER/MAKER")
        self.strat_b = self.mk_strategy_card_compact(exec_frame, 1, "MAKER COMPRA")
        self.strat_c_buy = self.mk_strategy_card_compact(exec_frame, 2, "SIN SETUP")
        
        # VENTA vs PPP con botón BAN integrado
        venta_box = ctk.CTkFrame(exec_frame, fg_color="#1a1a1a", corner_radius=6, border_width=1, border_color="#333")
        venta_box.grid(row=0, column=3, padx=3, sticky="nsew")
        
        venta_header = ctk.CTkFrame(venta_box, fg_color="transparent")
        venta_header.pack(fill="x", padx=5, pady=(8,2)) # Mismo padding que las otras
        
        # 1. Botón a la derecha (Primero para que se ancle al borde)
        ctk.CTkButton(
            venta_header,
            text="🚫",
            width=28,
            height=22,
            font=("Arial", 14),
            fg_color="#c0392b",
            hover_color="#922b21",
            command=self.abrir_blacklist_manager
        ).pack(side="right")
        
        # 2. Título CENTRADO (Con expand=True ocupa el centro)
        ctk.CTkLabel(
            venta_header, 
            text="VENTA vs PPP", 
            font=("Arial", 11, "bold"), # Aumentado a 11
            text_color="gray"
        ).pack(side="left", expand=True) 
        
        # Valor aumentado a 20
        self.strat_c_sell = ctk.CTkLabel(venta_box, text="--- %", font=("Arial", 20, "bold"), text_color="white")
        self.strat_c_sell.pack(pady=(0,8))

        # CALCULADORA (AUMENTADA)
        calc_frame = ctk.CTkFrame(self.radar_frame, fg_color="#121212", border_width=1, border_color="#333", corner_radius=6)
        calc_frame.pack(fill="x", padx=10, pady=(0,8))
        
        # Título más grande
        ctk.CTkLabel(calc_frame, text="SIMULADOR DE RIESGO", font=("Arial", 12, "bold"), text_color="gray").pack(pady=(8,5))
        
        calc_inner = ctk.CTkFrame(calc_frame, fg_color="transparent")
        calc_inner.pack(pady=(0,8))

        # COMPRA
        ctk.CTkLabel(calc_inner, text="COMPRA", font=("Arial", 12, "bold"), text_color="#2ecc71").pack(side="left", padx=5)
        # Input más grande (font 14) y un poco más ancho (100)
        self.entry_sim_buy = ctk.CTkEntry(calc_inner, width=100, justify="center", fg_color="#2b2b2b", border_width=0, font=("Arial", 14, "bold"))
        self.entry_sim_buy.pack(side="left", padx=2)
        self.entry_sim_buy.bind("<KeyRelease>", self.calcular_simulacion)
        
        self.sim_buy_mode = ctk.CTkOptionMenu(calc_inner, values=["Maker", "Taker"], width=75, fg_color="#333", button_color="#444", command=self.calcular_simulacion)
        self.sim_buy_mode.set("Maker")
        self.sim_buy_mode.pack(side="left", padx=2)

        # FLECHA
        ctk.CTkLabel(calc_inner, text="→", font=("Arial", 20), text_color="#555").pack(side="left", padx=10)

        # VENTA
        ctk.CTkLabel(calc_inner, text="VENTA", font=("Arial", 12, "bold"), text_color="#e74c3c").pack(side="left", padx=5)
        # Input más grande
        self.entry_sim_sell = ctk.CTkEntry(calc_inner, width=100, justify="center", fg_color="#2b2b2b", border_width=0, font=("Arial", 14, "bold"))
        self.entry_sim_sell.pack(side="left", padx=2)
        self.entry_sim_sell.bind("<KeyRelease>", self.calcular_simulacion)
        
        self.sim_sell_mode = ctk.CTkOptionMenu(calc_inner, values=["Maker", "Taker"], width=75, fg_color="#333", button_color="#444", command=self.calcular_simulacion)
        self.sim_sell_mode.set("Maker")
        self.sim_sell_mode.pack(side="left", padx=2)

        # IGUAL Y RESULTADO
        ctk.CTkLabel(calc_inner, text="=", font=("Arial", 20), text_color="#555").pack(side="left", padx=10)
        # Resultado GIGANTE (24)
        self.lbl_sim_result = ctk.CTkLabel(calc_inner, text="--- %", font=("Arial", 24, "bold"), text_color="gray")
        self.lbl_sim_result.pack(side="left", padx=5)

        # --- FOOTER ---
        self.f_sesion = ctk.CTkFrame(self, fg_color="#2b2b2b", border_color="#e3a319", border_width=2, corner_radius=8)
        self.f_sesion.pack(fill="x", padx=20, pady=(5, 20)) # Un poco más de aire abajo del todo
        
        sesion_content = ctk.CTkFrame(self.f_sesion, fg_color="transparent")
        sesion_content.pack(pady=10) # Más padding interno
        
        # Título
        ctk.CTkLabel(
            sesion_content, 
            text="TURNO ACTUAL:", 
            font=("Arial", 13, "bold"), # Aumentado a 14
            text_color="#e3a319"
        ).pack(side="left", padx=(10, 10))
        
        # Valor en Pesos (GIGANTE)
        self.lbl_gan_sesion = ctk.CTkLabel(
            sesion_content, 
            text="---", 
            font=("Arial", 16, "bold") # Aumentado a 30
        )
        self.lbl_gan_sesion.pack(side="left", padx=5)
        
        # Valor en USDT
        self.lbl_gan_sesion_usdt = ctk.CTkLabel(
            sesion_content, 
            text="--- USDT", 
            font=("Arial", 14, "bold"), # Aumentado a 16 Bold
            text_color="#aaaaaa"
        )
        self.lbl_gan_sesion_usdt.pack(side="left", padx=(10, 10))
        
        # --- INICIO MOTORES ---
        self.after(1000, self.auto_scan_loop)
        threading.Thread(target=self.cargar_historia_combinada, daemon=True).start()
        threading.Thread(target=self.background_dolarito_updater, daemon=True).start()

    def render_historia_inicial(self):
        if not self.datos_historicos_cache:
            return

        for i, dato in enumerate(self.datos_historicos_cache):
            if i >= 4: break 
            
            frame, lbl_dia, lbl_gap = self.market_widgets[i]
            
            dia_texto = dato["fecha"].split(',')[0].upper()[:3]
            gap_val = dato["gap"]
            
            color = "#3498db"
            
            if gap_val > 2.0: 
                color = "#e74c3c"
            elif gap_val < 0.0: 
                color = "#2ecc71"
            
            lbl_dia.configure(text=dia_texto)
            lbl_gap.configure(text=f"{gap_val:.2f}%", text_color=color)

    def background_dolarito_updater(self):
        while True:
            datos_precios = self.scraper_engine.obtener_precios_vivo()
            if datos_precios:
                self.cached_blue, self.cached_blue_pct = datos_precios["blue"]
                self.cached_mep, self.cached_mep_pct = datos_precios["mep"]
                # ✅ CCL TRATADO IGUAL QUE LOS DEMÁS
                self.cached_ccl, self.cached_ccl_pct = datos_precios["ccl"]
            
            # ✅ SIEMPRE VIVO (Sin validación de horario)
            self.ccl_status = "VIVO"
            
            time.sleep(60)

    def cargar_historia_combinada(self):
        print("📊 Iniciando carga de historia de Dolarito...")
        
        try:
            historia = self.scraper_engine.cargar_historia_combinada()
            
            if historia:
                self.historical_gaps = historia
                print(f"✅ Historia cargada: {len(historia)} registros")
                self.after(0, lambda: self.actualizar_timeline_viejo(historia))
            else:
                print("⚠️ No se pudo cargar historia de Dolarito")
                self.historical_gaps = []
                
        except Exception as e:
            print(f"❌ Error cargando historia: {e}")
            self.historical_gaps = []

    def actualizar_timeline_viejo(self, historia):
        try:
            for i, gap_data in enumerate(historia[:4]):
                if i >= len(self.market_widgets) - 1:
                    break
                
                frame_hist, lbl_dia, lbl_gap = self.market_widgets[i]
                
                dia_texto = gap_data.get('fecha', '---')
                gap_val = gap_data.get('gap', 0.0)
                
                color = "#3498db"
                if gap_val > 4.5:
                    color = "#e74c3c"
                elif gap_val < 2.5:
                    color = "#2ecc71"
                
                try:
                    dia_semana = dia_texto.split()[0][:3].upper()
                except:
                    dia_semana = "---"
                
                lbl_dia.configure(text=dia_semana)
                lbl_gap.configure(text=f"{gap_val:.2f}%", text_color=color)
                
        except Exception as e:
            print(f"Error actualizando timeline viejo: {e}")
            
    def auto_scan_loop(self):
        if not self.is_scanning: 
            self.lanzar_escaneo()
        
        try: 
            self.update_stats_footer()
            self.actualizar_tablero_estrategico()
            
            # --- CAMBIO AQUÍ: Actualizar el widget nuevo ---
            if hasattr(self, 'historical_timeline'):
                try:
                    self.historical_timeline.update_data()
                except Exception as e:
                    print(f"⚠️ Error widget histórico: {e}")
            # -----------------------------------------------
            
        except Exception as e: 
            print(f"⚠️ Error en loop visual: {e}") 
        
        self.after(5000, self.auto_scan_loop)

    def lanzar_escaneo(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.lbl_scanner_status.configure(text="⚡ Analizando...", text_color="#f39c12")
        self.resultado_escaneo = None 
        
        self.controller.cursor.execute("SELECT value FROM config WHERE key='api_key'")
        ak_res = self.controller.cursor.fetchone(); ak = ak_res[0] if ak_res else None
        self.controller.cursor.execute("SELECT value FROM config WHERE key='api_secret'")
        ask_res = self.controller.cursor.fetchone(); ask = ask_res[0] if ask_res else None
        self.controller.cursor.execute("SELECT value FROM config WHERE key='maker_fee'")
        res_mf = self.controller.cursor.fetchone(); maker_fee = float(res_mf[0]) if res_mf else 0.0020
        self.controller.cursor.execute("SELECT value FROM config WHERE key='taker_fee'")
        res_tf = self.controller.cursor.fetchone(); taker_fee = float(res_tf[0]) if res_tf else 0.0007
        
        ppp_ars = self.controller.obtener_ppp("ARS")
        saldo_ars = self.controller.obtener_saldo_total_ars()
        stock_usdt = self.controller.STOCK_USDT
        saldo_usd_fiat = 0.0 

        mep_ref = self.cached_mep; blue_ref = self.cached_blue; ccl_ref = self.cached_ccl
        mep_pct = self.cached_mep_pct; blue_pct = self.cached_blue_pct; ccl_pct = self.cached_ccl_pct
        
        ccl_state = self.ccl_status 

        threading.Thread(target=self._wrapper_logic, args=(ak, ask, maker_fee, taker_fee, ppp_ars, saldo_ars, stock_usdt, saldo_usd_fiat, mep_ref, blue_ref, ccl_ref, mep_pct, blue_pct, ccl_pct, ccl_state), daemon=True).start()
        
        self.after(100, self.verificar_resultado_escaneo)

    def _wrapper_logic(self, *args):
        resultado = self.logic_engine.ejecutar_escaneo(*args)
        self.resultado_escaneo = resultado

    def verificar_resultado_escaneo(self):
        if self.resultado_escaneo is None:
            self.after(100, self.verificar_resultado_escaneo)
            return
        resultado = self.resultado_escaneo
        self.is_scanning = False 
        
        if resultado["status"] == "success":
            args = resultado["data"]
            self.render_escaneo(*args)
        else:
            msg = resultado["msg"]
            self.lbl_scanner_status.configure(text=f"Error: {msg[:15]}", text_color="red")

    def render_escaneo(self, blue, mep, ccl, market_ask_1, market_ask_p2p5, market_bid_1, market_bid_p2p5, 
                            real_stock, gap_vivo, maker_fee, taker_fee, ppp, saldo_ars, stock_usdt, 
                            saldo_usd_fiat, mep_pct, blue_pct, ccl_pct, gap_ccl, canje_vivo, 
                            profit_c_buy, profit_c_sell, ccl_tipo):
            
            hora = datetime.now().strftime('%H:%M:%S')
            self.lbl_scanner_status.configure(text=f"⚡ ACTIVO: {hora}", text_color="#2ecc71")
            self.after(1000, lambda: self.lbl_scanner_status.configure(text_color="gray"))
            
            self.current_usdt_price = market_ask_1

            # PRECIOS
            self.update_price_card(self.card_blue, blue, blue_pct)
            self.update_price_card(self.card_mep, mep, mep_pct)
            self.update_price_card(self.card_ccl, ccl, ccl_pct)

            self.update_price_card(self.card_p2p_ask, market_bid_p2p5, None) 
            self.update_price_card(self.card_p2p_bid, market_ask_p2p5, None)
            
            self.lbl_ppp_radar.configure(text=f"$ {ppp:,.2f}")
            self.lbl_total_ars.configure(text=f"$ {saldo_ars:,.0f}")
            self.lbl_total_usdt.configure(text=f"{stock_usdt:,.2f}")
            
            # CUADRO VIVO
            frame_vivo, lbl_dia_vivo, lbl_gap_vivo = self.market_widgets[-1]
            
            frame_vivo.configure(fg_color="#1a1a1a", border_color="#3498db", border_width=2)
            
            color_vivo = "white"
            if canje_vivo > 5.00: color_vivo = "#e74c3c"
            elif canje_vivo < 2.00: color_vivo = "#2ecc71"
            
            lbl_dia_vivo.configure(text="CANJE", text_color="#3498db")
            lbl_gap_vivo.configure(text=f"{canje_vivo:.2f}%", text_color=color_vivo)
            
            # DECISIÓN
            if saldo_ars > 50000:
                mejor_entrada = min(market_bid_1, market_ask_1)
                modo_entrada = "(TAKER)" if market_ask_1 < market_bid_1 else "(MAKER)"
                if ppp == 0: txt_act, col_act, det_act = f"INICIAR {modo_entrada}", "#27ae60", "Inicia Posición."
                elif mejor_entrada < ppp: txt_act, col_act, det_act = "🟢 ACUMULAR", "#27ae60", f"Bajas PPP ({modo_entrada})."
                elif mejor_entrada < ppp * 1.01: txt_act, col_act, det_act = "🔵 SUMAR VOLUMEN", "#2980b9", "Mantienes PPP."
                else: txt_act, col_act, det_act = "ESPERAR", "gray", f"Mercado caro (${mejor_entrada:.0f})."
            else: txt_act, col_act, det_act = "SIN LIQUIDEZ", "#333", "Carga ARS."
            self.lbl_buy_action.configure(text=txt_act, text_color=col_act)
            self.lbl_buy_detail.configure(text=det_act)

            # CLIMA
            desvio = gap_vivo - 3.0
            clima_txt = "Estable"; color_clima = "#3498db"
            if gap_vivo > 0:
                if desvio > 0.5: clima_txt = "Eufórico (Vender)"; color_clima = "#e74c3c"
                elif desvio < -0.5: clima_txt = "Deprimido (Comprar)"; color_clima = "#2ecc71"
            if stock_usdt > 10:
                roi = (((market_ask_1 * (1 - maker_fee)) / ppp) - 1) * 100 if ppp > 0 else 0.0
                if roi > 0.5: txt_sell, col_sell, det_sell = f"🟢 VENDER (+{roi:.1f}%)", "#2ecc71", f"Mercado {clima_txt}."
                elif roi > -0.5: txt_sell, col_sell, det_sell = f"🔵 ROTAR ({roi:.1f}%)", "#2980b9", "Sales hecho."
                else: txt_sell, col_sell, det_sell = f"🛑 HOLDEAR ({roi:.1f}%)", "#c0392b", f"Clima: {clima_txt}"
            else: txt_sell, col_sell, det_sell = f"CLIMA: {clima_txt}", color_clima, f"Canje CCL: {gap_ccl:+.2f}%"
            self.lbl_sell_action.configure(text=txt_sell, text_color=col_sell)
            self.lbl_sell_detail.configure(text=det_sell)

            # ESTRATEGIAS
            val_ask_1 = float(market_ask_1) if market_ask_1 else 0.0
            val_ask_15 = float(market_ask_p2p5) if market_ask_p2p5 else 0.0
            val_bid_1 = float(market_bid_1) if market_bid_1 else 0.0
            val_bid_15 = float(market_bid_p2p5) if market_bid_p2p5 else 0.0

            if val_bid_15 > 0 and val_ask_15 > 0:
                profit_a = ((val_ask_15 * (1 - maker_fee)) / (val_bid_15 * (1 + maker_fee)) - 1) * 100
                skew_p2 = 0.0
                if val_ask_1 > 0 and val_ask_15 > 0: skew_p2 = ((val_ask_15 / val_ask_1) - 1) * 100
                
                texto_final = f"Spr: {profit_a:+.2f}% | Sk: {skew_p2:.2f}%"
                col_a = "#e74c3c"
                if profit_a > 1.5 and skew_p2 < 2.0: col_a = "#2ecc71"
                elif profit_a > 0: col_a = "#f39c12"
                self.strat_a.configure(text=texto_final, text_color=col_a)
            else:
                self.strat_a.configure(text="S/D", text_color="gray")

            if val_bid_1 > 0 and val_bid_15 > 0:
                dist_buy = (1 - (val_bid_15 / val_bid_1)) * 100
                text_b = f"Brecha: {dist_buy:.2f}%"
                col_b = "#3498db"
                if dist_buy > 0.8: col_b = "#2ecc71"
                elif dist_buy < 0.1: col_b = "#e74c3c"
                self.strat_b.configure(text=text_b, text_color=col_b)
            else:
                self.strat_b.configure(text="S/D", text_color="gray")

            UMBRAL_MIN = 0.3
            if profit_c_buy >= UMBRAL_MIN:
                tipo_buy = "💎 VIABLE"; color_buy = "#2ecc71"
            else:
                tipo_buy = "SIN SETUP"; color_buy = "gray"; profit_c_buy = max(profit_c_buy, -5.0)

            self.update_strat_card(self.strat_c_buy, profit_c_buy, "Mín: 0.3%")

            if profit_c_sell == -999.0: tipo_sell = "SIN PPP"; color_sell = "gray"; profit_c_sell = 0.0
            elif profit_c_sell >= 1.0: tipo_sell = "💎 VIABLE"; color_sell = "#2ecc71"
            elif profit_c_sell >= 0.3: tipo_sell = "⚠️ MARGINAL"; color_sell = "#f39c12"
            elif profit_c_sell >= 0.0: tipo_sell = "🔵 NEUTRO"; color_sell = "#3498db"
            else: tipo_sell = "🛑 HOLDEAR"; color_sell = "#e74c3c"; profit_c_sell = max(profit_c_sell, -5.0)

            self.update_strat_card(self.strat_c_sell, profit_c_sell, "Mín: 0.3%")
            
            self.lbl_equity.configure(text=f"US$ {(saldo_ars / market_ask_1 + stock_usdt):,.2f}" if market_ask_1 else "---")
            self.update_stats_footer()

    def update_stats_footer(self):
        try:
            ganancia_turno = self.controller.calc_ganancia_sesion_ars(None, "ARS")
            color = "#2ecc71" if ganancia_turno >= 0 else "#e74c3c"
            signo = "+" if ganancia_turno >= 0 else ""
            self.lbl_gan_sesion.configure(text=f"$ {ganancia_turno:,.0f}", text_color=color)
            precio_ref = self.current_usdt_price
            if precio_ref > 0:
                gan_usdt = ganancia_turno / precio_ref
                self.lbl_gan_sesion_usdt.configure(text=f"{signo}{gan_usdt:.2f} USDT", text_color="gray")
            else: self.lbl_gan_sesion_usdt.configure(text="--- USDT")
        except: self.lbl_gan_sesion.configure(text="---")

    def calcular_simulacion(self, event=None):
        try:
            def limpiar_monto(texto):
                if not texto: return 0.0
                try: return float(texto.strip().replace(',', '.'))
                except: return 0.0
            precio_salida = limpiar_monto(self.entry_sim_buy.get())
            precio_entrada = limpiar_monto(self.entry_sim_sell.get())
            if precio_salida <= 0 or precio_entrada <= 0:
                self.lbl_sim_result.configure(text="--- %", text_color="gray"); return
            try:
                self.controller.cursor.execute("SELECT value FROM config WHERE key='maker_fee'")
                m_fee = float(self.controller.cursor.fetchone()[0])
                self.controller.cursor.execute("SELECT value FROM config WHERE key='taker_fee'")
                t_fee = float(self.controller.cursor.fetchone()[0])
            except: m_fee = 0.0020; t_fee = 0.0007
            fee_in = t_fee if self.sim_sell_mode.get() == "Taker" else m_fee
            fee_out = t_fee if self.sim_buy_mode.get() == "Taker" else m_fee
            roi = ((precio_salida * (1-fee_out)) / (precio_entrada * (1+fee_in)) - 1) * 100
            if roi > 0: self.lbl_sim_result.configure(text=f"WIN: +{roi:.2f}%", text_color="#2ecc71")
            else: self.lbl_sim_result.configure(text=f"LOSS: {roi:.2f}%", text_color="#e74c3c")
        except: pass

    def mk_dolarito_card(self, col, title):
        card = ctk.CTkFrame(self.cards_frame, fg_color="#252525", corner_radius=6, border_width=1, border_color="#333")
        card.grid(row=0, column=col, padx=3, sticky="ew")
        ctk.CTkLabel(card, text=title, font=("Arial", 10, "bold"), text_color="#aaa").pack(pady=(6,0))
        lbl_val = ctk.CTkLabel(card, text="---", font=("Arial", 24, "bold"), text_color="white"); lbl_val.pack(pady=(2,0))
        pill = ctk.CTkFrame(card, corner_radius=10, height=20, fg_color="#252525"); pill.pack(pady=(2,6))
        lbl_pct = ctk.CTkLabel(pill, text="---", font=("Arial", 10, "bold"), text_color="white"); lbl_pct.pack(padx=8, pady=2)
        card.lbl_val = lbl_val; card.lbl_pct = lbl_pct; card.pill = pill
        return card

    def update_price_card(self, card_widget, precio, pct_str):
        card_widget.lbl_val.configure(text=f"${precio:,.2f}" if precio else "---")
        if pct_str and pct_str != "0.0%" and pct_str != "---":
            is_neg = "-" in pct_str
            card_widget.pill.configure(fg_color="#b91c1c" if is_neg else "#15803d")
            card_widget.lbl_pct.configure(text=f"{'▼' if is_neg else '▲'} {pct_str}")
        else:
            card_widget.pill.configure(fg_color="transparent"); card_widget.lbl_pct.configure(text="")

    def mk_strategy_card_compact(self, parent, col, title):
        card = ctk.CTkFrame(parent, fg_color="#1a1a1a", corner_radius=6, border_width=1, border_color="#333")
        card.grid(row=0, column=col, padx=3, sticky="nsew")
        
        # Título: Aumentado a 11
        ctk.CTkLabel(card, text=title, font=("Arial", 11, "bold"), text_color="gray").pack(pady=(8,2))
        
        # Valor: Aumentado a 20 (Más impacto)
        lbl_pct = ctk.CTkLabel(card, text="--- %", font=("Arial", 20, "bold"), text_color="white")
        lbl_pct.pack(pady=(0,8))
        return lbl_pct
    
    def update_strat_card(self, lbl, val, txt_extra):
        color = "#e74c3c" if val < 0 else "#2ecc71" if val > 0.5 else "#f1c40f"
        lbl.configure(text=f"{val:+.2f}%", text_color=color)
    
    def update_radar_labels(self, val): self.update_stats_footer()
    
    def confirmar_reset_ppp(self): 
        def do_reset(): self.controller.reiniciar_ppp(); self.lbl_ppp_radar.configure(text=f"PPP: $ 0.00")
        self.controller.ask_confirm("Reiniciar PPP", "¿Archivar compras y volver a 0?", do_reset)
    
    def update_view(self): self.update_stats_footer()

    def actualizar_tablero_estrategico(self):
        historia = getattr(self, "datos_historicos_cache", [])
        if not historia: historia = getattr(self, "historical_gaps", [])
        vivo = getattr(self.scraper_engine, "cache_vivo", None)

        try: estrategia = self.scraper_engine.analizar_mercado(historia, vivo)
        except: return

        if "CARGANDO" in estrategia.get('accion', '') and self.lbl_sell_action.cget("text") != "---": return 

        self.lbl_sell_action.configure(text=estrategia.get('accion', '---'))
        self.lbl_sell_detail.configure(text=estrategia.get('subtexto', '...'))
        
        cols = {"compra": "#2ecc71", "venta": "#e74c3c", "neutral": "#3498db"}
        self.lbl_sell_action.configure(text_color=cols.get(estrategia.get('tipo'), "white"))

        rec = estrategia.get('rec_contable', '---')
        self.lbl_buy_action.configure(text=rec)
        if "SUMAR" in rec: self.lbl_buy_action.configure(text_color="#2ecc71")
        elif "VENDER" in rec: self.lbl_buy_action.configure(text_color="#e74c3c")
        else: self.lbl_buy_action.configure(text_color="#3498db")
                
    def abrir_blacklist_manager(self):
        modal = ModernModal(self.controller, "🛡️ GESTOR DE BLACKLIST", width=600, height=500)
        
        add_frame = ctk.CTkFrame(modal.content_frame, fg_color="#1a1a1a", corner_radius=8)
        add_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(add_frame, text="BANEAR USUARIO:", font=("Arial", 12, "bold")).pack(anchor="w", padx=15, pady=(10,5))
        
        input_frame = ctk.CTkFrame(add_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0,10))
        
        entry_nick = ctk.CTkEntry(input_frame, placeholder_text="Escribe el nickname exacto...", width=300)
        entry_nick.pack(side="left", padx=(0,10))
        
        entry_motivo = ctk.CTkEntry(input_frame, placeholder_text="Motivo (opcional)", width=150)
        entry_motivo.pack(side="left", padx=(0,10))
        
        def agregar_a_blacklist():
            nick = entry_nick.get().strip()
            if not nick:
                self.controller.show_error("Error", "Debes escribir un nickname")
                return
            
            motivo = entry_motivo.get().strip() or "Sin motivo especificado"
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                self.controller.cursor.execute(
                    "INSERT INTO p2p_blacklist (nickname, fecha_baneo, motivo) VALUES (?, ?, ?)",
                    (nick, fecha, motivo)
                )
                self.controller.conn.commit()
                entry_nick.delete(0, "end")
                entry_motivo.delete(0, "end")
                actualizar_lista()
                self.controller.show_info("Baneado", f"'{nick}' añadido a la blacklist")
            except sqlite3.IntegrityError:
                self.controller.show_error("Duplicado", f"'{nick}' ya está en la blacklist")
            except Exception as e:
                self.controller.show_error("Error", str(e))
        
        ctk.CTkButton(
            input_frame, 
            text="🚫 BANEAR", 
            fg_color="#e74c3c", 
            hover_color="#c0392b",
            command=agregar_a_blacklist
        ).pack(side="left")
        
        ctk.CTkLabel(modal.content_frame, text="USUARIOS BANEADOS:", font=("Arial", 11, "bold"), text_color="gray").pack(anchor="w", padx=10, pady=(20,5))
        
        list_frame = ctk.CTkScrollableFrame(modal.content_frame, fg_color="#0a0a0a", height=250)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        def actualizar_lista():
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            self.controller.cursor.execute("SELECT id, nickname, fecha_baneo, motivo FROM p2p_blacklist ORDER BY fecha_baneo DESC")
            baneados = self.controller.cursor.fetchall()
            
            if not baneados:
                ctk.CTkLabel(list_frame, text="No hay usuarios baneados", text_color="gray").pack(pady=20)
                return
            
            for ban_id, nick, fecha, motivo in baneados:
                row = ctk.CTkFrame(list_frame, fg_color="#1a1a1a", corner_radius=6)
                row.pack(fill="x", pady=3, padx=5)
                
                info_box = ctk.CTkFrame(row, fg_color="transparent")
                info_box.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                
                ctk.CTkLabel(info_box, text=nick, font=("Arial", 13, "bold"), text_color="#e74c3c").pack(anchor="w")
                ctk.CTkLabel(info_box, text=f"Fecha: {fecha} | {motivo}", font=("Arial", 9), text_color="gray").pack(anchor="w")
                
                def eliminar_ban(ban_id=ban_id, nick=nick):
                    try:
                        self.controller.cursor.execute("DELETE FROM p2p_blacklist WHERE id=?", (ban_id,))
                        self.controller.conn.commit()
                        actualizar_lista()
                        self.controller.show_info("Desbaneado", f"'{nick}' eliminado de la blacklist")
                    except Exception as e:
                        self.controller.show_error("Error", str(e))
                
                ctk.CTkButton(
                    row, 
                    text="✓ DESBANEAR", 
                    width=100, 
                    fg_color="#27ae60",
                    hover_color="#229954",
                    command=eliminar_ban
                ).pack(side="right", padx=10)
        
        actualizar_lista()
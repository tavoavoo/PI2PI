import customtkinter as ctk
import threading
import time
import sqlite3
from datetime import datetime
from utils.ui_components import CustomDialog, ModernModal
# IMPORTS DE TUS NUEVOS MÓDULOS
from views.dashboard_modules.scrapers import DolaritoScraper
from views.dashboard_modules.logic import DashboardLogic
from views.dashboard_modules.historical_analyzer import HistoricalAnalyzer
from views.dashboard_modules.historical_widgets import HistoricalTimelineWidget

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # INICIALIZAR LOS MÓDULOS
        self.scraper_engine = DolaritoScraper()
        self.logic_engine = DashboardLogic(self.controller.api_client, self.controller.cursor, self.controller.conn)
        self.historical_analyzer = HistoricalAnalyzer(self.controller.conn)

        # TABLA DE BASE DE DATOS (Mantenida por seguridad)
        try:
            self.controller.cursor.execute("""
                CREATE TABLE IF NOT EXISTS p2p_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT, hora TEXT, usdt_buy_p5 REAL, usdt_sell_p5 REAL,
                    mep REAL, ccl REAL, gap_ccl REAL
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
        header.pack(fill="x", padx=20, pady=5)

        # Título
        ctk.CTkLabel(
            header, 
            text="TABLERO DE MANDO (V12.0 - Persistente Modular)", 
            font=("Arial", 22, "bold"), 
            text_color="#3498db"
        ).pack(side="left")

        # Contenedor de botones (CREAR PRIMERO)
        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        # Selector de moneda
        self.radar_currency = ctk.CTkOptionMenu(
            btn_box, 
            values=["ARS", "PEN"], 
            width=70, 
            command=self.update_radar_labels
        )
        self.radar_currency.set("ARS")
        self.radar_currency.pack(side="left", padx=5)

        # Botón de Blacklist
        ctk.CTkButton(
            btn_box, 
            text="🚫 BLACKLIST", 
            width=100, 
            fg_color="#c0392b", 
            hover_color="#922b21",
            command=self.abrir_blacklist_manager
        ).pack(side="left", padx=5)

        # --- PATRIMONIO ---
        self.patrimonio_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", border_width=1, border_color="#333")
        self.patrimonio_frame.pack(fill="x", padx=20, pady=(10, 5))
        self.patrimonio_frame.grid_columnconfigure((0,1,2), weight=1)
        
        self.lbl_total_ars = self.mk_stat_card(self.patrimonio_frame, 0, "TOTAL ARS", "$ ---", "#2cc985")
        self.lbl_total_usdt = self.mk_stat_card(self.patrimonio_frame, 1, "STOCK USDT", "---", "#e3a319")
        self.lbl_equity = self.mk_stat_card(self.patrimonio_frame, 2, "PATRIMONIO TOTAL", "US$ ---", "#3498db")

        # --- LÍNEA DE TIEMPO CLÁSICA (Scraper Dolarito + Turno en Vivo) ---
        # ⚠️ MANTENER ESTO - Se usa en render_escaneo() para mostrar el turno actual
        self.timeline_frame = ctk.CTkFrame(self, fg_color="#0f0f0f", border_width=1, border_color="#333")
        self.timeline_frame.pack(fill="x", padx=20, pady=5)
        self.timeline_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        self.market_widgets = []  # ⚠️ NO BORRAR - Se usa en render_escaneo()
        
        for i in range(5):
            f = ctk.CTkFrame(self.timeline_frame, fg_color="#1a1a1a", corner_radius=6, border_width=1, border_color="#333")
            f.grid(row=0, column=i, padx=4, pady=5, sticky="ew")
            lbl_dia = ctk.CTkLabel(f, text="---", font=("Arial", 11, "bold"), text_color="gray")
            lbl_dia.pack(pady=(5,0))
            lbl_gap = ctk.CTkLabel(f, text="---%", font=("Arial", 26, "bold"), text_color="white")
            lbl_gap.pack(pady=(0,5))
            self.market_widgets.append((f, lbl_dia, lbl_gap))
        
        # Separador visual
        separator = ctk.CTkFrame(self, height=2, fg_color="#333")
        separator.pack(fill="x", padx=40, pady=10)
        
        # --- LÍNEA DE TIEMPO NUEVA (Histórico Real de P2P BD) ---
        self.historical_timeline = HistoricalTimelineWidget(self, self.historical_analyzer)
        self.historical_timeline.pack(fill="x", padx=20, pady=5)

        # --- INICIO MOTORES ---
        self.after(1000, self.auto_scan_loop)
        threading.Thread(target=self.cargar_historia_combinada, daemon=True).start()
        threading.Thread(target=self.background_dolarito_updater, daemon=True).start()

        # --- RADAR ---
        self.radar_frame = ctk.CTkFrame(self, fg_color="#101010", border_width=1, border_color="#333")
        self.radar_frame.pack(fill="x", padx=20, pady=10)
        
        top_ctrl = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        top_ctrl.pack(fill="x", padx=10, pady=(5,5))
        ctk.CTkLabel(top_ctrl, text="MATRIZ DE PROBABILIDAD", font=("Arial", 14, "bold"), text_color="#888").pack(side="left")
        self.lbl_scanner_status = ctk.CTkLabel(top_ctrl, text="Iniciando...", text_color="gray", font=("Consolas", 11))
        self.lbl_scanner_status.pack(side="right", padx=10)

        self.cards_frame = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=10, pady=5)
        self.cards_frame.grid_columnconfigure((0,1,2,3,4), weight=1, uniform="x")
        
        self.card_blue = self.mk_dolarito_card(0, "BLUE")
        self.card_mep = self.mk_dolarito_card(1, "MEP")
        self.card_ccl = self.mk_dolarito_card(2, "CCL")
        self.card_p2p_ask = self.mk_dolarito_card(4, "MEJOR VENTA")  # 🔄 Columna 4 (derecha)
        self.card_p2p_bid = self.mk_dolarito_card(3, "MEJOR COMPRA") # 🔄 Columna 3 (izquierda)

        # --- DECISIÓN ---
        self.decision_frame = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        self.decision_frame.pack(fill="x", padx=10, pady=10)
        self.decision_frame.grid_columnconfigure((0,1), weight=1, uniform="decision")

        self.buy_signal_frame = ctk.CTkFrame(self.decision_frame, fg_color="#1a1a1a", corner_radius=8, border_width=1, border_color="#333")
        self.buy_signal_frame.grid(row=0, column=0, padx=(0,5), sticky="nsew")
        ctk.CTkLabel(self.buy_signal_frame, text="TU SITUACIÓN (CONTABLE)", font=("Arial", 11, "bold"), text_color="gray").pack(pady=(10,5))
        self.lbl_buy_action = ctk.CTkLabel(self.buy_signal_frame, text="---", font=("Arial", 18, "bold"), text_color="white")
        self.lbl_buy_action.pack(pady=5)
        self.lbl_buy_detail = ctk.CTkLabel(self.buy_signal_frame, text="...", font=("Arial", 12), text_color="gray")
        self.lbl_buy_detail.pack(pady=(0,10))

        self.sell_signal_frame = ctk.CTkFrame(self.decision_frame, fg_color="#1a1a1a", corner_radius=8, border_width=1, border_color="#333")
        self.sell_signal_frame.grid(row=0, column=1, padx=(5,0), sticky="nsew")
        ctk.CTkLabel(self.sell_signal_frame, text="CLIMA DE MERCADO (CANJE)", font=("Arial", 11, "bold"), text_color="gray").pack(pady=(10,5))
        self.lbl_sell_action = ctk.CTkLabel(self.sell_signal_frame, text="---", font=("Arial", 18, "bold"), text_color="white")
        self.lbl_sell_action.pack(pady=5)
        self.lbl_sell_detail = ctk.CTkLabel(self.sell_signal_frame, text="...", font=("Arial", 12), text_color="gray")
        self.lbl_sell_detail.pack(pady=(0,10))
        
        # --- ÁREA PPP ---
        self.ppp_container = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        self.ppp_container.pack(pady=(5, 10))
        self.lbl_ppp_radar = ctk.CTkLabel(self.ppp_container, text="PPP: $ ---", font=("Arial", 16, "bold"), text_color="white")
        self.lbl_ppp_radar.pack(side="left", padx=(0, 15))
        ctk.CTkButton(self.ppp_container, text="🔄 RESET CICLO", width=100, height=28, fg_color="#444", hover_color="#c0392b", command=self.confirmar_reset_ppp).pack(side="left")

        # --- MATRIZ ---
        self.matrix_frame = ctk.CTkFrame(self.radar_frame, fg_color="transparent")
        self.matrix_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.matrix_frame.grid_columnconfigure((0,1,2,3), weight=1, uniform="strat")  # 🔥 4 COLUMNAS

        self.strat_a = self.mk_strategy_card(0, "MAKER / MAKER", "Spread + Skew", "#27ae60")
        self.strat_b = self.mk_strategy_card(1, "MAKER / MAKER", "Spread + Skew", "#3498db")
        self.strat_c_buy = self.mk_strategy_card(2, "PEPITA COMPRA", "Arbitraje", "#f39c12")    # 🔥 NUEVA
        self.strat_c_sell = self.mk_strategy_card(3, "PEPITA VENTA", "Arbitraje", "#9b59b6")   # 🔥 NUEVA

        # --- SIMULADOR ---
        self.sim_frame = ctk.CTkFrame(self.radar_frame, fg_color="#121212", border_width=1, border_color="#333", corner_radius=10)
        self.sim_frame.pack(fill="x", padx=10, pady=(20, 5))
        
        sim_inner = ctk.CTkFrame(self.sim_frame, fg_color="transparent")
        sim_inner.pack(pady=12)

        ctk.CTkLabel(sim_inner, text="COMPRA", font=("Arial", 11, "bold"), text_color="#2ecc71").pack(side="left", padx=5)
        self.entry_sim_buy = ctk.CTkEntry(sim_inner, width=100, justify="center", fg_color="#2b2b2b", border_width=0, font=("Arial", 13, "bold"))
        self.entry_sim_buy.pack(side="left", padx=2)
        self.entry_sim_buy.bind("<KeyRelease>", self.calcular_simulacion)
        
        self.sim_buy_mode = ctk.CTkOptionMenu(sim_inner, values=["Maker", "Taker"], width=80, fg_color="#333", button_color="#444", command=self.calcular_simulacion)
        self.sim_buy_mode.set("Maker")
        self.sim_buy_mode.pack(side="left", padx=2)

        ctk.CTkLabel(sim_inner, text="➜", font=("Arial", 16), text_color="#555").pack(side="left", padx=15)

        ctk.CTkLabel(sim_inner, text="VENTA", font=("Arial", 11, "bold"), text_color="#e74c3c").pack(side="left", padx=5)
        self.entry_sim_sell = ctk.CTkEntry(sim_inner, width=100, justify="center", fg_color="#2b2b2b", border_width=0, font=("Arial", 13, "bold"))
        self.entry_sim_sell.pack(side="left", padx=2)
        self.entry_sim_sell.bind("<KeyRelease>", self.calcular_simulacion)
        
        self.sim_sell_mode = ctk.CTkOptionMenu(sim_inner, values=["Maker", "Taker"], width=80, fg_color="#333", button_color="#444", command=self.calcular_simulacion)
        self.sim_sell_mode.set("Maker")
        self.sim_sell_mode.pack(side="left", padx=2)

        ctk.CTkLabel(sim_inner, text="=", font=("Arial", 16), text_color="#555").pack(side="left", padx=15)
        self.lbl_sim_result = ctk.CTkLabel(sim_inner, text="--- %", font=("Arial", 18, "bold"), text_color="gray")
        self.lbl_sim_result.pack(side="left", padx=5)

        # --- FOOTER ---
        self.f_sesion = ctk.CTkFrame(self, fg_color="#2b2b2b", border_color="#e3a319", border_width=2, corner_radius=10)
        self.f_sesion.pack(fill="x", padx=20, pady=(10, 10))
        self.f_sesion.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.f_sesion, text="RENDIMIENTO TURNO ACTUAL", font=("Arial", 11, "bold"), text_color="#e3a319").grid(row=0, column=0, pady=(10, 2))
        self.lbl_gan_sesion = ctk.CTkLabel(self.f_sesion, text="---", font=("Arial", 26, "bold"))
        self.lbl_gan_sesion.grid(row=1, column=0, pady=2)
        self.lbl_gan_sesion_usdt = ctk.CTkLabel(self.f_sesion, text="--- USDT", font=("Arial", 12), text_color="#aaaaaa")
        self.lbl_gan_sesion_usdt.grid(row=2, column=0, pady=(0, 10))

    def render_historia_inicial(self):
            """ Pinta los GAPs históricos calculados en los 4 espacios de la izquierda """
            if not self.datos_historicos_cache:
                return

            for i, dato in enumerate(self.datos_historicos_cache):
                if i >= 4: break # El 5to espacio es para el "VIVO"
                
                frame, lbl_dia, lbl_gap = self.market_widgets[i]
                
                # Extraemos el día (ej: "Martes" de "Martes, 16 de...")
                dia_semana = dato["fecha"].split(',')[0] 
                gap_val = dato["gap"]
                
                # Colores de tendencia
                color = "white"
                if gap_val > 4.5: color = "#e74c3c" # Eufórico
                elif gap_val < 2.5: color = "#2ecc71" # Oportunidad
                
                lbl_dia.configure(text=dia_semana.upper()[:3]) # Muestra MAR, MIE, JUE...
                lbl_gap.configure(text=f"{gap_val:.2f}%", text_color=color)

    def background_dolarito_updater(self):
        while True:
            datos = self.scraper_engine.obtener_precios_vivo()
            if datos:
                self.cached_blue, self.cached_blue_pct = datos["blue"]
                self.cached_mep, self.cached_mep_pct = datos["mep"]
                self.cached_ccl, self.cached_ccl_pct = datos["ccl"]
            time.sleep(60)
    def cargar_historia_combinada(self):
        """
        Carga datos históricos del scraper de Dolarito
        (Sistema viejo - mantener para compatibilidad)
        """
        print("📊 Iniciando carga de historia de Dolarito...")
        
        try:
            # Cargar datos históricos del scraper
            historia = self.scraper_engine.cargar_historia_combinada()
            
            if historia:
                self.historical_gaps = historia
                print(f"✅ Historia cargada: {len(historia)} registros")
                
                # Actualizar los widgets de la línea de tiempo vieja
                self.after(0, lambda: self.actualizar_timeline_viejo(historia))
            else:
                print("⚠️ No se pudo cargar historia de Dolarito")
                self.historical_gaps = []
                
        except Exception as e:
            print(f"❌ Error cargando historia: {e}")
            self.historical_gaps = []

    def actualizar_timeline_viejo(self, historia):
        """
        Actualiza la línea de tiempo vieja (primeros 4 widgets)
        El 5to widget (market_widgets[-1]) se actualiza en render_escaneo
        """
        try:
            # Actualizar solo los primeros 4 (los históricos)
            for i, gap_data in enumerate(historia[:4]):
                if i >= len(self.market_widgets) - 1:  # -1 porque el último es "HOY"
                    break
                
                frame_hist, lbl_dia, lbl_gap = self.market_widgets[i]
                
                dia_texto = gap_data.get('fecha', '---')
                gap_val = gap_data.get('gap', 0.0)
                
                # Colorear según valor
                color = "#3498db"  # Azul por defecto
                if gap_val > 4.5:
                    color = "#e74c3c"  # Rojo (GAP alto)
                elif gap_val < 2.5:
                    color = "#2ecc71"  # Verde (GAP bajo - oportunidad)
                
                # Extraer día de la semana del texto
                try:
                    dia_semana = dia_texto.split()[0][:3].upper()
                except:
                    dia_semana = "---"
                
                lbl_dia.configure(text=dia_semana)
                lbl_gap.configure(text=f"{gap_val:.2f}%", text_color=color)
                
        except Exception as e:
            print(f"Error actualizando timeline viejo: {e}")
            
    # --- LÓGICA DE ESCANEO ---
    def auto_scan_loop(self):
        if not self.is_scanning: 
            self.lanzar_escaneo()
        
        try: 
            self.update_stats_footer()
            self.actualizar_tablero_estrategico()
            
            # ✅ MOVER DENTRO DEL TRY
            if hasattr(self, 'historical_timeline'):
                try:
                    self.historical_timeline.update_data()
                except Exception as e:
                    print(f"⚠️ Error actualizando timeline histórico: {e}")
                    # No hacer nada más, seguir con el loop
            
        except Exception as e: 
            print(f"⚠️ Error en loop visual: {e}") 
        
        # Reprogramar siempre (incluso si hubo error)
        self.after(5000, self.auto_scan_loop)
        

    def lanzar_escaneo(self):
        if self.is_scanning: return
        self.is_scanning = True
        self.lbl_scanner_status.configure(text="⚡ Analizando...", text_color="#f39c12")
        self.resultado_escaneo = None 
        
        self.controller.cursor.execute("SELECT value FROM config WHERE key='api_key'")
        ak = self.controller.cursor.fetchone()
        self.controller.cursor.execute("SELECT value FROM config WHERE key='api_secret'")
        ask = self.controller.cursor.fetchone()
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

        # LLAMADA AL CEREBRO EXTERNO
        threading.Thread(target=self._wrapper_logic, args=(ak[0] if ak else None, ask[0] if ask else None, maker_fee, taker_fee, ppp_ars, saldo_ars, stock_usdt, saldo_usd_fiat, mep_ref, blue_ref, ccl_ref, mep_pct, blue_pct, ccl_pct), daemon=True).start()
        
        self.after(100, self.verificar_resultado_escaneo)

    def _wrapper_logic(self, *args):
        # Wrapper para conectar con el módulo logic
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
                        profit_c_buy, profit_c_sell):
        
        hora = datetime.now().strftime('%H:%M:%S')
        self.lbl_scanner_status.configure(text=f"⚡ ACTIVO: {hora}", text_color="#2ecc71")
        self.after(1000, lambda: self.lbl_scanner_status.configure(text_color="gray"))
        
        self.current_usdt_price = market_ask_1

        # 1. PRECIOS
        self.update_price_card(self.card_blue, blue, blue_pct)
        self.update_price_card(self.card_mep, mep, mep_pct)
        self.update_price_card(self.card_ccl, ccl, ccl_pct)
        self.update_price_card(self.card_p2p_ask, market_bid_p2p5, None) # Muestra Fila 15
        self.update_price_card(self.card_p2p_bid, market_ask_p2p5, None) # Muestra Fila 15
        
        self.lbl_ppp_radar.configure(text=f"PPP: $ {ppp:,.2f}")
        self.lbl_total_ars.configure(text=f"$ {saldo_ars:,.0f}")
        self.lbl_total_usdt.configure(text=f"{stock_usdt:,.2f}")
        
        # 2. LÓGICA DEL CUADRO VIVO (TERMÓMETRO CANJE CCL)
        # Usamos el último cuadro de la lista (sea el 5to o el 6to)
        frame_vivo, lbl_dia_vivo, lbl_gap_vivo = self.market_widgets[-1]
        
        frame_vivo.configure(fg_color="#1a1a1a", border_color="#3498db", border_width=2)
        
        # Lógica visual para el CANJE CCL/MEP
        color_vivo = "white"
        if canje_vivo > 4.50: color_vivo = "#e74c3c"
        elif canje_vivo < 2.50: color_vivo = "#2ecc71"
        
        lbl_dia_vivo.configure(text="HOY (CCL)", text_color="#3498db")
        lbl_gap_vivo.configure(text=f"{canje_vivo:.2f}%", text_color=color_vivo)
        
        # 3. DECISION
        if saldo_ars > 50000:
            mejor_entrada = min(market_bid_1, market_ask_1)
            modo_entrada = "(TAKER)" if market_ask_1 < market_bid_1 else "(MAKER)"
            if ppp == 0: txt_act, col_act, det_act = f"INICIAR {modo_entrada}", "#27ae60", "Inicia Posición."
            elif mejor_entrada < ppp: txt_act, col_act, det_act = "🟢 ACUMULAR", "#27ae60", f"Bajas PPP ({modo_entrada})."
            elif mejor_entrada < ppp * 1.01: txt_act, col_act, det_act = "🔵 SUMAR VOLUMEN", "#2980b9", "Mantienes PPP."
            else: txt_act, col_act, det_act = "ESPERAR", "gray", f"Mercado caro (${mejor_entrada:.0f})."
        else: txt_act, col_act, det_act = "SIN LIQUIDEZ", "#333", "Carga ARS."
        self.lbl_buy_action.configure(text=txt_act, text_color=col_act)
        self.buy_signal_frame.configure(border_color=col_act)
        self.lbl_buy_detail.configure(text=det_act)

        # 4. CLIMA (Referencia GAP USDT vs MEP para saber si vender)
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
        self.sell_signal_frame.configure(border_color=col_sell)
        self.lbl_sell_detail.configure(text=det_sell)

        # --- 1. SANEAMIENTO DE DATOS (Variables limpias para todos) ---
        val_ask_1 = float(market_ask_1) if market_ask_1 else 0.0
        val_ask_15 = float(market_ask_p2p5) if market_ask_p2p5 else 0.0

        val_bid_1 = float(market_bid_1) if market_bid_1 else 0.0
        val_bid_15 = float(market_bid_p2p5) if market_bid_p2p5 else 0.0

        # A. IZQUIERDA: MAKER/MAKER (SPREAD + SKEW)
        # ---------------------------------------------------------
        if val_bid_15 > 0 and val_ask_15 > 0:
            # ✅ SPREAD: Comprar en fila 15 (Maker) y Vender en fila 15 (Maker)
            profit_a = ((val_ask_15 * (1 - maker_fee)) / (val_bid_15 * (1 + maker_fee)) - 1) * 100
            
            # ✅ SKEW CORREGIDO: Distancia entre fila 1 y fila 15 del lado de VENTA (ASKs)
            # Esto mide cuánto más caro está vender en fila 15 vs fila 1
            skew_p2 = 0.0
            if val_ask_1 > 0 and val_ask_15 > 0:  # 🔥 CORRECCIÓN: Ahora usa ASKs
                skew_p2 = ((val_ask_15 / val_ask_1) - 1) * 100
            
            texto_final = f"Spr: {profit_a:+.2f}% | Sk: {skew_p2:.2f}%"
            
            # 🎨 Lógica de colores
            col_a = "#e74c3c"  # Rojo por defecto
            if profit_a > 1.5 and skew_p2 < 2.0: 
                col_a = "#2ecc71"  # Verde: Setup ideal
            elif profit_a > 0: 
                col_a = "#f39c12"  # Amarillo: Rentable pero no óptimo
            
            self.strat_a.configure(text=texto_final, text_color=col_a)
        else:
            self.strat_a.configure(text="S/D", text_color="gray")

        # ---------------------------------------------------------
        # B. CENTRO: MAKER COMPRA (BRECHA)
        # ---------------------------------------------------------
        if val_bid_1 > 0 and val_bid_15 > 0:
            dist_buy = (1 - (val_bid_15 / val_bid_1)) * 100
            text_b = f"Brecha: {dist_buy:.2f}%"
            
            col_b = "#3498db"  # Azul neutro
            if dist_buy > 0.8: 
                col_b = "#2ecc71"  # Verde: Escalera pronunciada
            elif dist_buy < 0.1: 
                col_b = "#e74c3c"  # Rojo: Mercado plano
            
            self.strat_b.configure(text=text_b, text_color=col_b)
            
            # 🔥 Actualizamos el título de la tarjeta
            try: 
                # Accedemos al label del título (primer hijo del frame padre)
                titulo_label = self.strat_b.master.winfo_children()[0]
                if isinstance(titulo_label, ctk.CTkLabel):
                    titulo_label.configure(text="MAKER COMPRA")
            except Exception as e:
                print(f"⚠️ No se pudo actualizar título B: {e}")
        else:
            self.strat_b.configure(text="S/D", text_color="gray")

        # C. DERECHA: LA PEPITA (ARBITRAJE)
        # ═══════════════════════════════════════════════════════════
        # 🔥 PEPITA COMPRA: Compro barato (BID fila 1) → Revendo caro (ASK fila 15)
        # ═══════════════════════════════════════════════════════════
        if val_ask_15 > 0 and val_bid_1 > 0:  # 🔥 CORRECCIÓN: Ahora usa bid_1
            # YO compro como TAKER en fila 1 (BID), YO vendo como MAKER en fila 15 (ASK)
            profit_c_buy = ((val_ask_15 * (1 - maker_fee)) / (val_bid_1 * (1 + taker_fee)) - 1) * 100
        else:
            print("❌ Condición PEPITA COMPRA NO cumplida")
            profit_c_buy = -99.9

        # ═══════════════════════════════════════════════════════════
        # PEPITAS DUALES (COMPRA Y VENTA SEPARADAS)
        # ═══════════════════════════════════════════════════════════

        UMBRAL_MIN = 0.3  # Mínimo para considerar viable

        # 🔷 PEPITA COMPRA
        if profit_c_buy >= UMBRAL_MIN:
            tipo_buy = "💎 VIABLE"
            color_buy = "#2ecc71"
        else:
            tipo_buy = "SIN SETUP"
            color_buy = "gray"
            profit_c_buy = max(profit_c_buy, -5.0)  # Limitar negativos

        try:
            self.strat_c_buy.master.winfo_children()[0].configure(text=tipo_buy)
            self.update_strat_card(self.strat_c_buy, profit_c_buy, "Mín: 0.3%")
        except Exception as e:
            print(f"⚠️ Error actualizando PEPITA COMPRA: {e}")

        # 🔶 PEPITA VENTA
        if profit_c_sell == -999.0:
            # No hay PPP definido
            tipo_sell = "SIN PPP"
            color_sell = "gray"
            profit_c_sell = 0.0
        elif profit_c_sell >= 1.0:
            # Ganancia mayor a 1%
            tipo_sell = "💎 VIABLE"
            color_sell = "#2ecc71"
        elif profit_c_sell >= 0.3:
            # Ganancia marginal
            tipo_sell = "⚠️ MARGINAL"
            color_sell = "#f39c12"
        elif profit_c_sell >= 0.0:
            # Break-even o ganancia mínima
            tipo_sell = "🔵 NEUTRO"
            color_sell = "#3498db"
        else:
            # Pérdida
            tipo_sell = "🛑 HOLDEAR"
            color_sell = "#e74c3c"
            profit_c_sell = max(profit_c_sell, -5.0)  # Limitar display

        try:
            # Actualizar título dinámico
            ppp_actual = self.controller.obtener_ppp("ARS")
            if ppp_actual > 0:
                titulo_label = self.strat_c_sell.master.winfo_children()[0]
                titulo_label.configure(text=f"VENTA vs PPP (${ppp_actual:.0f})")
            else:
                titulo_label = self.strat_c_sell.master.winfo_children()[0]
                titulo_label.configure(text="PEPITA VENTA")
            
            # Actualizar el valor
            self.update_strat_card(self.strat_c_sell, profit_c_sell, "Mín: 0.3%")
        except Exception as e:
            print(f"⚠️ Error actualizando PEPITA VENTA: {e}")
        
        # 6. ACTUALIZACIONES FINALES
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
        card = ctk.CTkFrame(self.cards_frame, fg_color="#252525", corner_radius=8, border_width=1, border_color="#333")
        card.grid(row=0, column=col, padx=4, sticky="ew")
        ctk.CTkLabel(card, text=title, font=("Arial", 12, "bold"), text_color="#aaa").pack(pady=(10,0))
        lbl_val = ctk.CTkLabel(card, text="---", font=("Arial", 30, "bold"), text_color="white"); lbl_val.pack(pady=(5,0))
        pill = ctk.CTkFrame(card, corner_radius=12, height=24, fg_color="#252525"); pill.pack(pady=(5,12))
        lbl_pct = ctk.CTkLabel(pill, text="---", font=("Arial", 11, "bold"), text_color="white"); lbl_pct.pack(padx=10, pady=2)
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

    def mk_stat_card(self, parent, col, title, val, color):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.grid(row=0, column=col, padx=5, pady=5)
        ctk.CTkLabel(f, text=title, font=("Arial", 10, "bold"), text_color="gray").pack()
        lbl = ctk.CTkLabel(f, text=val, font=("Arial", 18, "bold"), text_color=color); lbl.pack(); return lbl
    def mk_strategy_card(self, col, title, subt, color):
        card = ctk.CTkFrame(self.matrix_frame, fg_color="#1a1a1a", corner_radius=8, border_width=1, border_color="#333"); card.grid(row=0, column=col, padx=4, sticky="ew")
        ctk.CTkLabel(card, text=title, font=("Arial", 11, "bold"), text_color=color).pack(pady=(8,0))
        lbl_pct = ctk.CTkLabel(card, text="--- %", font=("Arial", 18, "bold"), text_color="white"); lbl_pct.pack(pady=(2,0))
        ctk.CTkLabel(card, text=subt, font=("Arial", 10), text_color="gray").pack(pady=(0,8)); return lbl_pct
    def update_strat_card(self, lbl, val, txt_extra):
        color = "#e74c3c" if val < 0 else "#2ecc71" if val > 0.5 else "#f1c40f"
        lbl.configure(text=f"{val:+.2f}%", text_color=color)
    def update_radar_labels(self, val): self.update_stats_footer()
    def confirmar_reset_ppp(self): 
        def do_reset(): self.controller.reiniciar_ppp(); self.lbl_ppp_radar.configure(text=f"PPP: $ 0.00")
        self.controller.ask_confirm("Reiniciar PPP", "¿Archivar compras y volver a 0?", do_reset)
    def update_view(self): self.update_stats_footer()

# --- AGREGA ESTO AL FINAL DE TU CLASE DashboardView ---
    def actualizar_tablero_estrategico(self):
        """Actualiza los cuadros de Situación y Clima con MEMORIA"""
        
        historia = getattr(self, "historical_gaps", [])
        vivo = getattr(self.scraper_engine, "cache_vivo", None)

        estrategia = self.scraper_engine.analizar_mercado(historia, vivo)

        # --- LA CORRECCIÓN ANTI-PARPADEO ---
        # Si el cerebro responde "CARGANDO..." o "ESPERAR", pero la pantalla 
        # YA TIENE un dato válido (no es "---"), ignoramos esta actualización.
        # Preferimos ver el dato de hace 5 segundos que un letrero de "Cargando".
        
        texto_actual = self.lbl_sell_action.cget("text")
        nueva_accion = estrategia.get('accion', '---')
        
        if "CARGANDO" in nueva_accion and texto_actual != "---":
            return # Nos quedamos con lo que había, salimos de la función.
        # -----------------------------------

        # SI PASAMOS EL FILTRO, ACTUALIZAMOS TODO NORMAL:
        
        # 1. CUADRO DERECHO
        self.lbl_sell_action.configure(text=nueva_accion)
        self.lbl_sell_detail.configure(text=estrategia.get('subtexto', '...'))
        
        colores = {"compra": "#2ecc71", "venta": "#e74c3c", "neutral": "#3498db", "error": "#gray"}
        self.lbl_sell_action.configure(text_color=colores.get(estrategia.get('tipo'), "#white"))

        # 2. CUADRO IZQUIERDO
        rec = estrategia.get('rec_contable', '---')
        self.lbl_buy_action.configure(text=rec)
        
        if "SUMAR" in rec:
            self.lbl_buy_action.configure(text_color="#2ecc71")
            self.lbl_buy_detail.configure(text="El mercado favorece compra.")
        elif "VENDER" in rec:
            self.lbl_buy_action.configure(text_color="#e74c3c")
            self.lbl_buy_detail.configure(text="Aprovecha subida para salir.")
        else:
            self.lbl_buy_action.configure(text_color="#3498db")
            self.lbl_buy_detail.configure(text="Operación normal.")

    def abrir_blacklist_manager(self):
        """Abre ventana de gestión de usuarios baneados"""
        modal = ModernModal(self.controller, "🛡️ GESTOR DE BLACKLIST", width=600, height=500)
        
        # Frame superior: Añadir usuario
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
        
        # Frame inferior: Lista de baneados
        ctk.CTkLabel(modal.content_frame, text="USUARIOS BANEADOS:", font=("Arial", 11, "bold"), text_color="gray").pack(anchor="w", padx=10, pady=(20,5))
        
        list_frame = ctk.CTkScrollableFrame(modal.content_frame, fg_color="#0a0a0a", height=250)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        def actualizar_lista():
            # Limpiar lista actual
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            # Cargar desde BD
            self.controller.cursor.execute("SELECT id, nickname, fecha_baneo, motivo FROM p2p_blacklist ORDER BY fecha_baneo DESC")
            baneados = self.controller.cursor.fetchall()
            
            if not baneados:
                ctk.CTkLabel(list_frame, text="No hay usuarios baneados", text_color="gray").pack(pady=20)
                return
            
            for ban_id, nick, fecha, motivo in baneados:
                row = ctk.CTkFrame(list_frame, fg_color="#1a1a1a", corner_radius=6)
                row.pack(fill="x", pady=3, padx=5)
                
                # Info
                info_box = ctk.CTkFrame(row, fg_color="transparent")
                info_box.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                
                ctk.CTkLabel(info_box, text=nick, font=("Arial", 13, "bold"), text_color="#e74c3c").pack(anchor="w")
                ctk.CTkLabel(info_box, text=f"Fecha: {fecha} | {motivo}", font=("Arial", 9), text_color="gray").pack(anchor="w")
                
                # Botón eliminar
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
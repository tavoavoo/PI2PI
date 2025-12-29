"""
🎨 COMPONENTE VISUAL: HISTÓRICO HORIZONTAL (ESTILO CLONADO CANJE)
- Tarjetas: Misma tipografía y proporciones que el cuadro de arriba.
- Métricas: Abajo en fila horizontal.
"""

import customtkinter as ctk
from datetime import datetime

class HistoricalTimelineWidget(ctk.CTkFrame):
    def __init__(self, parent, analyzer, **kwargs):
        super().__init__(parent, fg_color="#0f0f0f", border_width=1, border_color="#333", **kwargs)
        self.analyzer = analyzer
        
        # --- 1. HEADER ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(5, 2)) # Menos padding vertical
        
        ctk.CTkLabel(header, text="📈 HISTÓRICO P2P (5 DÍAS)", font=("Arial", 12, "bold"), text_color="#3498db").pack(side="left")
        self.lbl_status = ctk.CTkLabel(header, text="...", font=("Consolas", 10), text_color="gray")
        self.lbl_status.pack(side="right")
        
        # --- 2. TARJETAS DE DÍAS (FILA SUPERIOR) ---
        self.cards_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_panel.pack(fill="x", padx=5, pady=(0, 2))
        self.cards_panel.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        self.day_cards = []
        for i in range(5):
            card = self._create_day_card(i)
            self.day_cards.append(card)

        # --- 3. MÉTRICAS GLOBALES (FILA INFERIOR) ---
        self.stats_panel = ctk.CTkFrame(self, fg_color="#151515", corner_radius=6)
        self.stats_panel.pack(fill="x", padx=10, pady=(2, 8))
        self.stats_panel.grid_columnconfigure((0,1,2,3), weight=12)
        
        # 4 Métricas alineadas horizontalmente
        self.lbl_avg_7d = self._create_bottom_stat(self.stats_panel, 0, "PROM 7D")
        self.lbl_volatility = self._create_bottom_stat(self.stats_panel, 1, "VOLATILIDAD")
        self.lbl_trend = self._create_bottom_stat(self.stats_panel, 2, "TENDENCIA")
        self.lbl_best_time = self._create_bottom_stat(self.stats_panel, 3, "MEJOR HORA")

    def _create_day_card(self, col):
        # Usamos el mismo color de fondo y borde que las tarjetas de arriba
        frame = ctk.CTkFrame(self.cards_panel, fg_color="#1a1a1a", corner_radius=6, border_width=1, border_color="#333")
        frame.grid(row=0, column=col, padx=3, pady=0, sticky="nsew")
        
        # A. Cabecera (Día + Fecha) - Compacta
        # Padding top 4 (igual que Canje)
        head = ctk.CTkFrame(frame, fg_color="transparent", height=15)
        head.pack(fill="x", pady=(4, 0), padx=5)
        
        lbl_day = ctk.CTkLabel(head, text="---", font=("Arial", 11, "bold"), text_color="gray") # Igual que Canje
        lbl_day.pack(side="left")
        
        lbl_date = ctk.CTkLabel(head, text="--/--", font=("Arial", 9), text_color="#555")
        lbl_date.pack(side="right")
        
        # B. GAP (Centro Grande)
        # Font 24 Bold (Igual que Canje) y sin padding extra
        lbl_gap = ctk.CTkLabel(frame, text="---%", font=("Arial", 24, "bold"), text_color="white")
        lbl_gap.pack(pady=(0, 0)) 
        
        # C. Footer (Volatilidad + Cierre)
        # Padding bottom 4 (Igual que Canje)
        foot = ctk.CTkFrame(frame, fg_color="transparent", height=15)
        foot.pack(fill="x", pady=(0, 4), padx=5)
        
        # Volatilidad (Abajo Izquierda - Gris Chiquito)
        lbl_range = ctk.CTkLabel(foot, text="↕ ---", font=("Arial", 13), text_color="#666")
        lbl_range.pack(side="left")
        
        # Cierre (Abajo Derecha - Azul Destacado)
        lbl_close = ctk.CTkLabel(foot, text="", font=("Arial", 15, "bold"), text_color="#3498db")
        lbl_close.pack(side="right")
        
        return {'frame': frame, 'lbl_day': lbl_day, 'lbl_date': lbl_date, 'lbl_gap': lbl_gap, 'lbl_range': lbl_range, 'lbl_close': lbl_close}
    
    def _create_bottom_stat(self, parent, col, title):
        """Crea una métrica para la barra inferior horizontal"""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, sticky="ns", padx=5, pady=5)
        
        # Título (gris)
        ctk.CTkLabel(f, text=title, font=("Arial", 9, "bold"), text_color="gray").pack()
        
        # Valor (blanco/color) -> AUMENTADO A 16
        lbl = ctk.CTkLabel(f, text="---", font=("Arial", 16, "bold"), text_color="white")
        lbl.pack()
        return lbl

    def update_data(self):
        try:
            if not self.analyzer: return
            try: metrics = self.analyzer.get_dashboard_metrics()
            except: return
            if not metrics or metrics.get('status') != 'success': 
                self.lbl_status.configure(text="Sin datos")
                return
            
            summary = metrics.get('summary_7days', [])
            if not summary: return
            
            summary_reversed = list(reversed(summary))
            last_5_days = summary_reversed[-5:] if len(summary_reversed) >= 5 else summary_reversed
            hoy_str = datetime.now().strftime("%Y-%m-%d")

            # --- ACTUALIZAR TARJETAS ---
            for i in range(5):
                card = self.day_cards[i]
                if i < len(last_5_days):
                    day_data = last_5_days[i]
                    fecha_str = day_data.get('fecha', '')
                    
                    # Textos
                    try:
                        dt = datetime.strptime(fecha_str, "%Y-%m-%d")
                        card['lbl_date'].configure(text=dt.strftime("%d/%m"))
                    except: card['lbl_date'].configure(text="--/--")
                    card['lbl_day'].configure(text=str(day_data.get('dia_nombre', '---')))
                    
                    # GAP y Color Estricto
                    gap = float(day_data.get('gap_promedio', 0) or 0)
                    card['lbl_gap'].configure(text=f"{gap:+.2f}%")
                    
                    if gap > 2.0: color = "#e74c3c"   # Rojo
                    elif gap < 0.0: color = "#2ecc71" # Verde
                    else: color = "#3498db"           # Azul
                    card['lbl_gap'].configure(text_color=color)
                    
                    # Volatilidad (Abajo Izquierda)
                    vol = float(day_data.get('volatilidad', 0) or 0)
                    card['lbl_range'].configure(text=f"↕ {vol:.2f}%")
                    
                    # Cierre (Abajo Derecha)
                    if fecha_str == hoy_str:
                        card['frame'].configure(border_color="#3498db", border_width=2)
                        card['lbl_close'].configure(text="")
                    else:
                        card['frame'].configure(border_color="#333", border_width=1)
                        cierre = float(day_data.get('cierre_usdt', 0) or 0)
                        card['lbl_close'].configure(text=f"${cierre:,.0f}")
                else:
                    card['lbl_day'].configure(text="---")
                    card['lbl_gap'].configure(text="---")
                    card['lbl_range'].configure(text="")
                    card['lbl_close'].configure(text="")

            # --- ACTUALIZAR MÉTRICAS INFERIORES ---
            vol_data = metrics.get('volatility', {})
            prom = float(vol_data.get('promedio', 0) or 0)
            self.lbl_avg_7d.configure(text=f"{prom:+.2f}%", text_color="#3498db")
            
            dev = float(vol_data.get('desviacion_estandar', 0) or 0)
            self.lbl_volatility.configure(text=f"±{dev:.2f}%", text_color="white")
            
            trend = metrics.get('trend_24h', {})
            t_dir = trend.get('direccion', 'estable')
            
            if t_dir == 'subiendo':
                txt_t = "↗ Subiendo"
            elif t_dir == 'bajando':
                txt_t = "↘ Bajando"
            else:
                txt_t = "→ Estable"
            
            self.lbl_trend.configure(text=txt_t, text_color=trend.get('color', 'white'))
            
            # 4. MEJOR HORA (🔥 ESTE ERA EL FIX FALTANTE)
            best_time = metrics.get('best_trading_time', {})
            hora = best_time.get('mejor_hora', 0)
            gap_hora = float(best_time.get('mejor_gap', 0) or 0)
            
            # Formatear hora con padding (ej: "09:00" en vez de "9:00")
            hora_texto = f"{hora:02d}:00"
            
            self.lbl_best_time.configure(
                text=f"{hora_texto}\n({gap_hora:+.2f}%)", 
                text_color="#e3a319"  # Color dorado para destacar
            )
            
        except Exception as e:
            print(f"Error widget: {e}")
            self.lbl_status.configure(text="Err", text_color="red")

class CompactHistoricalCard(ctk.CTkFrame):
    """Mantenida por compatibilidad"""
    def __init__(self, parent, analyzer, **kwargs):
        super().__init__(parent, fg_color="#1a1a1a", **kwargs)
    def update_data(self): pass
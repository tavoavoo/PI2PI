"""
🎨 COMPONENTE VISUAL: HISTÓRICO MEJORADO
Versión con orden correcto: Mié → Jue → Vie → Sáb → Dom
"""

import customtkinter as ctk
from datetime import datetime

class HistoricalTimelineWidget(ctk.CTkFrame):
    """
    Widget de línea de tiempo histórica basado en datos reales de P2P
    Muestra últimos 5 días: [Mié] [Jue] [Vie] [Sáb] [Dom-HOY]
    """
    
    def __init__(self, parent, analyzer, **kwargs):
        super().__init__(parent, fg_color="#0f0f0f", border_width=1, border_color="#333", **kwargs)
        
        self.analyzer = analyzer
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            header, 
            text="📈 HISTÓRICO 5 DÍAS: GAP CCL vs USDT P2P", 
            font=("Arial", 13, "bold"), 
            text_color="#3498db"
        ).pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(
            header,
            text="Cargando...",
            font=("Consolas", 10),
            text_color="gray"
        )
        self.lbl_status.pack(side="right")
        
        # Contenedor de tarjetas (5 días)
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=5, pady=5)
        self.cards_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        # Crear 5 tarjetas (últimos 5 días)
        self.day_cards = []
        for i in range(5):
            card = self._create_day_card(i)
            self.day_cards.append(card)
        
        # Panel de estadísticas debajo
        stats_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=6)
        stats_frame.pack(fill="x", padx=10, pady=(5, 10))
        stats_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        # Métrica 1: Promedio 7 días
        self.lbl_avg_7d = self._create_mini_stat(stats_frame, 0, "PROMEDIO 7D")
        
        # Métrica 2: Volatilidad
        self.lbl_volatility = self._create_mini_stat(stats_frame, 1, "VOLATILIDAD")
        
        # Métrica 3: Tendencia 24h
        self.lbl_trend = self._create_mini_stat(stats_frame, 2, "TENDENCIA 24H")
        
        # Métrica 4: Mejor hora
        self.lbl_best_time = self._create_mini_stat(stats_frame, 3, "MEJOR HORA")
    
    def _create_day_card(self, col):
        """Crea una tarjeta individual para un día"""
        frame = ctk.CTkFrame(
            self.cards_frame, 
            fg_color="#1a1a1a", 
            corner_radius=6, 
            border_width=1, 
            border_color="#333"
        )
        frame.grid(row=0, column=col, padx=3, pady=5, sticky="ew")
        
        # Día de la semana
        lbl_day = ctk.CTkLabel(
            frame, 
            text="---", 
            font=("Arial", 10, "bold"), 
            text_color="gray"
        )
        lbl_day.pack(pady=(8, 2))
        
        # Fecha
        lbl_date = ctk.CTkLabel(
            frame,
            text="--/--",
            font=("Arial", 9),
            text_color="#666"
        )
        lbl_date.pack(pady=(0, 5))
        
        # GAP principal (grande)
        lbl_gap = ctk.CTkLabel(
            frame, 
            text="---%", 
            font=("Arial", 22, "bold"), 
            text_color="white"
        )
        lbl_gap.pack(pady=(0, 3))
        
        # Rango (min-max)
        lbl_range = ctk.CTkLabel(
            frame,
            text="↕ ---",
            font=("Arial", 8),
            text_color="#888"
        )
        lbl_range.pack(pady=(0, 8))
        
        return {
            'frame': frame,
            'lbl_day': lbl_day,
            'lbl_date': lbl_date,
            'lbl_gap': lbl_gap,
            'lbl_range': lbl_range
        }
    
    def _create_mini_stat(self, parent, col, title):
        """Crea una mini-estadística"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, padx=5, pady=8)
        
        ctk.CTkLabel(
            frame,
            text=title,
            font=("Arial", 9),
            text_color="gray"
        ).pack()
        
        lbl_value = ctk.CTkLabel(
            frame,
            text="---",
            font=("Arial", 13, "bold"),
            text_color="white"
        )
        lbl_value.pack()
        
        return lbl_value
    
    def update_data(self):
        """
        Actualiza todas las tarjetas con datos frescos de la BD
        ORDEN CORRECTO: [Mié] [Jue] [Vie] [Sáb] [Dom-HOY]
        """
        try:
            # ========================================================================
            # VALIDACIONES INICIALES
            # ========================================================================
            if not hasattr(self, 'analyzer') or self.analyzer is None:
                self.lbl_status.configure(text="❌ Analyzer no inicializado")
                return
            
            try:
                metrics = self.analyzer.get_dashboard_metrics()
            except Exception as e:
                self.lbl_status.configure(text=f"❌ Error DB: {str(e)[:20]}")
                return
            
            if not metrics or not isinstance(metrics, dict):
                self.lbl_status.configure(text="❌ Sin datos")
                return
            
            if metrics.get('status') != 'success':
                error_msg = metrics.get('message', 'Error desconocido')
                self.lbl_status.configure(text=f"❌ {error_msg[:25]}")
                return
            
            # ========================================================================
            # OBTENER Y ORDENAR DATOS (MÁS ANTIGUO → MÁS RECIENTE)
            # ========================================================================
            summary = metrics.get('summary_7days', [])
            
            if not summary or not isinstance(summary, list):
                self.lbl_status.configure(text="⚠️ Sin resumen diario")
                return
            
            # El analyzer devuelve ordenado DESC (más reciente primero)
            # Necesitamos invertir para tener: [más antiguo → hoy]
            summary_reversed = list(reversed(summary))
            
            # Tomar los últimos 5 días (los más recientes)
            last_5_days = summary_reversed[-5:] if len(summary_reversed) >= 5 else summary_reversed
            
            print(f"📊 Mostrando últimos 5 días (orden: antiguo→hoy):")
            for idx, day in enumerate(last_5_days):
                print(f"  [{idx}] {day.get('dia_nombre')} {day.get('fecha')}: {day.get('gap_promedio', 0):.2f}%")
            
            # ========================================================================
            # ACTUALIZAR TARJETAS (ORDEN: MIÉ JUE VIE SÁB DOM)
            # ========================================================================
            for i in range(5):
                card = self.day_cards[i]
                
                if i < len(last_5_days):
                    day_data = last_5_days[i]
                    
                    if not isinstance(day_data, dict):
                        continue
                    
                    # Día de la semana
                    dia_nombre = day_data.get('dia_nombre', '---')
                    card['lbl_day'].configure(text=str(dia_nombre))
                    
                    # Fecha (formato DD/MM)
                    fecha_str = day_data.get('fecha', '')
                    try:
                        if fecha_str:
                            dt = datetime.strptime(fecha_str, "%Y-%m-%d")
                            fecha_corta = dt.strftime("%d/%m")
                            card['lbl_date'].configure(text=fecha_corta)
                        else:
                            card['lbl_date'].configure(text="--/--")
                    except:
                        card['lbl_date'].configure(text=str(fecha_str)[-5:] if fecha_str else "--/--")
                    
                    # GAP promedio
                    gap = day_data.get('gap_promedio', 0)
                    try:
                        gap = float(gap) if gap is not None else 0.0
                    except:
                        gap = 0.0
                    
                    card['lbl_gap'].configure(text=f"{gap:+.2f}%")
                    
                    # Color según valor
                    if gap > 1.0:
                        color = "#2ecc71"  # Verde fuerte
                    elif gap > 0.5:
                        color = "#52c785"  # Verde suave
                    elif gap > 0:
                        color = "#e3a319"  # Amarillo
                    else:
                        color = "#e74c3c"  # Rojo
                    
                    card['lbl_gap'].configure(text_color=color)
                    
                    # Volatilidad
                    volatilidad = day_data.get('volatilidad', 0)
                    try:
                        volatilidad = float(volatilidad) if volatilidad is not None else 0.0
                    except:
                        volatilidad = 0.0
                    
                    card['lbl_range'].configure(text=f"↕ {volatilidad:.2f}%")
                    
                    # Borde especial si es HOY (última tarjeta)
                    hoy = datetime.now().strftime("%Y-%m-%d")
                    if fecha_str == hoy:
                        card['frame'].configure(border_color="#3498db", border_width=2)
                    else:
                        card['frame'].configure(border_color="#333", border_width=1)
                else:
                    # Si no hay suficientes días, dejar vacío
                    card['lbl_day'].configure(text="---")
                    card['lbl_date'].configure(text="--/--")
                    card['lbl_gap'].configure(text="---%")
                    card['lbl_range'].configure(text="↕ ---")
            
            # ========================================================================
            # ESTADÍSTICAS GLOBALES
            # ========================================================================
            
            # Promedio 7 días
            volatility = metrics.get('volatility')
            if volatility and isinstance(volatility, dict):
                promedio = volatility.get('promedio', 0)
                try:
                    promedio = float(promedio) if promedio is not None else 0.0
                    self.lbl_avg_7d.configure(
                        text=f"{promedio:+.2f}%",
                        text_color="#3498db"
                    )
                except:
                    self.lbl_avg_7d.configure(text="---")
            else:
                self.lbl_avg_7d.configure(text="---")
            
            # Volatilidad
            if volatility and isinstance(volatility, dict):
                vol = volatility.get('desviacion_estandar', 0)
                try:
                    vol = float(vol) if vol is not None else 0.0
                    self.lbl_volatility.configure(
                        text=f"±{vol:.2f}%",
                        text_color="#e3a319" if vol > 0.5 else "#2ecc71"
                    )
                except:
                    self.lbl_volatility.configure(text="---")
            else:
                self.lbl_volatility.configure(text="---")
            
            # Tendencia 24h
            trend = metrics.get('trend_24h')
            if trend and isinstance(trend, dict):
                direccion = trend.get('direccion', 'estable')
                cambio = trend.get('cambio', 0)
                color = trend.get('color', '#3498db')
                
                try:
                    cambio = float(cambio) if cambio is not None else 0.0
                    
                    if direccion == 'subiendo':
                        texto = f"↗ +{cambio:.2f}%"
                    elif direccion == 'bajando':
                        texto = f"↘ {cambio:.2f}%"
                    else:
                        texto = "→ Estable"
                    
                    self.lbl_trend.configure(text=texto, text_color=color)
                except:
                    self.lbl_trend.configure(text="---")
            else:
                self.lbl_trend.configure(text="---")
            
            # Mejor hora para operar
            best_time = metrics.get('best_trading_time')
            if best_time and isinstance(best_time, dict):
                hora = best_time.get('mejor_hora', 0)
                gap = best_time.get('mejor_gap', 0)
                
                try:
                    hora = int(hora) if hora is not None else 0
                    gap = float(gap) if gap is not None else 0.0
                    
                    self.lbl_best_time.configure(
                        text=f"{hora:02d}:00h ({gap:+.2f}%)",
                        text_color="#2ecc71"
                    )
                except:
                    self.lbl_best_time.configure(text="---")
            else:
                self.lbl_best_time.configure(text="---")
            
            # Status (success)
            total_regs = metrics.get('total_registros', 0)
            try:
                total_regs = int(total_regs) if total_regs is not None else 0
                self.lbl_status.configure(
                    text=f"✓ {total_regs} registros",
                    text_color="#2ecc71"
                )
            except:
                self.lbl_status.configure(text="✓ OK", text_color="#2ecc71")
            
        except Exception as e:
            error_msg = str(e)[:30]
            print(f"❌ Error actualizando timeline: {e}")
            self.lbl_status.configure(
                text=f"⚠️ {error_msg}",
                text_color="#e74c3c"
            )


class CompactHistoricalCard(ctk.CTkFrame):
    """
    Versión compacta del histórico para espacios reducidos
    """
    
    def __init__(self, parent, analyzer, **kwargs):
        super().__init__(parent, fg_color="#1a1a1a", corner_radius=8, border_width=1, border_color="#333", **kwargs)
        
        self.analyzer = analyzer
        
        # Header
        ctk.CTkLabel(
            self,
            text="📊 RESUMEN HISTÓRICO",
            font=("Arial", 11, "bold"),
            text_color="#3498db"
        ).pack(pady=(10, 5))
        
        # Grid de métricas
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(padx=15, pady=5)
        
        # GAP Actual vs Promedio
        ctk.CTkLabel(grid, text="Gap Actual:", font=("Arial", 9), text_color="gray").grid(row=0, column=0, sticky="e", padx=5)
        self.lbl_gap_actual = ctk.CTkLabel(grid, text="---", font=("Arial", 11, "bold"))
        self.lbl_gap_actual.grid(row=0, column=1, sticky="w")
        
        ctk.CTkLabel(grid, text="vs Promedio:", font=("Arial", 9), text_color="gray").grid(row=1, column=0, sticky="e", padx=5)
        self.lbl_gap_prom = ctk.CTkLabel(grid, text="---", font=("Arial", 11, "bold"))
        self.lbl_gap_prom.grid(row=1, column=1, sticky="w")
        
        # Indicador
        self.lbl_indicador = ctk.CTkLabel(
            self,
            text="---",
            font=("Arial", 13, "bold"),
            text_color="white"
        )
        self.lbl_indicador.pack(pady=(5, 10))
    
    def update_data(self):
        """Actualiza la tarjeta compacta (VERSIÓN BLINDADA)"""
        try:
            if not hasattr(self, 'analyzer') or self.analyzer is None:
                return
            
            metrics = self.analyzer.get_dashboard_metrics()
            
            if not metrics or not isinstance(metrics, dict):
                return
            
            if metrics.get('status') != 'success':
                return
            
            current = metrics.get('current_vs_avg')
            
            if not current or not isinstance(current, dict):
                return
            
            # GAP actual
            gap_actual = current.get('gap_actual', 0)
            try:
                gap_actual = float(gap_actual) if gap_actual is not None else 0.0
                self.lbl_gap_actual.configure(
                    text=f"{gap_actual:+.2f}%",
                    text_color="#2ecc71" if gap_actual > 0 else "#e74c3c"
                )
            except:
                self.lbl_gap_actual.configure(text="---")
            
            # GAP promedio
            gap_prom = current.get('gap_promedio', 0)
            try:
                gap_prom = float(gap_prom) if gap_prom is not None else 0.0
                self.lbl_gap_prom.configure(
                    text=f"{gap_prom:+.2f}%",
                    text_color="#888"
                )
            except:
                self.lbl_gap_prom.configure(text="---")
            
            # Indicador de desviación
            z = current.get('z_score', 0)
            try:
                z = float(z) if z is not None else 0.0
                
                if z > 1:
                    texto = "🔥 MUY ALTO"
                    color = "#e74c3c"
                elif z > 0.5:
                    texto = "↗ ARRIBA PROMEDIO"
                    color = "#2ecc71"
                elif z < -1:
                    texto = "❄️ MUY BAJO"
                    color = "#3498db"
                elif z < -0.5:
                    texto = "↘ BAJO PROMEDIO"
                    color = "#e3a319"
                else:
                    texto = "→ NORMAL"
                    color = "white"
                
                self.lbl_indicador.configure(text=texto, text_color=color)
            except:
                self.lbl_indicador.configure(text="---")
            
        except Exception as e:
            print(f"Error en tarjeta compacta: {e}")
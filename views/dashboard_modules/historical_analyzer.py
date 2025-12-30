"""
📊 MÓDULO DE ANÁLISIS HISTÓRICO P2P
Analiza datos históricos de USDT Binance P2P vs CCL/MEP
Genera visualizaciones y estadísticas para el dashboard
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

class HistoricalAnalyzer:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.cursor = db_connection.cursor()
        
    def get_timeline_data(self, days=7):
        fecha_limite = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = """
            SELECT fecha, hora, gap_ccl, usdt_sell_p5, ccl, mep
            FROM p2p_history
            WHERE fecha >= ?
            ORDER BY fecha ASC, hora ASC
        """
        
        self.cursor.execute(query, (fecha_limite,))
        results = self.cursor.fetchall()
        
        timeline = []
        for fecha, hora, gap, usdt, ccl, mep in results:
            if gap is not None: 
                timeline.append({
                    'fecha': fecha,
                    'hora': hora,
                    'datetime': f"{fecha} {hora}",
                    'gap': gap,
                    'usdt': usdt if usdt else 0.0,
                    'ccl': ccl if ccl else 0.0,
                    'mep': mep
                })
        
        return timeline
    
    def get_daily_summary(self, days=7):
        """
        Resumen diario con LÓGICA DE CIERRE BANCARIO (17:00 - 18:30)
        """
        raw_data = self.get_timeline_data(days)
        
        if not raw_data: return []

        grouped_data = defaultdict(list)
        for row in raw_data:
            grouped_data[row['fecha']].append(row)

        summary = []
        
        # Ordenamos fechas (Reciente -> Antiguo)
        for fecha in sorted(grouped_data.keys(), reverse=True):
            datos_dia = grouped_data[fecha]
            if not datos_dia: continue

            # Estadísticas básicas
            gaps = [d['gap'] for d in datos_dia]
            usdts = [d['usdt'] for d in datos_dia if d['usdt'] > 0]
            
            gap_avg = statistics.mean(gaps)
            gap_min = min(gaps)
            gap_max = max(gaps)
            usdt_avg = statistics.mean(usdts) if usdts else 0
            
            # --- LÓGICA DE CIERRE BANCARIO (SNAPSHOT) ---
            cierre_usdt = 0.0
            encontrado_en_hora = False
            
            # 1. Buscamos primero en la Ventana Bancaria (17:00 a 18:30)
            # Recorremos cronológicamente para encontrar el último dentro de ese rango
            for dato in datos_dia:
                hora = dato.get('hora', '00:00:00')
                precio = dato.get('usdt', 0)
                
                # Ventana de Cierre Financiero (CCL cierra 17hs, damos margen hasta 18:30)
                if "17:00:00" <= hora <= "18:30:59" and precio > 100:
                    cierre_usdt = precio
                    encontrado_en_hora = True
            
            # 2. Si NO encontramos dato en horario bancario (ej: cerraste la app a las 15hs o abriste a las 20hs)
            # Usamos el ÚLTIMO dato disponible del día (Cierre After-Market)
            if not encontrado_en_hora or cierre_usdt == 0:
                for dato in reversed(datos_dia): # Buscamos desde el final hacia atrás
                    precio = dato.get('usdt', 0)
                    if precio > 100:
                        cierre_usdt = precio
                        break

            # Formato Fecha
            try:
                dt = datetime.strptime(fecha, "%Y-%m-%d")
                dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
                dia_nombre = dias_semana[dt.weekday()]
            except: dia_nombre = "---"

            summary.append({
                'fecha': fecha,
                'dia_nombre': dia_nombre,
                'gap_promedio': gap_avg,
                'gap_minimo': gap_min,
                'gap_maximo': gap_max,
                'usdt_promedio': usdt_avg,
                'cierre_usdt': cierre_usdt, # Este es el dato filtrado
                'volatilidad': gap_max - gap_min,
                'registros': len(datos_dia)
            })
        
        return summary
    
    # --- FUNCIONES AUXILIARES (Sin cambios) ---
    def get_hourly_patterns(self):
        """
        Analiza patrones horarios con VALIDACIÓN de datos
        """
        query = """
            SELECT 
                CAST(substr(hora, 1, 2) AS INTEGER) as hour_of_day,
                AVG(gap_ccl) as gap_promedio,
                COUNT(*) as registros
            FROM p2p_history
            WHERE gap_ccl IS NOT NULL 
            AND hora IS NOT NULL
            AND length(hora) >= 2
            GROUP BY hour_of_day
            HAVING registros >= 5
            ORDER BY hour_of_day
        """
        
        try:
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            patterns = {}
            for hour, gap_avg, count in results:
                # Validar que la hora sea razonable (0-23)
                if 0 <= hour <= 23:
                    patterns[hour] = {
                        'gap': float(gap_avg) if gap_avg else 0.0,
                        'registros': int(count)
                    }
            
            return patterns
        except Exception as e:
            print(f"⚠️ Error en get_hourly_patterns: {e}")
            return {}
    
    def get_best_trading_time(self):
        """
        Encuentra el mejor momento del día para operar
        CON MANEJO DE ERRORES
        """
        patterns = self.get_hourly_patterns()
        
        # Si no hay datos suficientes, devolver None
        if not patterns or len(patterns) < 3:
            print("⚠️ Datos insuficientes para calcular mejor hora")
            return None
        
        try:
            # Ordenar por GAP promedio (mayor gap = mejor oportunidad)
            best_hour = max(patterns.items(), key=lambda x: x[1]['gap'])
            worst_hour = min(patterns.items(), key=lambda x: x[1]['gap'])
            
            return {
                'mejor_hora': int(best_hour[0]),
                'mejor_gap': float(best_hour[1]['gap']),
                'peor_hora': int(worst_hour[0]),
                'peor_gap': float(worst_hour[1]['gap']),
                'total_horas': len(patterns)
            }
        except Exception as e:
            print(f"⚠️ Error calculando mejor hora: {e}")
            return None
    
    def get_volatility_index(self, days=7):
        limit = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        self.cursor.execute("SELECT gap_ccl FROM p2p_history WHERE fecha >= ? AND gap_ccl IS NOT NULL", (limit,))
        gaps = [r[0] for r in self.cursor.fetchall()]
        if len(gaps) < 2: return None
        return {'desviacion_estandar': statistics.stdev(gaps), 'promedio': statistics.mean(gaps)}
    
    def get_current_vs_average(self):
        vol = self.get_volatility_index(7)
        if not vol: return None
        self.cursor.execute("SELECT gap_ccl, usdt_sell_p5 FROM p2p_history ORDER BY fecha DESC, hora DESC LIMIT 1")
        res = self.cursor.fetchone()
        if not res: return None
        gap, usdt = res
        prom = vol['promedio']
        dev = vol['desviacion_estandar']
        return {
            'gap_actual': gap, 'gap_promedio': prom, 
            'z_score': (gap - prom)/dev if dev > 0 else 0, 'usdt_actual': usdt
        }
    
    def get_trend_direction(self, hours=24):
        limit = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("SELECT gap_ccl FROM p2p_history WHERE fecha || ' ' || hora >= ? ORDER BY fecha, hora", (limit,))
        gaps = [r[0] for r in self.cursor.fetchall() if r[0]]
        if len(gaps) < 10: return {'direccion': 'estable', 'cambio': 0, 'color': '#3498db'}
        half = len(gaps)//2
        dif = statistics.mean(gaps[half:]) - statistics.mean(gaps[:half])
        col = '#e74c3c' if dif > 0 else ('#2ecc71' if dif < 0 else '#3498db')
        return {'direccion': 'subiendo' if dif > 0 else 'bajando', 'cambio': dif, 'color': col}

    def get_dashboard_metrics(self):
        try:
            summary = self.get_daily_summary(7)
            return {
                'status': 'success',
                'summary_7days': summary,
                'volatility': self.get_volatility_index(7),
                'current_vs_avg': self.get_current_vs_average(),
                'trend_24h': self.get_trend_direction(24),
                'best_trading_time': self.get_best_trading_time(),
                'total_registros': sum(d['registros'] for d in summary)
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
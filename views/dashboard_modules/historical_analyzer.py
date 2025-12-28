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
    """
    Analizador de datos históricos de P2P con métricas avanzadas
    """
    
    def __init__(self, db_connection):
        self.conn = db_connection
        self.cursor = db_connection.cursor()
        self.cache = {}
        self.cache_timestamp = None
        
    def get_timeline_data(self, days=7):
        """
        Obtiene datos de línea temporal para gráfico
        Devuelve lista de puntos (fecha, hora, gap_ccl, usdt_price, ccl_price)
        """
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
            if gap is not None and usdt is not None:
                timeline.append({
                    'fecha': fecha,
                    'hora': hora,
                    'datetime': f"{fecha} {hora}",
                    'gap': gap,
                    'usdt': usdt,
                    'ccl': ccl,
                    'mep': mep
                })
        
        return timeline
    
    def get_daily_summary(self, days=7):
        """
        Resumen diario: promedio, min, max de GAP por día
        Devuelve lista ordenada de más reciente a más antiguo
        """
        fecha_limite = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = """
            SELECT 
                fecha,
                AVG(gap_ccl) as gap_promedio,
                MIN(gap_ccl) as gap_minimo,
                MAX(gap_ccl) as gap_maximo,
                AVG(usdt_sell_p5) as usdt_promedio,
                AVG(ccl) as ccl_promedio,
                COUNT(*) as registros
            FROM p2p_history
            WHERE fecha >= ? AND gap_ccl IS NOT NULL
            GROUP BY fecha
            ORDER BY fecha DESC
        """
        
        self.cursor.execute(query, (fecha_limite,))
        results = self.cursor.fetchall()
        
        summary = []
        for fecha, gap_avg, gap_min, gap_max, usdt_avg, ccl_avg, count in results:
            # Calcular día de la semana
            try:
                dt = datetime.strptime(fecha, "%Y-%m-%d")
                dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
                dia_nombre = dias_semana[dt.weekday()]
            except:
                dia_nombre = "---"
            
            summary.append({
                'fecha': fecha,
                'dia_nombre': dia_nombre,
                'gap_promedio': gap_avg,
                'gap_minimo': gap_min,
                'gap_maximo': gap_max,
                'usdt_promedio': usdt_avg,
                'ccl_promedio': ccl_avg,
                'volatilidad': gap_max - gap_min,
                'registros': count
            })
        
        return summary
    
    def get_hourly_patterns(self):
        """
        Analiza patrones horarios: ¿A qué hora es mejor operar?
        Devuelve diccionario {hora: gap_promedio}
        """
        query = """
            SELECT 
                CAST(substr(hora, 1, 2) AS INTEGER) as hour_of_day,
                AVG(gap_ccl) as gap_promedio,
                COUNT(*) as registros
            FROM p2p_history
            WHERE gap_ccl IS NOT NULL
            GROUP BY hour_of_day
            HAVING registros > 10
            ORDER BY hour_of_day
        """
        
        self.cursor.execute(query)
        results = self.cursor.fetchall()
        
        patterns = {}
        for hour, gap_avg, count in results:
            patterns[hour] = {
                'gap': gap_avg,
                'registros': count
            }
        
        return patterns
    
    def get_best_trading_time(self):
        """
        Encuentra el mejor momento del día para operar
        """
        patterns = self.get_hourly_patterns()
        
        if not patterns:
            return None
        
        # Ordenar por GAP promedio (mayor es mejor)
        best_hour = max(patterns.items(), key=lambda x: x[1]['gap'])
        worst_hour = min(patterns.items(), key=lambda x: x[1]['gap'])
        
        return {
            'mejor_hora': best_hour[0],
            'mejor_gap': best_hour[1]['gap'],
            'peor_hora': worst_hour[0],
            'peor_gap': worst_hour[1]['gap']
        }
    
    def get_volatility_index(self, days=7):
        """
        Calcula índice de volatilidad (desviación estándar del GAP)
        Útil para detectar momentos de alta oportunidad
        """
        fecha_limite = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        query = """
            SELECT gap_ccl
            FROM p2p_history
            WHERE fecha >= ? AND gap_ccl IS NOT NULL
        """
        
        self.cursor.execute(query, (fecha_limite,))
        gaps = [row[0] for row in self.cursor.fetchall()]
        
        if len(gaps) < 2:
            return None
        
        return {
            'desviacion_estandar': statistics.stdev(gaps),
            'rango': max(gaps) - min(gaps),
            'promedio': statistics.mean(gaps),
            'mediana': statistics.median(gaps)
        }
    
    def get_current_vs_average(self):
        """
        Compara situación actual vs promedio histórico
        Devuelve si estamos arriba/abajo del promedio
        """
        # Promedio de últimos 7 días
        vol = self.get_volatility_index(7)
        if not vol:
            return None
        
        # Último registro
        self.cursor.execute("""
            SELECT gap_ccl, usdt_sell_p5
            FROM p2p_history
            ORDER BY fecha DESC, hora DESC
            LIMIT 1
        """)
        
        result = self.cursor.fetchone()
        if not result:
            return None
        
        gap_actual, usdt_actual = result
        
        promedio = vol['promedio']
        desviacion = vol['desviacion_estandar']
        
        # Calcular z-score
        z_score = (gap_actual - promedio) / desviacion if desviacion > 0 else 0
        
        return {
            'gap_actual': gap_actual,
            'gap_promedio': promedio,
            'diferencia': gap_actual - promedio,
            'diferencia_pct': ((gap_actual / promedio) - 1) * 100 if promedio != 0 else 0,
            'z_score': z_score,
            'usdt_actual': usdt_actual
        }
    
    def get_trend_direction(self, hours=24):
        """
        Detecta tendencia en las últimas horas
        Retorna: 'subiendo', 'bajando', 'estable'
        """
        fecha_limite = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        
        query = """
            SELECT gap_ccl
            FROM p2p_history
            WHERE fecha || ' ' || hora >= ?
            ORDER BY fecha ASC, hora ASC
        """
        
        self.cursor.execute(query, (fecha_limite,))
        gaps = [row[0] for row in self.cursor.fetchall() if row[0] is not None]
        
        if len(gaps) < 10:
            return 'insuficientes_datos'
        
        # Dividir en dos mitades
        primera_mitad = gaps[:len(gaps)//2]
        segunda_mitad = gaps[len(gaps)//2:]
        
        promedio_primera = statistics.mean(primera_mitad)
        promedio_segunda = statistics.mean(segunda_mitad)
        
        diferencia = promedio_segunda - promedio_primera
        
        # Umbral de cambio significativo
        if abs(diferencia) < 0.1:
            return {
                'direccion': 'estable',
                'cambio': diferencia,
                'color': '#3498db'
            }
        elif diferencia > 0:
            return {
                'direccion': 'subiendo',
                'cambio': diferencia,
                'color': '#2ecc71'
            }
        else:
            return {
                'direccion': 'bajando',
                'cambio': diferencia,
                'color': '#e74c3c'
            }
    
    def get_dashboard_metrics(self):
        """
        Obtiene todas las métricas relevantes para el dashboard
        Esta es la función principal que debes llamar
        """
        try:
            summary = self.get_daily_summary(7)
            volatility = self.get_volatility_index(7)
            current = self.get_current_vs_average()
            trend = self.get_trend_direction(24)
            best_time = self.get_best_trading_time()
            
            return {
                'status': 'success',
                'summary_7days': summary,
                'volatility': volatility,
                'current_vs_avg': current,
                'trend_24h': trend,
                'best_trading_time': best_time,
                'total_registros': sum(d['registros'] for d in summary)
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_miniature_timeline(self, days=5):
        """
        Versión compacta de timeline para UI pequeñas
        Devuelve solo 1 punto por hora
        """
        timeline = self.get_timeline_data(days)
        
        if not timeline:
            return []
        
        # Agrupar por hora
        hourly_data = defaultdict(list)
        
        for point in timeline:
            # Extraer hora (primeras 13 caracteres: YYYY-MM-DD HH)
            hour_key = point['datetime'][:13]
            hourly_data[hour_key].append(point)
        
        # Promediar cada hora
        miniature = []
        for hour_key in sorted(hourly_data.keys()):
            points = hourly_data[hour_key]
            avg_gap = statistics.mean(p['gap'] for p in points)
            avg_usdt = statistics.mean(p['usdt'] for p in points)
            
            miniature.append({
                'datetime': hour_key,
                'gap': avg_gap,
                'usdt': avg_usdt
            })
        
        return miniature
"""
📊 MÓDULO DE ANÁLISIS HISTÓRICO P2P (VERSIÓN BLINDADA)
Analiza datos históricos de USDT Binance P2P vs CCL/MEP.
Garantiza que siempre haya un dato para mostrar.
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
        
        try:
            self.cursor.execute(query, (fecha_limite,))
            results = self.cursor.fetchall()
        except:
            return []
        
        timeline = []
        for fecha, hora, gap, usdt, ccl, mep in results:
            # Validamos que gap sea un número
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
        """Resumen diario con LÓGICA DE CIERRE BANCARIO"""
        raw_data = self.get_timeline_data(days)
        
        if not raw_data: return []

        grouped_data = defaultdict(list)
        for row in raw_data:
            grouped_data[row['fecha']].append(row)

        summary = []
        
        for fecha in sorted(grouped_data.keys(), reverse=True):
            datos_dia = grouped_data[fecha]
            if not datos_dia: continue

            gaps = [d['gap'] for d in datos_dia if d['gap'] is not None]
            if not gaps: continue

            usdts = [d['usdt'] for d in datos_dia if d['usdt'] > 0]
            
            gap_avg = statistics.mean(gaps)
            gap_min = min(gaps)
            gap_max = max(gaps)
            usdt_avg = statistics.mean(usdts) if usdts else 0
            
            # --- CIERRE ---
            cierre_usdt = 0.0
            encontrado = False
            
            # 1. Ventana Bancaria (17:00 - 18:30)
            for d in datos_dia:
                h = d.get('hora', '00:00:00')
                if "17:00:00" <= h <= "18:30:59" and d['usdt'] > 100:
                    cierre_usdt = d['usdt']
                    encontrado = True
            
            # 2. Último dato (Fallback)
            if not encontrado or cierre_usdt == 0:
                for d in reversed(datos_dia):
                    if d['usdt'] > 100:
                        cierre_usdt = d['usdt']
                        break

            try:
                dt = datetime.strptime(fecha, "%Y-%m-%d")
                dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
                nom = dias[dt.weekday()]
            except: nom = "---"

            summary.append({
                'fecha': fecha,
                'dia_nombre': nom,
                'gap_promedio': gap_avg,
                'cierre_usdt': cierre_usdt,
                'volatilidad': gap_max - gap_min,
                'registros': len(datos_dia)
            })
        
        return summary
    
    def get_hourly_patterns(self):
        """Patrones horarios BLINDADOS"""
        # Usamos COALESCE para evitar nulos y quitamos el HAVING
        query = """
            SELECT 
                CAST(substr(hora, 1, 2) AS INTEGER) as hour,
                AVG(COALESCE(gap_ccl, 0)) as gap, 
                COUNT(*) as c
            FROM p2p_history 
            WHERE gap_ccl IS NOT NULL 
            GROUP BY hour 
            ORDER BY gap DESC
        """
        try:
            self.cursor.execute(query)
            res = self.cursor.fetchall()
            # Convertimos a diccionario: {hora: {'gap': x, 'registros': y}}
            return {r[0]: {'gap': r[1], 'registros': r[2]} for r in res}
        except:
            return {}
    
    def get_best_trading_time(self):
        """Devuelve la mejor hora o la hora ACTUAL si no hay datos"""
        patterns = self.get_hourly_patterns()
        
        if not patterns:
            # SI FALLA TODO: Devolvemos la hora actual
            now_h = datetime.now().hour
            return {'mejor_hora': now_h, 'mejor_gap': 0.0}
            
        try:
            # Buscamos la hora con mayor GAP promedio
            best_h = max(patterns.items(), key=lambda x: x[1]['gap'])
            return {'mejor_hora': best_h[0], 'mejor_gap': best_h[1]['gap']}
        except:
            now_h = datetime.now().hour
            return {'mejor_hora': now_h, 'mejor_gap': 0.0}
    
    def get_volatility_index(self, days=7):
        try:
            l = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            self.cursor.execute("SELECT gap_ccl FROM p2p_history WHERE fecha >= ? AND gap_ccl IS NOT NULL", (l,))
            g = [r[0] for r in self.cursor.fetchall()]
            if len(g) < 2: return {'desviacion_estandar': 0.0, 'promedio': 0.0}
            return {'desviacion_estandar': statistics.stdev(g), 'promedio': statistics.mean(g)}
        except:
            return {'desviacion_estandar': 0.0, 'promedio': 0.0}
    
    def get_current_vs_average(self):
        try:
            vol = self.get_volatility_index(7)
            self.cursor.execute("SELECT gap_ccl, usdt_sell_p5 FROM p2p_history ORDER BY fecha DESC, hora DESC LIMIT 1")
            r = self.cursor.fetchone()
            if not r: return {'gap_actual': 0, 'gap_promedio': 0, 'z_score': 0, 'usdt_actual': 0}
            g, u = r
            p = vol['promedio']
            d = vol['desviacion_estandar']
            z = (g - p)/d if d > 0 else 0
            return {'gap_actual': g, 'gap_promedio': p, 'z_score': z, 'usdt_actual': u}
        except:
            return {'gap_actual': 0, 'gap_promedio': 0, 'z_score': 0, 'usdt_actual': 0}
    
    def get_trend_direction(self, hours=24):
        try:
            l = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("SELECT gap_ccl FROM p2p_history WHERE fecha || ' ' || hora >= ? ORDER BY fecha, hora", (l,))
            g = [r[0] for r in self.cursor.fetchall() if r[0] is not None]
            
            if len(g) < 5: return {'direccion': 'estable', 'cambio': 0, 'color': '#3498db'}
            
            # Tendencia simple: Promedio últimos 5 vs Promedio primeros 5
            fin = statistics.mean(g[-5:])
            ini = statistics.mean(g[:5])
            dif = fin - ini
            
            c = '#e74c3c' if dif > 0 else ('#2ecc71' if dif < 0 else '#3498db')
            return {'direccion': 'subiendo' if dif > 0 else 'bajando', 'cambio': abs(dif), 'color': c}
        except:
            return {'direccion': 'estable', 'cambio': 0, 'color': '#3498db'}

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
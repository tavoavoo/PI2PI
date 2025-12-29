import sqlite3
from datetime import datetime, time

class CCLManager:
    def __init__(self, db_connection):
        self.conn = db_connection
        self.cursor = db_connection.cursor()
        self.ccl_congelado = None
        self.fecha_congelamiento = None
        
        # Asegurar tabla de configuración
        self._init_config_table()

    def _init_config_table(self):
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_ccl (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    timestamp TEXT
                )
            """)
            self.conn.commit()
        except: pass

    def es_horario_mercado(self):
        """
        Devuelve True si estamos en horario bancario:
        Lunes a Viernes de 11:00 a 17:00 hs.
        """
        ahora = datetime.now()
        dia_semana = ahora.weekday() # 0=Lun, 5=Sab, 6=Dom
        hora_actual = ahora.time()

        # 1. Fin de semana (Sábado o Domingo)
        if dia_semana >= 5:
            return False
        
        # 2. Fuera de horario (Antes de las 11 o después de las 17)
        if hora_actual < time(11, 0) or hora_actual > time(17, 0):
            return False
            
        return True

    def obtener_ccl_inteligente(self, scraper_engine):
        """
        El cerebro de la operación:
        - Si el mercado está abierto -> Scrapea y guarda.
        - Si el mercado está cerrado -> Recupera el último cierre guardado.
        """
        ahora = datetime.now()

        if self.es_horario_mercado():
            # --- MERCADO ABIERTO ---
            try:
                datos = scraper_engine.obtener_precios_vivo()
                if datos and datos.get("ccl") and datos["ccl"][0] > 0:
                    precio_vivo = datos["ccl"][0]
                    pct_vivo = datos["ccl"][1]
                    
                    # Guardamos este precio como "Último Cierre Conocido"
                    self._guardar_cierre(precio_vivo)
                    
                    return {
                        "precio": precio_vivo,
                        "pct": pct_vivo,
                        "tipo": "VIVO",  # Mercado activo
                        "timestamp": ahora
                    }
            except Exception as e:
                print(f"Error scraping vivo: {e}")
        
        # --- MERCADO CERRADO O FALLO DE SCRAPER ---
        # Si llegamos acá, usamos la "Referencia Congelada"
        precio_congelado = self._cargar_ultimo_cierre()
        
        return {
            "precio": precio_congelado,
            "pct": "0.00%", # En fin de semana el cambio es 0
            "tipo": "CONGELADO", # Mercado cerrado
            "timestamp": ahora
        }

    def _guardar_cierre(self, precio):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("INSERT OR REPLACE INTO config_ccl (key, value, timestamp) VALUES (?, ?, ?)", 
                               ("ultimo_cierre", str(precio), ts))
            self.conn.commit()
        except: pass

    def _cargar_ultimo_cierre(self):
        try:
            self.cursor.execute("SELECT value FROM config_ccl WHERE key='ultimo_cierre'")
            res = self.cursor.fetchone()
            if res:
                return float(res[0])
            
            # Si no hay config, buscamos el último histórico
            self.cursor.execute("SELECT ccl FROM p2p_history ORDER BY id DESC LIMIT 1")
            res_hist = self.cursor.fetchone()
            if res_hist:
                return float(res_hist[0])
                
        except: pass
        return 0.0 # Peor caso
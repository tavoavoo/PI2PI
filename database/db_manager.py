import sqlite3

class DBManager:
    def __init__(self, db_name="p2p_data.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA journal_mode=WAL;") 
        self.conn.commit()
        self.init_db()
        self.check_and_seed_accounts()
        
    def setup_blacklist_table(self):
        """Crea la tabla de usuarios baneados si no existe"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS p2p_blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT UNIQUE NOT NULL,
                fecha_baneo TEXT NOT NULL,
                motivo TEXT
            )
        """)
        self.conn.commit()

    def init_db(self):
        # Definición de tablas (Nota que 'operaciones' ahora incluye 'rol')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS cuentas (id INTEGER PRIMARY KEY, nombre TEXT, tipo TEXT, limite_mensual REAL, acumulado_actual REAL, estado TEXT, saldo REAL DEFAULT 0, moneda TEXT DEFAULT 'ARS')''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS operaciones (id INTEGER PRIMARY KEY, fecha TEXT, nickname TEXT, tipo TEXT, banco TEXT, monto_ars REAL, monto_usdt REAL, cotizacion REAL, fee REAL DEFAULT 0, moneda TEXT DEFAULT 'ARS', archivado INTEGER DEFAULT 0, order_id TEXT, rol TEXT DEFAULT '---')''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS cierres (id INTEGER PRIMARY KEY, fecha_cierre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value REAL)''')
        
        # --- MIGRACIONES (Para actualizar tu DB existente sin borrar datos) ---
        try: self.cursor.execute("ALTER TABLE cuentas ADD COLUMN moneda TEXT DEFAULT 'ARS'")
        except: pass
        try: self.cursor.execute("ALTER TABLE operaciones ADD COLUMN moneda TEXT DEFAULT 'ARS'")
        except: pass
        try: self.cursor.execute("ALTER TABLE operaciones ADD COLUMN archivado INTEGER DEFAULT 0")
        except: pass
        try: self.cursor.execute("ALTER TABLE operaciones ADD COLUMN order_id TEXT") 
        except: pass
        
        # MIGRACIÓN CLAVE: AGREGAR ROL
        try: self.cursor.execute("ALTER TABLE operaciones ADD COLUMN rol TEXT DEFAULT '---'") 
        except: pass

        self.cursor.execute("UPDATE cuentas SET limite_mensual = 45000000 WHERE moneda = 'ARS'")
        
        # --- CONFIGURACIÓN DE VALORES POR DEFECTO (AQUÍ ESTÁ EL CAMBIO) ---
        
        # Stock inicial en 0 si no existe
        self.cursor.execute("SELECT value FROM config WHERE key='stock_usdt'")
        if not self.cursor.fetchone(): 
            self.cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('stock_usdt', 0.0))
        
        # 1. MAKER FEE (Bronce 0.16% = 0.0016)
        # Seteamos las dos llaves para evitar conflictos futuros
        self.cursor.execute("SELECT value FROM config WHERE key='comision_maker'")
        if not self.cursor.fetchone(): 
            self.cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('comision_maker', 0.0016))

        self.cursor.execute("SELECT value FROM config WHERE key='maker_fee'")
        if not self.cursor.fetchone(): 
            self.cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('maker_fee', 0.0016))

        # 2. TAKER FEE (Estándar 0.07% = 0.0007)
        self.cursor.execute("SELECT value FROM config WHERE key='taker_fee'")
        if not self.cursor.fetchone(): 
            self.cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('taker_fee', 0.0007))

        self.conn.commit()

    def check_and_seed_accounts(self):
        self.cursor.execute("SELECT count(*) FROM cuentas")
        if self.cursor.fetchone()[0] == 0:
            LIMITE_SEGURO = 45000000 
            bancos = ["Galicia", "Santander", "Banco Nación", "Cuenta DNI", "Brubank", "Prex", "Lemon Cash", "Naranja X", "MercadoPago", "Ualá", "Personal Pay"]
            for banco in bancos: 
                self.cursor.execute("INSERT INTO cuentas (nombre, tipo, limite_mensual, acumulado_actual, estado, saldo, moneda) VALUES (?, 'Banco', ?, 0, 'Activo', 0, 'ARS')", (banco, LIMITE_SEGURO))
            self.conn.commit()
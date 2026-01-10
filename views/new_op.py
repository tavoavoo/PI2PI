import customtkinter as ctk
from datetime import datetime
from utils.ui_components import ModernModal

class NuevaOperacionView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.c = controller
        
        # --- AUTO-MIGRACIÓN (Agregar columna notas si no existe) ---
        self.verificar_columna_notas()

        # Título
        ctk.CTkLabel(self, text="Carga Manual de Operación", font=("Arial", 24, "bold")).pack(pady=20)
        
        # Formulario
        form_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=10)
        form_frame.pack(fill="both", expand=True, padx=40, pady=10)
        
        # --- FILA 1: TIPO Y FECHA ---
        ctk.CTkLabel(form_frame, text="Tipo de Movimiento:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=20, pady=(20,5), sticky="w")
        self.tipo_var = ctk.StringVar(value="Compra")
        self.combo_tipo = ctk.CTkOptionMenu(form_frame, variable=self.tipo_var, values=["Compra", "Venta"])
        self.combo_tipo.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.lbl_tipo_desc = ctk.CTkLabel(form_frame, text="Compra: Sale Pesos (Gasto/Inversión)\nVenta: Sale Crypto (Retiro/Venta)", font=("Arial", 11), text_color="gray")
        self.lbl_tipo_desc.grid(row=2, column=0, padx=20, pady=0, sticky="w")

        ctk.CTkLabel(form_frame, text="Fecha (dd/mm/aaaa):", font=("Arial", 14, "bold")).grid(row=0, column=1, padx=20, pady=(20,5), sticky="w")
        self.entry_fecha = ctk.CTkEntry(form_frame)
        self.entry_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.entry_fecha.grid(row=1, column=1, padx=20, pady=5, sticky="ew")

        # --- FILA 2: MONTOS ---
        ctk.CTkLabel(form_frame, text="Cantidad USDT (0 si es solo Pesos):", font=("Arial", 14, "bold")).grid(row=3, column=0, padx=20, pady=(20,5), sticky="w")
        self.entry_usdt = ctk.CTkEntry(form_frame, placeholder_text="0.00")
        self.entry_usdt.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        
        ctk.CTkLabel(form_frame, text="Monto Total ARS:", font=("Arial", 14, "bold")).grid(row=3, column=1, padx=20, pady=(20,5), sticky="w")
        self.entry_ars = ctk.CTkEntry(form_frame, placeholder_text="0.00")
        self.entry_ars.grid(row=4, column=1, padx=20, pady=5, sticky="ew")

        # --- FILA 3: COTIZACIÓN Y BANCO ---
        ctk.CTkLabel(form_frame, text="Cotización / Precio (Opcional):", font=("Arial", 14, "bold")).grid(row=5, column=0, padx=20, pady=(20,5), sticky="w")
        self.entry_cot = ctk.CTkEntry(form_frame, placeholder_text="Ej: 1530")
        self.entry_cot.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        ctk.CTkLabel(form_frame, text="Banco / Caja:", font=("Arial", 14, "bold")).grid(row=5, column=1, padx=20, pady=(20,5), sticky="w")
        self.c.cursor.execute("SELECT nombre FROM cuentas WHERE estado='Activo' ORDER BY nombre")
        bancos = [b[0] for b in self.c.cursor.fetchall()]
        if not bancos: bancos = ["Efectivo", "Otro"]
        else: bancos.append("Otro")
        self.combo_banco = ctk.CTkOptionMenu(form_frame, values=bancos)
        self.combo_banco.grid(row=6, column=1, padx=20, pady=5, sticky="ew")

        # --- FILA 4: NOTAS INTERNAS (NUEVO) ---
        ctk.CTkLabel(form_frame, text="Notas Internas (SOLO PARA TI):", font=("Arial", 14, "bold"), text_color="#3498db").grid(row=7, column=0, columnspan=2, padx=20, pady=(20,5), sticky="w")
        self.entry_notas = ctk.CTkEntry(form_frame, placeholder_text="Ej: Regalo mamá, Devolución préstamo, Envío Perú... (Esto NO sale en el reporte)")
        self.entry_notas.grid(row=8, column=0, columnspan=2, padx=20, pady=5, sticky="ew")

        # --- FILA 5: CHECKBOX PERSONAL ---
        self.chk_personal_var = ctk.IntVar(value=0)
        self.chk_personal = ctk.CTkCheckBox(form_frame, text="Es Movimiento PERSONAL / CAPITAL (No Comercial)", variable=self.chk_personal_var, font=("Arial", 12, "bold"), text_color="#9b59b6")
        self.chk_personal.grid(row=9, column=0, columnspan=2, padx=20, pady=20, sticky="w")

        # Botón Guardar
        ctk.CTkButton(self, text="GUARDAR OPERACIÓN", width=200, height=50, fg_color="#27ae60", hover_color="#2ecc71", font=("Arial", 14, "bold"), command=self.guardar).pack(pady=10)

    def verificar_columna_notas(self):
        """Revisa si existe la columna notas, si no, la agrega."""
        try:
            self.c.cursor.execute("PRAGMA table_info(operaciones)")
            columns = [info[1] for info in self.c.cursor.fetchall()]
            if "notas" not in columns:
                self.c.cursor.execute("ALTER TABLE operaciones ADD COLUMN notas TEXT")
                self.c.conn.commit()
        except Exception as e: print(f"DB Warning: {e}")

    def guardar(self):
        try:
            tipo = self.tipo_var.get()
            fecha_str = self.entry_fecha.get().strip()
            
            # Parsear Fecha
            try:
                dt_obj = datetime.strptime(fecha_str, "%d/%m/%Y")
                fecha_iso = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except:
                self.c.show_error("Error", "Formato de fecha inválido. Usa dd/mm/aaaa")
                return

            # Parsear Números
            try:
                usdt = float(self.entry_usdt.get().strip() or 0)
                ars = float(self.entry_ars.get().strip() or 0)
                cot_str = self.entry_cot.get().strip()
                cot = float(cot_str) if cot_str else 0.0
                
                if cot == 0 and usdt > 0 and ars > 0: cot = ars / usdt
            except:
                self.c.show_error("Error", "Montos inválidos. Usa punto para decimales.")
                return

            banco = self.combo_banco.get()
            es_personal = self.chk_personal_var.get()
            notas = self.entry_notas.get().strip() # Capturamos la nota
            
            # --- LÓGICA DE SALDOS ---
            if banco != "Otro" and banco != "Efectivo": 
                if tipo == "Compra": 
                    self.c.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (ars, banco))
                else: 
                    self.c.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (ars, banco))
            
            if usdt > 0:
                if tipo == "Compra": 
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) + ? WHERE key='stock_usdt'", (usdt,))
                else: 
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) - ? WHERE key='stock_usdt'", (usdt,))

            # --- GUARDADO EN BD (Incluyendo Notas) ---
            manual_id = f"MAN-{int(datetime.now().timestamp())}"
            
            # Nota para la DB: Guardamos la nota en el campo 'notas' y TAMBIÉN concatenada en 'nickname' 
            # para que sea fácil de ver en el historial si quieres, pero el reporte limpia eso.
            # O mejor, guardamos limpio.
            
            self.c.cursor.execute("""
                INSERT INTO operaciones 
                (fecha, nickname, tipo, banco, monto_ars, monto_usdt, cotizacion, fee, moneda, order_id, rol, archivado, es_personal, notas) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'ARS', ?, 'Manual', 0, ?, ?)
            """, (fecha_iso, "Carga Manual", tipo, banco, ars, usdt, cot, manual_id, es_personal, notas))
            
            self.c.conn.commit()
            self.c.refresh_all_views() 
            
            self.c.show_info("Éxito", "Operación registrada.")
            
            # Limpiar campos clave
            self.entry_usdt.delete(0, "end")
            self.entry_ars.delete(0, "end")
            self.entry_cot.delete(0, "end")
            self.entry_notas.delete(0, "end")

        except Exception as e:
            self.c.show_error("Error Crítico", str(e))
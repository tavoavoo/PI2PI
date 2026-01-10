import customtkinter as ctk
from datetime import datetime, timedelta
from utils.ui_components import ModernModal, CustomDialog

# --- VENTANA MODAL DE GESTIÓN (Mantenida intacta) ---
class TransactionDialog(ctk.CTkToplevel):
    def __init__(self, parent, nombre_cuenta, saldo_actual, on_confirm):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.saldo_actual = saldo_actual
        self.nombre_cuenta = nombre_cuenta
        
        self.title("Gestión de Fondos")
        self.geometry("400x380")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 190
        self.geometry(f"+{x}+{y}")
        self.configure(fg_color="#1a1a1a")

        ctk.CTkLabel(self, text=f"GESTIONAR: {nombre_cuenta}", font=("Arial", 16, "bold"), text_color="#f39c12").pack(pady=(20, 5))
        ctk.CTkLabel(self, text=f"Saldo Actual: {saldo_actual:,.2f}", font=("Arial", 12), text_color="gray").pack(pady=(0, 20))

        self.accion_var = ctk.StringVar(value="INGRESAR")
        self.seg_btn = ctk.CTkSegmentedButton(self, values=["INGRESAR", "RETIRAR", "CORREGIR"], 
                                                variable=self.accion_var, command=self.update_ui,
                                                selected_color="#27ae60", selected_hover_color="#2ecc71")
        self.seg_btn.pack(pady=10, padx=20, fill="x")

        self.entry_monto = ctk.CTkEntry(self, placeholder_text="Monto...", font=("Arial", 14), height=40, justify="center")
        self.entry_monto.pack(pady=10, padx=40, fill="x")
        self.entry_monto.bind("<KeyRelease>", self.calc_preview)

        self.lbl_preview = ctk.CTkLabel(self, text="Nuevo Saldo: ---", font=("Arial", 13, "bold"), text_color="white")
        self.lbl_preview.pack(pady=10)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)
        
        self.btn_confirm = ctk.CTkButton(btn_frame, text="CONFIRMAR", font=("Arial", 12, "bold"), height=40, 
                                         fg_color="#27ae60", hover_color="#219150", command=self.confirmar)
        self.btn_confirm.pack(side="right", expand=True, fill="x", padx=(5,0))
        
        ctk.CTkButton(btn_frame, text="CANCELAR", font=("Arial", 12), height=40, 
                      fg_color="#444", hover_color="#333", command=self.destroy).pack(side="left", expand=True, fill="x", padx=(0,5))

        self.update_ui("INGRESAR")

    def update_ui(self, value):
        color = "#27ae60" # Verde
        if value == "RETIRAR": color = "#c0392b" # Rojo
        elif value == "CORREGIR": color = "#2980b9" # Azul
        
        self.seg_btn.configure(selected_color=color, selected_hover_color=color)
        self.btn_confirm.configure(fg_color=color, hover_color=color)
        self.calc_preview()

    def calc_preview(self, event=None):
        try:
            txt = self.entry_monto.get().replace(',', '')
            if not txt: 
                self.lbl_preview.configure(text="Nuevo Saldo: ---")
                return
            
            monto = float(txt)
            accion = self.accion_var.get()
            nuevo = self.saldo_actual
            
            if accion == "INGRESAR": nuevo += monto
            elif accion == "RETIRAR": nuevo -= monto
            elif accion == "CORREGIR": nuevo = monto
            
            self.lbl_preview.configure(text=f"Nuevo Saldo: {nuevo:,.2f}")
        except:
            self.lbl_preview.configure(text="Monto inválido")

    def confirmar(self):
        try:
            monto = float(self.entry_monto.get().replace(',', ''))
            accion = self.accion_var.get()
            self.on_confirm(accion, monto)
            self.destroy()
        except: pass

# --- VISTA PRINCIPAL (Con Lógica de Bloqueo Inyectada) ---
class TesoreriaView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # Auto-Migración (Bloqueos)
        self.verificar_db()

        # Header
        ctk.CTkLabel(self, text="TESORERÍA & GESTIÓN DE CAPITAL", font=("Arial", 22, "bold"), text_color="#f39c12").pack(anchor="w", padx=20, pady=20)
        
        # --- SALDOS GENERALES ---
        self.info_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.info_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.info_frame.grid_columnconfigure((0,1), weight=1)
        
        # ARS es solo lectura (suma de bancos)
        # Cambio: Ahora muestra CAPITAL DISPONIBLE REAL (Restando bloqueados)
        self.lbl_saldo_ars = self.mk_card(0, "CAPITAL OPERATIVO (ARS)", None)
        
        # USDT
        self.lbl_saldo_usdt = self.mk_card(1, "STOCK USDT", self.gestionar_usdt)

        # --- LISTA DE CUENTAS ---
        header_list = ctk.CTkFrame(self, fg_color="transparent")
        header_list.pack(fill="x", padx=20)
        ctk.CTkLabel(header_list, text="CUENTA", width=120, anchor="w", font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(header_list, text="SALDO REAL", width=100, anchor="w", font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(header_list, text="LÍMITE FISCAL / ESTADO", width=200, anchor="w", font=("Arial", 11, "bold")).pack(side="left", padx=10)
        
        self.scroll_bancos = ctk.CTkScrollableFrame(self, fg_color="#101010")
        self.scroll_bancos.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.bank_widgets = []
        self.timers = {} # Cache para cronómetros
        
        # Crear slots vacíos (Pool de widgets para performance)
        for _ in range(15):
            row = ctk.CTkFrame(self.scroll_bancos, fg_color="transparent")
            
            # Nombre
            lbl_nom = ctk.CTkLabel(row, text="", width=120, anchor="w", font=("Arial", 12, "bold"))
            lbl_nom.pack(side="left")
            
            # Saldo
            lbl_saldo = ctk.CTkLabel(row, text="", width=100, anchor="w", text_color="#2cc985")
            lbl_saldo.pack(side="left")
            
            # Barra de Progreso
            pb = ctk.CTkProgressBar(row, height=12)
            pb.pack(side="left", fill="x", expand=True, padx=10)
            
            # Etiqueta Límite / Cronómetro
            lbl_limite = ctk.CTkLabel(row, text="", width=100, font=("Arial", 10), text_color="gray", anchor="w")
            lbl_limite.pack(side="left")
            
            # Frame Botones (Para poner Bloquear y Configurar juntos)
            btn_frame = ctk.CTkFrame(row, fg_color="transparent", width=80)
            btn_frame.pack(side="right", padx=5)
            
            # Botón Bloqueo (Dinamico: 🔒 o ⚡)
            btn_lock = ctk.CTkButton(btn_frame, text="🔒", width=30, height=25, fg_color="#c0392b", hover_color="#922b21")
            btn_lock.pack(side="left", padx=2)

            # Botón Config (⚙️)
            btn_conf = ctk.CTkButton(btn_frame, text="⚙️", width=30, height=25, fg_color="#333", hover_color="#444")
            btn_conf.pack(side="left", padx=2)
            
            self.bank_widgets.append({
                "frame": row, "nom": lbl_nom, "saldo": lbl_saldo, "pb": pb, 
                "lim": lbl_limite, "btn_lock": btn_lock, "btn_conf": btn_conf
            })

        self.update_timers_loop() # Iniciar reloj

    def verificar_db(self):
        try:
            self.controller.cursor.execute("PRAGMA table_info(cuentas)")
            cols = [info[1] for info in self.controller.cursor.fetchall()]
            if "bloqueado_hasta" not in cols:
                self.controller.cursor.execute("ALTER TABLE cuentas ADD COLUMN bloqueado_hasta TEXT")
                self.controller.conn.commit()
        except: pass

    def mk_card(self, col, title, cmd):
        f = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        f.grid(row=0, column=col, padx=20, pady=15)
        
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack()
        ctk.CTkLabel(header, text=title, font=("Arial", 12, "bold"), text_color="gray").pack(side="left")
        
        if cmd:
            btn = ctk.CTkButton(header, text="⚙️", width=30, height=20, fg_color="#333", hover_color="#444", command=cmd)
            btn.pack(side="left", padx=10)

        lbl = ctk.CTkLabel(f, text="---", font=("Arial", 24, "bold"), text_color="white")
        lbl.pack()
        return lbl

    # --- LÓGICA GESTIÓN USDT (Igual) ---
    def gestionar_usdt(self):
        current_stock = self.controller.STOCK_USDT
        def aplicar_usdt(accion, monto):
            nuevo_stock = current_stock
            if accion == "INGRESAR": nuevo_stock += monto
            elif accion == "RETIRAR": nuevo_stock -= monto
            elif accion == "CORREGIR": nuevo_stock = monto
            
            self.controller.STOCK_USDT = nuevo_stock
            try:
                self.controller.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('stock_usdt', ?)", (str(nuevo_stock),))
                self.controller.conn.commit()
            except: pass
            self.update_view()

        TransactionDialog(self, "STOCK USDT", current_stock, aplicar_usdt)

    def abrir_modal_gestion(self, nombre_cuenta, saldo_actual):
        def aplicar_banco(accion, monto):
            if accion == "INGRESAR":
                self.controller.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (monto, nombre_cuenta))
            elif accion == "RETIRAR":
                self.controller.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (monto, nombre_cuenta))
            elif accion == "CORREGIR":
                self.controller.cursor.execute("UPDATE cuentas SET saldo = ? WHERE nombre=?", (monto, nombre_cuenta))
            
            self.controller.conn.commit()
            self.update_view()
            
        TransactionDialog(self, nombre_cuenta, saldo_actual, aplicar_banco)

    # --- ACCIONES DE BLOQUEO ---
    def bloquear_24h(self, cid):
        unlock_time = datetime.now() + timedelta(hours=24)
        unlock_str = unlock_time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.controller.cursor.execute("UPDATE cuentas SET bloqueado_hasta = ? WHERE id = ?", (unlock_str, cid))
            self.controller.conn.commit()
            self.update_view()
        except: pass

    def desbloquear(self, cid):
        try:
            self.controller.cursor.execute("UPDATE cuentas SET bloqueado_hasta = NULL WHERE id = ?", (cid,))
            self.controller.conn.commit()
            self.update_view()
        except: pass

    # --- RENDERIZADO PRINCIPAL ---
    def update_view(self):
        # 1. Limpiar timers viejos
        self.timers = {}
        now = datetime.now()

        # 2. Resetear widgets
        for w in self.bank_widgets: w["frame"].pack_forget()
        
        # 3. Datos
        self.controller.cursor.execute("SELECT id, nombre, saldo, limite_mensual, moneda, bloqueado_hasta FROM cuentas WHERE estado='Activo' ORDER BY nombre")
        cuentas = self.controller.cursor.fetchall()
        mes_actual = datetime.now().strftime("%Y-%m")
        
        total_ars_disponible = 0.0 # Solo cuentas NO bloqueadas
        
        for i, (cid, nom, saldo, lim, mon, block_str) in enumerate(cuentas):
            if i >= len(self.bank_widgets): break
            
            # Chequear bloqueo
            es_bloqueado = False
            tiempo_restante = None
            if block_str:
                try:
                    dt_block = datetime.strptime(block_str, "%Y-%m-%d %H:%M:%S")
                    if dt_block > now:
                        es_bloqueado = True
                        tiempo_restante = dt_block
                    else:
                        # Auto-desbloqueo si venció
                        self.controller.cursor.execute("UPDATE cuentas SET bloqueado_hasta = NULL WHERE id = ?", (cid,))
                        self.controller.conn.commit()
                except: pass

            # Sumar al total disponible si es ARS y no está bloqueado
            if mon == 'ARS' and not es_bloqueado:
                total_ars_disponible += saldo

            # Obtener consumo fiscal
            self.controller.cursor.execute("SELECT SUM(monto_ars) FROM operaciones WHERE banco=? AND strftime('%Y-%m', fecha)=?", (nom, mes_actual))
            res = self.controller.cursor.fetchone()
            consumido = res[0] if res[0] else 0.0
            
            # --- RENDER ROW ---
            w = self.bank_widgets[i]
            w["frame"].pack(fill="x", pady=4)
            
            # Estilos según estado
            if es_bloqueado:
                w["frame"].configure(fg_color="#2b1616") # Rojo oscuro fondo
                w["saldo"].configure(text_color="#e74c3c") # Rojo texto
                w["nom"].configure(text_color="#e74c3c")
            else:
                w["frame"].configure(fg_color="transparent")
                w["saldo"].configure(text_color="#2cc985")
                w["nom"].configure(text_color="white")

            simbolo = "S/" if mon == "PEN" else "$" if mon == "ARS" else "u$s"
            w["nom"].configure(text=nom)
            w["saldo"].configure(text=f"{simbolo} {saldo:,.2f}")
            
            # Barra Fiscal
            pct = 0.0
            if lim > 0: pct = consumido / lim
            col_bar = "#2cc985"
            if pct > 0.7: col_bar = "#e3a319"
            if pct > 0.9: col_bar = "#cf3030"
            
            w["pb"].configure(progress_color=col_bar)
            w["pb"].set(min(pct, 1.0))
            
            # Etiqueta Dinámica (Límite o Timer)
            if es_bloqueado:
                # Si está bloqueado, mostramos el timer en lugar del % fiscal
                self.timers[i] = {"expiry": tiempo_restante, "label": w["lim"]} # Guardar para el loop
                w["lim"].configure(text="Calculando...", text_color="#e74c3c", font=("Consolas", 11, "bold"))
                
                # Botón pasa a ser "Rayo" (Desbloquear)
                w["btn_lock"].configure(text="⚡", fg_color="#27ae60", hover_color="#2ecc71", 
                                        command=lambda c=cid: self.desbloquear(c))
            else:
                w["lim"].configure(text=f"{pct*100:.0f}% Fiscal", text_color="gray", font=("Arial", 10))
                
                # Botón pasa a ser "Candado" (Bloquear)
                w["btn_lock"].configure(text="🔒", fg_color="#c0392b", hover_color="#922b21", 
                                        command=lambda c=cid: self.bloquear_24h(c))

            # Botón Config siempre igual
            w["btn_conf"].configure(command=lambda n=nom, s=saldo: self.abrir_modal_gestion(n, s))

        # Actualizar Saldos Globales
        self.lbl_saldo_ars.configure(text=f"$ {total_ars_disponible:,.0f}")
        self.lbl_saldo_usdt.configure(text=f"{self.controller.STOCK_USDT:,.2f} USDT")

    def update_timers_loop(self):
        """Cronómetro en tiempo real para cuentas bloqueadas"""
        now = datetime.now()
        needs_refresh = False
        
        for idx, data in self.timers.items():
            expiry = data["expiry"]
            remaining = expiry - now
            if remaining.total_seconds() > 0:
                # Formato HH:MM:SS
                total_sec = int(remaining.total_seconds())
                h = total_sec // 3600
                m = (total_sec % 3600) // 60
                s = total_sec % 60
                data["label"].configure(text=f"⏳ {h:02}:{m:02}:{s:02}")
            else:
                needs_refresh = True
        
        if needs_refresh:
            self.update_view() # Recarga para quitar el bloqueo vencido
        else:
            try:
                self.after(1000, self.update_timers_loop)
            except: pass
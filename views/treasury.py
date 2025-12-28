import customtkinter as ctk
from datetime import datetime

# --- VENTANA MODAL DE GESTIÓN ---
class TransactionDialog(ctk.CTkToplevel):
    def __init__(self, parent, nombre_cuenta, saldo_actual, on_confirm):
        super().__init__(parent)
        self.on_confirm = on_confirm
        self.saldo_actual = saldo_actual
        self.nombre_cuenta = nombre_cuenta
        
        # Configuración
        self.title("Gestión de Fondos")
        self.geometry("400x380")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        # Centrar
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 190
        self.geometry(f"+{x}+{y}")
        self.configure(fg_color="#1a1a1a")

        # Título
        ctk.CTkLabel(self, text=f"GESTIONAR: {nombre_cuenta}", font=("Arial", 16, "bold"), text_color="#f39c12").pack(pady=(20, 5))
        ctk.CTkLabel(self, text=f"Saldo Actual: {saldo_actual:,.2f}", font=("Arial", 12), text_color="gray").pack(pady=(0, 20))

        # Selector
        self.accion_var = ctk.StringVar(value="INGRESAR")
        self.seg_btn = ctk.CTkSegmentedButton(self, values=["INGRESAR", "RETIRAR", "CORREGIR"], 
                                             variable=self.accion_var, command=self.update_ui,
                                             selected_color="#27ae60", selected_hover_color="#2ecc71")
        self.seg_btn.pack(pady=10, padx=20, fill="x")

        # Input
        self.entry_monto = ctk.CTkEntry(self, placeholder_text="Monto...", font=("Arial", 14), height=40, justify="center")
        self.entry_monto.pack(pady=10, padx=40, fill="x")
        self.entry_monto.bind("<KeyRelease>", self.calc_preview)

        # Preview
        self.lbl_preview = ctk.CTkLabel(self, text="Nuevo Saldo: ---", font=("Arial", 13, "bold"), text_color="white")
        self.lbl_preview.pack(pady=10)

        # Botones
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

# --- VISTA PRINCIPAL ---
class TesoreriaView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # Header
        ctk.CTkLabel(self, text="TESORERÍA & GESTIÓN DE CAPITAL", font=("Arial", 22, "bold"), text_color="#f39c12").pack(anchor="w", padx=20, pady=20)
        
        # --- SALDOS GENERALES ---
        self.info_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.info_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.info_frame.grid_columnconfigure((0,1), weight=1)
        
        # ARS es solo lectura (suma de bancos)
        self.lbl_saldo_ars = self.mk_card(0, "SALDO TOTAL ARS", None)
        
        # USDT ahora tiene botón de gestión (command=...)
        self.lbl_saldo_usdt = self.mk_card(1, "SALDO TOTAL USDT", self.gestionar_usdt)

        # --- LISTA DE CUENTAS ---
        header_list = ctk.CTkFrame(self, fg_color="transparent")
        header_list.pack(fill="x", padx=20)
        ctk.CTkLabel(header_list, text="CUENTA", width=120, anchor="w", font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(header_list, text="SALDO REAL", width=100, anchor="w", font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(header_list, text="LÍMITE FISCAL (AFIP)", width=200, anchor="w", font=("Arial", 11, "bold")).pack(side="left", padx=10)
        
        self.scroll_bancos = ctk.CTkScrollableFrame(self, fg_color="#101010")
        self.scroll_bancos.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.bank_widgets = []
        for _ in range(15):
            row = ctk.CTkFrame(self.scroll_bancos, fg_color="transparent")
            lbl_nom = ctk.CTkLabel(row, text="", width=120, anchor="w", font=("Arial", 12, "bold"))
            lbl_nom.pack(side="left")
            lbl_saldo = ctk.CTkLabel(row, text="", width=100, anchor="w", text_color="#2cc985")
            lbl_saldo.pack(side="left")
            pb = ctk.CTkProgressBar(row, height=12)
            pb.pack(side="left", fill="x", expand=True, padx=10)
            lbl_limite = ctk.CTkLabel(row, text="", width=80, font=("Arial", 10), text_color="gray")
            lbl_limite.pack(side="left")
            btn = ctk.CTkButton(row, text="⚙️", width=40, fg_color="#333", hover_color="#444")
            btn.pack(side="right", padx=5)
            self.bank_widgets.append({"frame": row, "nom": lbl_nom, "saldo": lbl_saldo, "pb": pb, "lim": lbl_limite, "btn": btn})

    def mk_card(self, col, title, cmd):
        f = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        f.grid(row=0, column=col, padx=20, pady=15)
        
        # Título y Botón opcional
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack()
        ctk.CTkLabel(header, text=title, font=("Arial", 12, "bold"), text_color="gray").pack(side="left")
        
        if cmd:
            btn = ctk.CTkButton(header, text="⚙️", width=30, height=20, fg_color="#333", hover_color="#444", command=cmd)
            btn.pack(side="left", padx=10)

        lbl = ctk.CTkLabel(f, text="---", font=("Arial", 24, "bold"), text_color="white")
        lbl.pack()
        return lbl

    # --- LÓGICA DE GESTIÓN DE USDT ---
    def gestionar_usdt(self):
        current_stock = self.controller.STOCK_USDT
        
        def aplicar_usdt(accion, monto):
            nuevo_stock = current_stock
            if accion == "INGRESAR": nuevo_stock += monto
            elif accion == "RETIRAR": nuevo_stock -= monto
            elif accion == "CORREGIR": nuevo_stock = monto
            
            # Guardamos en Memoria y BD
            self.controller.STOCK_USDT = nuevo_stock
            # Actualizamos tabla config para persistencia
            try:
                self.controller.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('stock_usdt', ?)", (str(nuevo_stock),))
                self.controller.conn.commit()
            except Exception as e:
                print(f"Error guardando stock: {e}")
            
            self.update_view()

        TransactionDialog(self, "STOCK USDT", current_stock, aplicar_usdt)

    # --- LÓGICA DE GESTIÓN DE BANCOS ---
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

    def update_view(self):
        # 1. Saldos Globales
        ars = self.controller.obtener_saldo_total_ars()
        usdt = self.controller.STOCK_USDT
        self.lbl_saldo_ars.configure(text=f"$ {ars:,.0f}")
        self.lbl_saldo_usdt.configure(text=f"{usdt:,.2f} USDT")

        # 2. Lista de Bancos
        for w in self.bank_widgets: w["frame"].pack_forget()
        
        self.controller.cursor.execute("SELECT nombre, saldo, limite_mensual, moneda FROM cuentas ORDER BY nombre")
        cuentas = self.controller.cursor.fetchall()
        mes_actual = datetime.now().strftime("%Y-%m")
        
        for i, (nom, saldo, lim, mon) in enumerate(cuentas):
            if i >= len(self.bank_widgets): break
            
            self.controller.cursor.execute("SELECT SUM(monto_ars) FROM operaciones WHERE banco=? AND strftime('%Y-%m', fecha)=?", (nom, mes_actual))
            res = self.controller.cursor.fetchone()
            consumido = res[0] if res[0] else 0.0
            
            pct = 0.0
            if lim > 0: pct = consumido / lim
            
            col_bar = "#2cc985"
            if pct > 0.7: col_bar = "#e3a319"
            if pct > 0.9: col_bar = "#cf3030"
            
            simbolo = "S/" if mon == "PEN" else "$" if mon == "ARS" else "u$s"
            
            w = self.bank_widgets[i]
            w["frame"].pack(fill="x", pady=4)
            w["nom"].configure(text=nom)
            w["saldo"].configure(text=f"{simbolo} {saldo:,.0f}")
            w["pb"].configure(progress_color=col_bar)
            w["pb"].set(min(pct, 1.0))
            w["lim"].configure(text=f"{pct*100:.0f}% Fiscal")
            w["btn"].configure(command=lambda n=nom, s=saldo: self.abrir_modal_gestion(n, s))
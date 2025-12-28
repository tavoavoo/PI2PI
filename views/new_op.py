import customtkinter as ctk
import math
import re
from datetime import datetime
from utils.ui_components import ModernModal

class NewOpView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.c = controller
        self.locked = False
        self.last_edited = "fiat"
        self.tipo_op = "Compra"
        
        # Batch (Puedes dejarlo básico o expandirlo luego)
        parser_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        parser_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(parser_frame, text="Pegar Ordenes (Batch - Chat o Recibo Completo):", font=("Inter", 12, "bold"), text_color="#3498db").pack(anchor="w", padx=15)
        self.txt_paste = ctk.CTkTextbox(parser_frame, height=100)
        self.txt_paste.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(parser_frame, text="⚡ PROCESAR LOTE", fg_color="#27ae60", height=40, command=self.process_batch).pack(fill="x", padx=15, pady=10)

        # Manual
        self.main_box = ctk.CTkFrame(self, fg_color="#1e1e1e", corner_radius=15)
        self.main_box.pack(padx=40, pady=10, fill="both", expand=True)
        
        moneda_frame = ctk.CTkFrame(self.main_box, fg_color="transparent")
        moneda_frame.pack(pady=10)
        ctk.CTkLabel(moneda_frame, text="MONEDA:").pack(side="left", padx=5)
        self.seg_moneda = ctk.CTkSegmentedButton(moneda_frame, values=["ARS", "PEN"], command=self.update_bancos)
        self.seg_moneda.set("ARS")
        self.seg_moneda.pack(side="left", padx=5)

        self.seg_tipo = ctk.CTkSegmentedButton(self.main_box, values=["Compra", "Venta"], command=self.cambio_tipo)
        self.seg_tipo.set("Compra")
        self.seg_tipo.pack(fill="x", padx=40, pady=5)

        # SELECTOR DE ROL
        ctk.CTkLabel(self.main_box, text="ROL:", font=("Arial", 10, "bold")).pack(pady=(5,0))
        self.seg_rol = ctk.CTkSegmentedButton(self.main_box, values=["Maker", "Taker"])
        self.seg_rol.set("Maker")
        self.seg_rol.pack(pady=5)

        grid = ctk.CTkFrame(self.main_box, fg_color="transparent")
        grid.pack(padx=20, pady=5)
        ctk.CTkLabel(grid, text="Banco:").grid(row=0, column=0, sticky="e")
        self.banco_var = ctk.CTkOptionMenu(grid, width=180)
        self.banco_var.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(grid, text="Nick:").grid(row=0, column=2, sticky="e")
        self.entry_nick = ctk.CTkEntry(grid, width=180)
        self.entry_nick.grid(row=0, column=3, padx=5)
        ctk.CTkLabel(grid, text="Cotización:").grid(row=1, column=0, sticky="e", pady=10)
        self.var_cot = ctk.StringVar()
        self.entry_cot = ctk.CTkEntry(grid, textvariable=self.var_cot, width=180)
        self.entry_cot.grid(row=1, column=1, padx=5)
        ctk.CTkLabel(grid, text="Comisión (%):").grid(row=1, column=2, sticky="e")
        fee_frame = ctk.CTkFrame(grid, fg_color="transparent")
        fee_frame.grid(row=1, column=3, sticky="w", padx=5)
        self.var_fee = ctk.StringVar()
        self.entry_fee = ctk.CTkEntry(fee_frame, textvariable=self.var_fee, width=80)
        self.entry_fee.pack(side="left")
        
        m_frame = ctk.CTkFrame(self.main_box, fg_color="transparent")
        m_frame.pack(pady=5)
        self.var_fiat = ctk.StringVar()
        self.var_usdt = ctk.StringVar()
        ctk.CTkEntry(m_frame, textvariable=self.var_fiat, width=140, font=("Arial", 16)).pack(side="left", padx=(10, 2))
        self.lbl_fiat_unit = ctk.CTkLabel(m_frame, text="ARS", font=("Arial", 14, "bold"), text_color="gray")
        self.lbl_fiat_unit.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(m_frame, text="↔", font=("Arial", 20)).pack(side="left")
        ctk.CTkEntry(m_frame, textvariable=self.var_usdt, width=140, font=("Arial", 16)).pack(side="left", padx=(10, 2))
        ctk.CTkLabel(m_frame, text="USDT", font=("Arial", 14, "bold"), text_color="#2ecc71").pack(side="left", padx=(0, 10))
        self.lbl_neto = ctk.CTkLabel(self.main_box, text="---", text_color="#aaaaaa", font=("Inter", 12, "bold"))
        self.lbl_neto.pack(pady=5)
        self.btn_ok = ctk.CTkButton(self.main_box, text="GUARDAR MANUALMENTE", height=30, command=self.guardar)
        self.btn_ok.pack(pady=10)

        self.var_cot.trace_add("write", lambda *a: self.calc_bidireccional("cot"))
        self.var_fiat.trace_add("write", lambda *a: self.calc_bidireccional("fiat"))
        self.var_usdt.trace_add("write", lambda *a: self.calc_bidireccional("usdt"))
        self.var_fee.trace_add("write", lambda *a: self.calc_neto_display())

    def guardar(self):
        try:
            moneda = self.seg_moneda.get()
            fiat = self.c.limpiar_numero(self.var_fiat.get())
            usdt_input = self.c.limpiar_numero(self.var_usdt.get()) 
            cot = self.c.limpiar_numero(self.var_cot.get())
            fee_pct_user = self.c.limpiar_numero(self.var_fee.get())
            fee_decimal = fee_pct_user / 100.0
            nick = self.entry_nick.get()
            banco = self.banco_var.get()
            rol = self.seg_rol.get() # <--- LEEMOS EL ROL DEL SELECTOR
            
            fee_val = math.floor((usdt_input * fee_decimal) * 100) / 100 
            monto_final_db = 0.0
            if self.tipo_op == "Compra":
                monto_final_db = usdt_input - fee_val
                stock_impact = monto_final_db
            else:
                monto_final_db = usdt_input
                stock_impact = usdt_input
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.c.cursor.execute("INSERT INTO operaciones (fecha, nickname, tipo, banco, monto_ars, monto_usdt, cotizacion, fee, moneda, rol) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (now, nick, self.tipo_op, banco, fiat, monto_final_db, cot, fee_val, moneda, rol))
            
            if self.tipo_op == "Compra":
                self.c.update_stock_usdt(stock_impact)
                self.c.update_saldo_banco(banco, -fiat)
            else:
                self.c.update_stock_usdt(-stock_impact) 
                self.c.update_saldo_banco(banco, fiat)
                
            self.c.cursor.execute("UPDATE cuentas SET acumulado_actual = acumulado_actual + ? WHERE nombre=?", (fiat, banco))
            self.c.conn.commit()
            self.c.refresh_all_views() 
            self.c.show_info("OK", f"Operación guardada ({rol}).\nImpacto Real: {stock_impact:.2f} USDT")
            self.var_fiat.set("")
            self.var_usdt.set("")
        except Exception as e: self.c.show_error("Error", str(e))

    # --- Funciones Auxiliares (sin cambios lógicos) ---
    def calc_bidireccional(self, origen):
        if self.locked: return
        self.locked = True
        try:
            if origen == "fiat": self.last_edited = "fiat"
            elif origen == "usdt": self.last_edited = "usdt"
            cot = self.c.limpiar_numero(self.var_cot.get())
            if cot > 0:
                driver = origen if origen != "cot" else self.last_edited
                if driver == "usdt":
                    usdt = self.c.limpiar_numero(self.var_usdt.get())
                    new_fiat = usdt * cot
                    if abs(self.c.limpiar_numero(self.var_fiat.get()) - new_fiat) > 0.01: self.var_fiat.set(f"{new_fiat:.2f}")
                elif driver == "fiat":
                    fiat = self.c.limpiar_numero(self.var_fiat.get())
                    new_usdt = fiat / cot
                    if abs(self.c.limpiar_numero(self.var_usdt.get()) - new_usdt) > 0.01: self.var_usdt.set(f"{new_usdt:.2f}")
        except: pass
        self.calc_neto_display()
        self.locked = False
    def calc_neto_display(self):
        try:
            usdt = self.c.limpiar_numero(self.var_usdt.get())
            fee_pct = self.c.limpiar_numero(self.var_fee.get())
            fee_val = usdt * (fee_pct/100)
            fee_trunc = math.floor(fee_val * 100) / 100 
            if self.tipo_op == "Compra": self.lbl_neto.configure(text=f"📉 RECIBIRÁS NETO: {usdt - fee_trunc:.2f} USDT", text_color="#2cc985")
            else: self.lbl_neto.configure(text=f"📉 SE DESCONTARÁ: {usdt + fee_trunc:.2f} USDT", text_color="#e3a319")
        except: pass
    def update_view(self):
        self.update_bancos("ARS")
        self.c.load_config()
        self.var_fee.set(f"{self.c.COMISION_VENTA * 100:.2f}")
        self.cambio_tipo("Compra")
    def update_bancos(self, moneda):
        self.c.cursor.execute("SELECT nombre FROM cuentas WHERE estado='Activo' AND moneda=?", (moneda,))
        b = [x[0] for x in self.c.cursor.fetchall()]
        self.banco_var.configure(values=b if b else ["Sin Cuentas"])
        if b: self.banco_var.set(b[0])
        if hasattr(self, 'lbl_fiat_unit'): self.lbl_fiat_unit.configure(text=moneda)
    def cambio_tipo(self, val):
        self.tipo_op = val
        col = "#2cc985" if val == "Compra" else "#e3a319"
        self.seg_tipo.configure(selected_color=col)
        self.btn_ok.configure(fg_color=col, hover_color="#1ea86d" if val=="Compra" else "#c98d0e", text=f"GUARDAR {val.upper()} ({self.seg_moneda.get()})")
        self.calc_neto_display()
    def process_batch(self): pass 
    def open_batch_modal(self, orders, total_fiat, moneda): pass
    def save_batch_to_db(self, orders): pass
    def fijar_comision(self): pass
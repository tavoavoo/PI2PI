import customtkinter as ctk
import csv
from tkinter import filedialog
from utils.ui_components import CustomDialog, ModernModal
import sqlite3

class HistorialView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.c = controller
        self.search_term = "" 
        
        # --- AUTO-MIGRACIÓN DE BASE DE DATOS (Seguridad) ---
        self.verificar_columna_personal()

        # --- HEADER ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(header, text="Historial Global", font=("Arial", 26, "bold")).pack(side="left")
        
        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")
        ctk.CTkButton(btn_box, text="📡 SYNC RAPIDO", width=140, fg_color="#2980b9", hover_color="#1c5980", command=self.sync_binance_api).pack(side="left", padx=5)
        ctk.CTkButton(btn_box, text="📗 EXPORTAR EXCEL", width=140, font=("Arial", 12, "bold"), fg_color="#27ae60", hover_color="#219150", command=self.exportar_excel).pack(side="left", padx=5)

        # --- BUSCADOR ---
        search_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", border_width=1, border_color="#333")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(search_frame, text="🔍 BUSCADOR:", font=("Arial", 12, "bold"), text_color="gray").pack(side="left", padx=15, pady=10)
        
        self.entry_search = ctk.CTkEntry(search_frame, width=320, placeholder_text="Escribe ID, Nick, Monto o Banco...")
        self.entry_search.pack(side="left", padx=5, pady=10)
        self.entry_search.bind("<Return>", lambda event: self.ejecutar_busqueda())
        
        ctk.CTkButton(search_frame, text="BUSCAR", width=100, command=self.ejecutar_busqueda, fg_color="#3498db").pack(side="left", padx=5)
        ctk.CTkButton(search_frame, text="LIMPIAR", width=80, command=self.limpiar_busqueda, fg_color="#444", hover_color="#222").pack(side="left", padx=5)

        # --- NAV & ACCIONES ---
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=20)
        self.pagina = 1
        self.items_por_pagina = 10 
        ctk.CTkButton(self.nav_frame, text="< ANTERIOR", width=100, height=30, font=("Arial", 12), command=self.prev_page).pack(side="left")
        self.lbl_pag = ctk.CTkLabel(self.nav_frame, text="Pág. 1", font=("Arial", 14, "bold"))
        self.lbl_pag.pack(side="left", padx=20)
        ctk.CTkButton(self.nav_frame, text="SIGUIENTE >", width=100, height=30, font=("Arial", 12), command=self.next_page).pack(side="left")
        ctk.CTkButton(self.nav_frame, text="🗑 ELIMINAR SELECCIONADOS", fg_color="#c0392b", hover_color="#922b21", width=200, command=self.eliminar_seleccionados).pack(side="right")

        # --- TABLA ---
        self.header_frame = ctk.CTkFrame(self, height=50)
        self.header_frame.pack(fill="x", padx=20, pady=(15,0))
        self.chk_master_var = ctk.IntVar()
        self.chk_master = ctk.CTkCheckBox(self.header_frame, text="", variable=self.chk_master_var, width=24, checkbox_width=20, checkbox_height=20, command=self.toggle_select_all)
        self.chk_master.pack(side="left", padx=(10, 5))

        headers = ["Fecha", "Moneda", "Rol", "Tipo", "Banco (Clasificar)", "Fiat", "USDT", "Cotiz.", "Acción"]
        widths = [130, 60, 60, 80, 160, 100, 100, 70, 90] 
        for i, h in enumerate(headers): 
            ctk.CTkLabel(self.header_frame, text=h, width=widths[i], font=("Arial", 12, "bold")).pack(side="left", padx=5)

        self.table = ctk.CTkScrollableFrame(self, height=450)
        self.table.pack(fill="both", expand=True, padx=20, pady=5)
        self.rows_cache = [] 
        self.crear_filas_vacias(10)
        self.lbl_status = ctk.CTkLabel(self, text="", font=("Consolas", 11), text_color="gray")
        self.lbl_status.pack(pady=5)
        
        # Inicia loop sync
        self.after(5000, self.loop_sync_automatico)

    def verificar_columna_personal(self):
        """Revisa si existe la columna es_personal, si no, la agrega."""
        try:
            self.c.cursor.execute("PRAGMA table_info(operaciones)")
            columns = [info[1] for info in self.c.cursor.fetchall()]
            if "es_personal" not in columns:
                print("Migrando DB: Agregando columna 'es_personal'...")
                self.c.cursor.execute("ALTER TABLE operaciones ADD COLUMN es_personal INTEGER DEFAULT 0")
                self.c.conn.commit()
        except Exception as e:
            print(f"Error en migración DB: {e}")

    def loop_sync_automatico(self):
        self.sync_binance_api()
        self.after(60000, self.loop_sync_automatico)

    def crear_filas_vacias(self, cantidad):
        widths = [130, 60, 60, 80, 160, 100, 100, 70]
        for _ in range(cantidad):
            row_frame = ctk.CTkFrame(self.table, height=45)
            chk_var = ctk.IntVar()
            chk = ctk.CTkCheckBox(row_frame, text="", variable=chk_var, width=24, checkbox_width=20, checkbox_height=20)
            chk.pack(side="left", padx=(10, 5))
            
            widgets_row = []
            for i, w in enumerate(widths):
                if i == 4: # Banco Container
                    container = ctk.CTkFrame(row_frame, width=w, height=35, fg_color="transparent")
                    container.pack_propagate(False)
                    container.pack(side="left", padx=2)
                    lbl = ctk.CTkLabel(container, text="", font=("Arial", 13))
                    lbl.pack(expand=True)
                    opt = ctk.CTkOptionMenu(container, width=w-10, height=28, font=("Arial", 11))
                    widgets_row.append({"type": "bank_container", "lbl": lbl, "opt": opt, "container": container})
                else:
                    l = ctk.CTkLabel(row_frame, text="", width=w, font=("Arial", 13))
                    l.pack(side="left", padx=2)
                    widgets_row.append({"type": "label", "widget": l})

            btn_edit = ctk.CTkButton(row_frame, text="✎", width=35, height=25, fg_color="#3498db", font=("Arial", 12))
            btn_edit.pack(side="left", padx=5)
            btn_del = ctk.CTkButton(row_frame, text="X", width=35, height=25, fg_color="#cf3030", font=("Arial", 12))
            btn_del.pack(side="left", padx=5)
            
            self.rows_cache.append({
                "frame": row_frame, "chk": chk, "var": chk_var, "cols": widgets_row, 
                "btn_edit": btn_edit, "btn_del": btn_del, "current_oid": None
            })

    def renderizar_pagina(self):
        self.c.cursor.execute("SELECT nombre FROM cuentas WHERE estado='Activo' ORDER BY nombre")
        res_bancos = self.c.cursor.fetchall()
        mis_bancos = [b[0] for b in res_bancos] if res_bancos else ["Sin Cuentas"]

        for row in self.rows_cache: 
            row["frame"].pack_forget()
            row["var"].set(0)
            row["current_oid"] = None
        self.chk_master_var.set(0)
        
        offset = (self.pagina - 1) * self.items_por_pagina
        
        # QUERY ACTUALIZADA CON es_personal
        base_query = "SELECT id, fecha, moneda, rol, tipo, banco, monto_ars, monto_usdt, cotizacion, fee, es_personal FROM operaciones" 
        params = []
        where_clause = ""
        
        if self.search_term:
            term = self.search_term.strip()
            like_term = f"%{term}%"
            where_clause = " WHERE (nickname LIKE ? OR banco LIKE ? OR order_id LIKE ? OR CAST(monto_usdt AS TEXT) LIKE ?)"
            params.extend([like_term, like_term, like_term, like_term])
        
        final_query = base_query + where_clause + f" ORDER BY fecha DESC LIMIT {self.items_por_pagina} OFFSET {offset}"
        
        self.c.cursor.execute(final_query, tuple(params))
        db_rows = self.c.cursor.fetchall()
        
        if not db_rows and self.pagina > 1:
            self.pagina -= 1; self.renderizar_pagina(); return

        self.lbl_pag.configure(text=f"Página {self.pagina}")

        for i, r in enumerate(db_rows):
            oid, fecha, moneda, rol, tipo, banco, fiat, usdt_db_value, cot, fee, es_personal = r 
            
            # --- LÓGICA DE COLOR (VIOLETA SI ES PERSONAL) ---
            if es_personal == 1:
                color_tipo = "#8e44ad" # Violeta
                tipo_display = f"{tipo} (P)" # Indicador visual
            else:
                color_tipo = "#2cc985" if tipo == "Compra" else "#e3a319"
                tipo_display = tipo

            rol_str = rol if rol else "---"
            color_rol = "#9b59b6" if rol_str == "Maker" else "#e67e22" if rol_str == "Taker" else "gray"
            usdt_display = round(usdt_db_value, 2)

            if i >= len(self.rows_cache): self.crear_filas_vacias(5)
            
            widgets = self.rows_cache[i]
            widgets["frame"].pack(fill="x", pady=2)
            widgets["current_oid"] = oid 
            
            vals = [fecha[:16], moneda, rol_str, tipo_display, banco, f"${fiat:,.2f}", f"{usdt_display:.2f}", f"{cot:.1f}"]
            
            col_objs = widgets["cols"]
            col_objs[0]["widget"].configure(text=vals[0])
            col_objs[1]["widget"].configure(text=vals[1])
            col_objs[2]["widget"].configure(text=vals[2], text_color=color_rol, font=("Arial", 11, "bold"))
            col_objs[3]["widget"].configure(text=vals[3], text_color=color_tipo, font=("Arial", 12, "bold"))
            
            bank_item = col_objs[4]
            es_pendiente = (banco == "Por Clasificar")
            
            if es_pendiente:
                bank_item["lbl"].pack_forget()
                bank_item["opt"].pack(expand=True)
                bank_item["opt"].configure(
                    values=mis_bancos, fg_color="#e74c3c", button_color="#c0392b",
                    command=lambda val, id_op=oid: self.asignar_banco(id_op, val)
                )
                bank_item["opt"].set("Seleccionar...")
            else:
                bank_item["opt"].pack_forget()
                bank_item["lbl"].pack(expand=True)
                bank_item["lbl"].configure(text=banco, text_color="white")

            col_objs[5]["widget"].configure(text=vals[5])
            col_objs[6]["widget"].configure(text=vals[6], text_color=color_tipo)
            col_objs[7]["widget"].configure(text=vals[7])
            
            widgets["btn_edit"].configure(command=self.make_cmd(self.modal_editar, oid))
            widgets["btn_del"].configure(command=self.make_cmd(self.borrar, oid))

    def asignar_banco(self, oid, banco_seleccionado):
        if banco_seleccionado == "Sin Cuentas" or not banco_seleccionado: return
        try:
            self.c.cursor.execute("SELECT tipo, monto_ars FROM operaciones WHERE id=?", (oid,))
            res = self.c.cursor.fetchone()
            if not res: return
            tipo_op, monto_fiat = res
            
            self.c.cursor.execute("UPDATE operaciones SET banco=? WHERE id=?", (banco_seleccionado, oid))
            
            if tipo_op == "Compra":
                self.c.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (monto_fiat, banco_seleccionado))
            else:
                self.c.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (monto_fiat, banco_seleccionado))
            
            self.c.conn.commit()
            self.c.refresh_all_views() 
            self.renderizar_pagina() 
            self.c.show_info("Clasificado", f"Operación asignada a {banco_seleccionado}.")
        except Exception as e:
            self.c.show_error("Error", str(e))

    def sync_binance_api(self):
        self.c.cursor.execute("SELECT value FROM config WHERE key='api_key'")
        ak_res = self.c.cursor.fetchone()
        self.c.cursor.execute("SELECT value FROM config WHERE key='api_secret'")
        ask_res = self.c.cursor.fetchone()
        if not ak_res or not ask_res: self.pedir_credenciales() 
        else: self.ejecutar_sync_silencioso(ak_res[0], ask_res[0])

    def ejecutar_sync_silencioso(self, api_key, api_secret):
        self.lbl_status.configure(text="⏳ Conectando con Binance...", text_color="#f39c12")
        self.update()
        try:
            orders = self.c.fetch_binance_history(api_key, api_secret)
            if not orders:
                self.lbl_status.configure(text="✅ Todo al día.", text_color="#2cc985")
                return

            count = 0
            for orden in orders:
                self.c.cursor.execute("SELECT 1 FROM ignored_orders WHERE order_id=?", (str(orden['order_id']),))
                if self.c.cursor.fetchone(): continue
                self.c.cursor.execute("SELECT 1 FROM operaciones WHERE order_id=?", (str(orden['order_id']),))
                if self.c.cursor.fetchone(): continue

                banco_inicial = "Por Clasificar"
                
                # Insertamos con es_personal = 0 por defecto
                self.c.cursor.execute(
                    """
                    INSERT INTO operaciones 
                    (fecha, nickname, tipo, banco, monto_ars, monto_usdt, cotizacion, fee, moneda, order_id, rol, archivado, es_personal) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (orden['fecha'], orden['nick'], orden['tipo'], banco_inicial, orden['fiat'], orden['usdt_nominal'], orden['cot'], orden['fee'], orden['moneda'], orden['order_id'], orden['rol'])
                )
                
                if orden['tipo'] == "Compra":
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) + ? WHERE key='stock_usdt'", (orden['stock_impact'],))
                    self.c.STOCK_USDT += orden['stock_impact']
                else:
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) - ? WHERE key='stock_usdt'", (orden['stock_impact'],))
                    self.c.STOCK_USDT -= orden['stock_impact']
                
                count += 1
            
            self.c.conn.commit()
            self.c.refresh_all_views()
            self.renderizar_pagina()
            
            if count > 0: self.lbl_status.configure(text=f"✅ {count} Nuevas.", text_color="#3498db")
            else: self.lbl_status.configure(text="✅ Sincronizado.", text_color="#2cc985")
            
        except Exception as e:
            self.lbl_status.configure(text=f"❌ Error Sync: {str(e)}", text_color="red")
            print(f"Error detallado en sync: {e}")

    # --- EDICIÓN CON FLAG PERSONAL ---
    def modal_editar(self, oid):
        self.c.cursor.execute("SELECT fecha, nickname, tipo, banco, monto_ars, monto_usdt, cotizacion, moneda, es_personal FROM operaciones WHERE id=?", (oid,))
        data = self.c.cursor.fetchone()
        if not data: return

        fecha, nick, tipo, old_banco, old_fiat, old_usdt, old_cot, moneda, is_personal_val = data
        
        modal = ModernModal(self.c, f"Editar Op #{oid} - {tipo}", height=500)
        
        ctk.CTkLabel(modal.content_frame, text="Banco / Cuenta:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        self.c.cursor.execute("SELECT nombre FROM cuentas WHERE estado='Activo' ORDER BY nombre")
        bancos = [b[0] for b in self.c.cursor.fetchall()]
        cbo_banco = ctk.CTkOptionMenu(modal.content_frame, values=bancos)
        cbo_banco.pack(fill="x", pady=5)
        if old_banco in bancos: cbo_banco.set(old_banco)
        elif old_banco == "Por Clasificar": cbo_banco.set(bancos[0] if bancos else "Sin Cuentas")
        else: cbo_banco.set(old_banco)
        
        ctk.CTkLabel(modal.content_frame, text="Monto Total (ARS):", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        entry_fiat = ctk.CTkEntry(modal.content_frame)
        entry_fiat.insert(0, str(old_fiat))
        entry_fiat.pack(fill="x", pady=5)
        
        ctk.CTkLabel(modal.content_frame, text="Cantidad USDT:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        entry_usdt = ctk.CTkEntry(modal.content_frame)
        entry_usdt.insert(0, str(old_usdt))
        entry_usdt.pack(fill="x", pady=5)

        ctk.CTkLabel(modal.content_frame, text="Precio / Cotización:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        entry_cot = ctk.CTkEntry(modal.content_frame)
        entry_cot.insert(0, str(old_cot))
        entry_cot.pack(fill="x", pady=5)

        # CHECKBOX PERSONAL
        chk_personal_var = ctk.IntVar(value=is_personal_val if is_personal_val else 0)
        chk_personal = ctk.CTkCheckBox(modal.content_frame, text="Es Movimiento PERSONAL (No Comercial)", variable=chk_personal_var, font=("Arial", 12, "bold"), text_color="#9b59b6")
        chk_personal.pack(pady=15)

        def guardar_cambios():
            try:
                new_fiat = float(entry_fiat.get())
                new_usdt = float(entry_usdt.get())
                new_cot = float(entry_cot.get())
                new_banco = cbo_banco.get()
                new_personal = chk_personal_var.get()
                
                if not new_banco or new_banco == "Sin Cuentas":
                    self.c.show_error("Error", "Debes seleccionar un banco válido.")
                    return

                # REVERTIR LO VIEJO (Saldos)
                if old_banco != "Por Clasificar":
                    if tipo == "Compra": self.c.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (old_fiat, old_banco))
                    else: self.c.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (old_fiat, old_banco))
                
                if tipo == "Compra": self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) - ? WHERE key='stock_usdt'", (old_usdt,))
                else: self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) + ? WHERE key='stock_usdt'", (old_usdt,))

                # APLICAR LO NUEVO (Saldos)
                if tipo == "Compra": self.c.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (new_fiat, new_banco))
                else: self.c.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (new_fiat, new_banco))
                
                if tipo == "Compra": self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) + ? WHERE key='stock_usdt'", (new_usdt,))
                else: self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) - ? WHERE key='stock_usdt'", (new_usdt,))

                # ACTUALIZAR REGISTRO INCLUYENDO es_personal
                self.c.cursor.execute("""
                    UPDATE operaciones 
                    SET banco=?, monto_ars=?, monto_usdt=?, cotizacion=?, es_personal=?
                    WHERE id=?
                """, (new_banco, new_fiat, new_usdt, new_cot, new_personal, oid))
                
                self.c.conn.commit()
                self.c.refresh_all_views()
                self.renderizar_pagina()
                modal.close()
                self.c.show_info("Éxito", "Operación corregida.")

            except ValueError:
                self.c.show_error("Error", "Los campos numéricos deben ser válidos.")
            except Exception as e:
                self.c.show_error("Error Crítico", str(e))

        ctk.CTkButton(modal.content_frame, text="GUARDAR CAMBIOS", fg_color="#27ae60", hover_color="#2ecc71", command=guardar_cambios).pack(pady=20, fill="x")

    def exportar_excel(self): 
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not filename: return
            self.c.cursor.execute("SELECT id, fecha, nickname, tipo, banco, monto_ars, monto_usdt, cotizacion, fee, moneda, rol, es_personal FROM operaciones ORDER BY fecha DESC")
            rows = self.c.cursor.fetchall()
            def fmt_num(val): return f"{val:.2f}".replace('.', ',') if val else "0,00"
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["ID", "Fecha", "Nick", "Tipo", "Banco", "Fiat", "USDT", "Cot", "Fee", "Moneda", "Rol", "Es Personal"])
                for r in rows:
                    w.writerow([r[0], r[1], r[2], r[3], r[4], fmt_num(r[5]), fmt_num(r[6]), fmt_num(r[7]), fmt_num(r[8]), r[9], r[10], "SI" if r[11] else "NO"])
            self.c.show_info("Listo", "Exportado correctamente.")
        except Exception as e: self.c.show_error("Error", str(e))

    # --- RESTO DE FUNCIONES ---
    def ejecutar_busqueda(self):
        self.search_term = self.entry_search.get()
        self.pagina = 1 
        self.renderizar_pagina()
        if self.search_term: self.lbl_status.configure(text=f"🔎 Filtrando por: '{self.search_term}'", text_color="#3498db")
        else: self.lbl_status.configure(text="")

    def limpiar_busqueda(self):
        self.entry_search.delete(0, "end")
        self.search_term = ""
        self.pagina = 1
        self.renderizar_pagina()
        self.lbl_status.configure(text="")

    def eliminar_seleccionados(self):
        ids_to_delete = []
        for row in self.rows_cache:
            if row["var"].get() == 1 and row["current_oid"] is not None:
                ids_to_delete.append(row["current_oid"])
        if not ids_to_delete: return self.c.show_info("Info", "No seleccionaste nada.")
        self.c.ask_confirm("Borrado Masivo", f"¿Eliminar {len(ids_to_delete)} operaciones?\nSe reembolsarán los saldos.", 
                           lambda: self.do_delete_batch(ids_to_delete))

    def do_delete_batch(self, ids):
        count = 0
        try:
            for oid in ids:
                if self.do_delete(oid, refresh=False): count += 1
            self.c.conn.commit()
            self.c.refresh_all_views()
            self.renderizar_pagina()
            self.c.show_info("Listo", f"Se eliminaron {count} operaciones.")
        except Exception as e: self.c.show_error("Error", str(e))

    def make_cmd(self, func, arg): return lambda: func(arg)
    def toggle_select_all(self):
        val = self.chk_master_var.get()
        for row in self.rows_cache:
            if row["current_oid"] is not None: row["var"].set(val)
    def next_page(self): self.pagina += 1; self.renderizar_pagina()
    def prev_page(self): 
        if self.pagina > 1: self.pagina -= 1; self.renderizar_pagina()
    def update_view(self): self.renderizar_pagina()

    def borrar(self, oid): 
        self.c.ask_confirm("Borrar", f"¿Eliminar operación ID {oid}?", lambda: self.do_delete(oid))

    def do_delete(self, oid, refresh=True):
        try:
            self.c.cursor.execute("SELECT tipo, banco, monto_ars, monto_usdt, order_id FROM operaciones WHERE id=?", (oid,))
            op = self.c.cursor.fetchone()
            if op:
                tipo, banco, fiat, usdt, order_id_binance = op
                es_pendiente = (banco == "Por Clasificar")

                if tipo == "Compra":
                    if not es_pendiente: self.c.cursor.execute("UPDATE cuentas SET saldo = saldo + ? WHERE nombre=?", (fiat, banco))
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) - ? WHERE key='stock_usdt'", (usdt,))
                else: 
                    if not es_pendiente: self.c.cursor.execute("UPDATE cuentas SET saldo = saldo - ? WHERE nombre=?", (fiat, banco))
                    self.c.cursor.execute("UPDATE config SET value = CAST(value AS REAL) + ? WHERE key='stock_usdt'", (usdt,))

                if order_id_binance:
                    self.c.cursor.execute("INSERT OR IGNORE INTO ignored_orders (order_id) VALUES (?)", (order_id_binance,))

                self.c.cursor.execute("DELETE FROM operaciones WHERE id=?", (oid,))
                if refresh:
                    self.c.conn.commit()
                    self.c.refresh_all_views()
                    self.renderizar_pagina()
                return True
            return False
        except Exception as e:
            print(f"Error borrando ID {oid}: {e}")
            return False

    def pedir_credenciales(self):
        dialog = ModernModal(self.c, "Configurar Binance API", height=320)
        
        ctk.CTkLabel(dialog.content_frame, text="API Key:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        entry_key = ctk.CTkEntry(dialog.content_frame, width=300)
        entry_key.pack(pady=5)
        
        ctk.CTkLabel(dialog.content_frame, text="API Secret:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10,0))
        entry_secret = ctk.CTkEntry(dialog.content_frame, width=300, show="*")
        entry_secret.pack(pady=5)
        
        def save():
            k = entry_key.get().strip()
            s = entry_secret.get().strip()
            if k and s:
                self.c.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('api_key', ?)", (k,))
                self.c.cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('api_secret', ?)", (s,))
                self.c.conn.commit()
                dialog.close()
                self.sync_binance_api() 
            else:
                self.c.show_error("Error", "Campos vacíos.")
                
        ctk.CTkButton(dialog.content_frame, text="GUARDAR", fg_color="#27ae60", hover_color="#2ecc71", command=save).pack(pady=20, fill="x")
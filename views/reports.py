import customtkinter as ctk
from datetime import datetime, timedelta
import calendar
import threading

class ReportesView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        
        # --- HEADER Y FILTROS ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="BITÁCORA DE RENDIMIENTO", font=("Arial", 22, "bold"), text_color="#9b59b6").pack(side="left")
        
        # Filtros
        filter_frame = ctk.CTkFrame(header, fg_color="transparent")
        filter_frame.pack(side="right")
        
        self.combo_mes = ctk.CTkOptionMenu(filter_frame, values=self.get_meses(), width=120)
        self.combo_mes.set(self.get_mes_actual())
        self.combo_mes.pack(side="left", padx=5)
        
        self.combo_anio = ctk.CTkOptionMenu(filter_frame, values=["2024", "2025", "2026"], width=80)
        self.combo_anio.set(datetime.now().strftime("%Y"))
        self.combo_anio.pack(side="left", padx=5)
        
        ctk.CTkButton(filter_frame, text="GENERAR", width=100, fg_color="#333", hover_color="#444", 
                      command=self.generar_reporte).pack(side="left", padx=5)

        # --- KPI GLOBAL (AHORA SON 3) ---
        self.kpi_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.kpi_frame.grid_columnconfigure((0,1,2), weight=1)
        
        # 1. Ganancia del Mes
        self.card_ganancia_mes = self.mk_kpi_card(0, "GANANCIA (MES)", "#2ecc71")
        # 2. Ganancia Histórica (Nueva)
        self.card_ganancia_total = self.mk_kpi_card(1, "GANANCIA HISTÓRICA", "#f39c12")
        # 3. Volumen
        self.card_volumen = self.mk_kpi_card(2, "VOLUMEN (MES)", "#3498db")

        # --- LISTA DE TURNOS ---
        mid_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=10)
        mid_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Encabezados de Tabla
        head_list = ctk.CTkFrame(mid_frame, fg_color="transparent")
        head_list.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(head_list, text="FECHA DE CIERRE", width=150, anchor="w", font=("Arial", 11, "bold"), text_color="gray").pack(side="left")
        ctk.CTkLabel(head_list, text="RESULTADO (ARS)", width=150, anchor="w", font=("Arial", 11, "bold"), text_color="gray").pack(side="left")
        ctk.CTkLabel(head_list, text="ESTADO", width=100, anchor="w", font=("Arial", 11, "bold"), text_color="gray").pack(side="left")
        
        self.scroll_turnos = ctk.CTkScrollableFrame(mid_frame, fg_color="transparent")
        self.scroll_turnos.pack(fill="both", expand=True, padx=5, pady=(0, 10))
        
        self.shift_widgets = []

    def mk_kpi_card(self, col, title, color):
        f = ctk.CTkFrame(self.kpi_frame, fg_color="#1a1a1a", border_width=1, border_color="#333")
        f.grid(row=0, column=col, padx=5, sticky="ew")
        ctk.CTkLabel(f, text=title, font=("Arial", 11, "bold"), text_color="gray").pack(pady=(15, 5))
        lbl = ctk.CTkLabel(f, text="---", font=("Arial", 24, "bold"), text_color=color)
        lbl.pack(pady=(0, 15))
        return lbl

    def get_meses(self):
        return ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    def get_mes_actual(self):
        return self.get_meses()[datetime.now().month - 1]

    def generar_reporte(self):
        threading.Thread(target=self.calculo_pesado, daemon=True).start()

    def calculo_pesado(self):
        try:
            mes_nombre = self.combo_mes.get()
            anio = self.combo_anio.get()
            mes_idx = self.get_meses().index(mes_nombre) + 1
            
            # Rango del Mes Seleccionado
            _, last_day = calendar.monthrange(int(anio), mes_idx)
            fecha_inicio_mes = f"{anio}-{mes_idx:02d}-01 00:00:00"
            fecha_fin_mes = f"{anio}-{mes_idx:02d}-{last_day} 23:59:59"
            
            # A. CÁLCULO MENSUAL
            ganancia_mes = self.controller.calc_ganancia_rango_ars(fecha_inicio_mes, fecha_fin_mes, "ARS")
            
            self.controller.cursor.execute("SELECT SUM(monto_ars) FROM operaciones WHERE fecha >= ? AND fecha <= ? AND archivado=0", (fecha_inicio_mes, fecha_fin_mes))
            res_vol = self.controller.cursor.fetchone()
            volumen_mes = res_vol[0] if res_vol and res_vol[0] else 0.0
            
            # B. CÁLCULO HISTÓRICO TOTAL (Desde el inicio de los tiempos hasta hoy)
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ganancia_total = self.controller.calc_ganancia_rango_ars("2020-01-01 00:00:00", ahora, "ARS")
            
            # C. DETALLE POR TURNO
            self.controller.cursor.execute("SELECT fecha_cierre FROM cierres ORDER BY fecha_cierre ASC")
            all_cierres = [row[0] for row in self.controller.cursor.fetchall()]
            
            lista_turnos = []
            
            # Filtramos los cierres que caen en este mes
            cierres_del_mes = [c for c in all_cierres if fecha_inicio_mes <= c <= fecha_fin_mes]
            
            for cierre_dt in cierres_del_mes:
                idx = all_cierres.index(cierre_dt)
                if idx > 0: inicio_turno = all_cierres[idx-1]
                else: inicio_turno = "2020-01-01 00:00:00"
                
                gan_turno = self.controller.calc_ganancia_rango_ars(inicio_turno, cierre_dt, "ARS")
                
                lista_turnos.append({
                    "fecha": cierre_dt,
                    "ganancia": gan_turno,
                    "estado": "CERRADO"
                })
            
            # TURNO EN CURSO (Solo si es mes actual)
            now = datetime.now()
            if str(now.year) == anio and now.month == mes_idx:
                ultimo_cierre = all_cierres[-1] if all_cierres else "2020-01-01 00:00:00"
                gan_en_curso = self.controller.calc_ganancia_rango_ars(ultimo_cierre, now.strftime("%Y-%m-%d %H:%M:%S"), "ARS")
                lista_turnos.append({
                    "fecha": "EN CURSO (Ahora)",
                    "ganancia": gan_en_curso,
                    "estado": "ABIERTO"
                })

            lista_turnos.reverse()
            
            self.after(0, lambda: self.render_reporte(ganancia_mes, ganancia_total, volumen_mes, lista_turnos))
            
        except Exception as e:
            print(f"Error reporte: {e}")

    def render_reporte(self, gan_mes, gan_total, vol_mes, turnos):
        # 1. Ganancia Mes
        col_gm = "#2ecc71" if gan_mes >= 0 else "#e74c3c"
        self.card_ganancia_mes.configure(text=f"$ {gan_mes:,.0f}", text_color=col_gm)
        
        # 2. Ganancia Histórica (Color Dorado/Naranja para diferenciar)
        col_gh = "#f39c12" if gan_total >= 0 else "#e74c3c"
        self.card_ganancia_total.configure(text=f"$ {gan_total:,.0f}", text_color=col_gh)
        
        # 3. Volumen
        self.card_volumen.configure(text=f"$ {vol_mes:,.0f}")
        
        # Lista Turnos
        for widget in self.scroll_turnos.winfo_children(): widget.destroy()
            
        for t in turnos:
            row = ctk.CTkFrame(self.scroll_turnos, fg_color="transparent")
            row.pack(fill="x", pady=5)
            
            dt_str = t['fecha']
            try:
                if "EN CURSO" not in dt_str:
                    obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    dt_str = obj.strftime("%d/%m %H:%Mhs")
            except: pass
            
            ctk.CTkLabel(row, text=dt_str, width=150, anchor="w", font=("Arial", 12)).pack(side="left")
            
            g = t['ganancia']
            col_g = "#2ecc71" if g >= 0 else "#e74c3c"
            ctk.CTkLabel(row, text=f"$ {g:,.0f}", width=150, anchor="w", font=("Arial", 12, "bold"), text_color=col_g).pack(side="left")
            
            est = t['estado']
            col_e = "#3498db" if est == "ABIERTO" else "gray"
            ctk.CTkLabel(row, text=est, width=100, anchor="w", font=("Arial", 10, "bold"), text_color=col_e).pack(side="left")
            
            ctk.CTkFrame(self.scroll_turnos, height=1, fg_color="#333").pack(fill="x")
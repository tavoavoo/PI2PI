import customtkinter as ctk
from tkinter import TclError

class CustomDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, message, type="info", callback=None):
        super().__init__(parent)
        self.callback = callback
        self.overrideredirect(True) 
        self.attributes('-topmost', True)
        self.frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1a1a1a", border_width=2, border_color="#333")
        self.frame.pack(fill="both", expand=True)
        colors = {"info": "#2cc985", "error": "#cf3030", "confirm": "#e3a319"}
        color = colors.get(type, "white")
        title_prefix = "✅" if type == "info" else "❌" if type == "error" else "⚠️"
        ctk.CTkLabel(self.frame, text=f"{title_prefix} {title}", font=("Arial", 16, "bold"), text_color=color).pack(pady=(20, 10))
        self.lbl_msg = ctk.CTkLabel(self.frame, text=message, font=("Arial", 13), text_color="gray90", justify="center")
        self.lbl_msg.pack(pady=10, padx=20)
        btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x")
        if type == "confirm":
            ctk.CTkButton(btn_frame, text="CANCELAR", width=100, fg_color="transparent", border_width=1, border_color="gray", hover_color="#333", command=self.close).pack(side="left", padx=(50, 10), expand=True)
            ctk.CTkButton(btn_frame, text="CONFIRMAR", width=100, fg_color=color, text_color="black", hover_color="#c98d0e", command=self.confirm_action).pack(side="left", padx=(10, 50), expand=True)
        else:
            ctk.CTkButton(btn_frame, text="ACEPTAR", width=120, fg_color=color, text_color="white" if type=="error" else "black", hover_color="#333", command=self.close).pack()
        
        self.update_idletasks()
        try:
            width = max(self.frame.winfo_reqwidth() + 40, 400)
            height = max(self.frame.winfo_reqheight() + 20, 200)
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except: pass
        self.configure(fg_color="#101010") 
        self.after(50, self._safe_grab) 

    def _safe_grab(self):
        try:
            if self.winfo_exists():
                self.grab_set()
                self.focus_force()
        except (TclError, Exception): pass

    def confirm_action(self):
        self.grab_release()
        self.destroy()
        if self.callback: self.master.after(100, self.callback)
    def close(self):
        self.grab_release()
        self.destroy()

class ModernModal(ctk.CTkToplevel):
    def __init__(self, master, title, width=400, height=300, **kwargs):
        super().__init__(master, **kwargs)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        try:
            x = master.winfo_x() + (master.winfo_width() // 2) - (width // 2)
            y = master.winfo_y() + (master.winfo_height() // 2) - (height // 2)
        except: x, y = 100, 100
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.configure(fg_color="#101010")
        self.card = ctk.CTkFrame(self, corner_radius=15, fg_color="#1e1e1e", border_width=2, border_color="#333333")
        self.card.pack(fill="both", expand=True)
        self.card.pack_propagate(False)
        close_btn = ctk.CTkButton(self.card, text="✕", width=30, height=30, fg_color="transparent", hover_color="#333", text_color="gray", command=self.close)
        close_btn.place(relx=0.92, rely=0.02)
        ctk.CTkLabel(self.card, text=title, font=("Arial", 18, "bold"), text_color="white").pack(pady=(20, 10))
        self.content_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=20, pady=5)
        self.after(50, self._safe_grab)

    def _safe_grab(self):
        try:
            if self.winfo_exists():
                self.grab_set()
                self.focus_force()
        except (TclError, Exception): pass

    def close(self):
        self.grab_release()
        self.destroy()
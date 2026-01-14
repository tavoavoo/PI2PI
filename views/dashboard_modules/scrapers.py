import subprocess
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

class DolaritoScraper:
    def __init__(self):
        # Opciones Ligeras (Histórico)
        self.options_light = Options()
        self.options_light.add_argument("--headless=new")
        self.options_light.add_argument("--no-sandbox")
        self.options_light.add_argument("--log-level=3")
        self.options_light.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Opciones Persistentes (Vivo)
        self.options_persistent = Options()
        self.options_persistent.add_argument("--headless")
        self.options_persistent.add_argument("--disable-gpu")
        self.options_persistent.add_argument("--no-sandbox")
        self.options_persistent.add_argument("--disable-dev-shm-usage")
        self.options_persistent.add_argument("--log-level=3")
        self.options_persistent.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver_vivo = None

    def _iniciar_driver(self, options):
        try:
            service = Service(ChromeDriverManager().install())
            service.creation_flags = subprocess.CREATE_NO_WINDOW
            return webdriver.Chrome(service=service, options=options)
        except: return None
    # --- HISTÓRICO BLINDADO (PARSER CORREGIDO) ---
    def cargar_historia_combinada(self):
        print("🦅 Buscando historia en Dolarito (Modo Precisión)...")
        driver = self._iniciar_driver(self.options_light)
        if not driver: return []
        
        registros_finales = []
        try:
            wait = WebDriverWait(driver, 15)
            driver.get("https://www.dolarito.ar/cotizaciones-historicas/ccl")
            
            # 1. CLICS DE PREPARACIÓN (Igual que antes)
            try:
                xp_mep = '//*[@id="switch:quotation-type-mep:thumb"]'
                xp_oficial = '//*[@id="switch:quotation-type-oficial:thumb"]'
                wait.until(EC.presence_of_element_located((By.XPATH, xp_mep)))
                driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, xp_mep))
                driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, xp_oficial))
                time.sleep(1)
                
                xpath_btn = '/html/body/div[3]/div/div/div[3]/div[2]/button[2]'
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_btn)))
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
            except: pass 

            # 2. EXTRACCIÓN INTELIGENTE
            xpath_contenedor = '//*[@id="chart-image"]/div[1]/div[2]'
            texto_crudo = wait.until(EC.visibility_of_element_located((By.XPATH, xpath_contenedor))).text
            
            lineas = [l.strip() for l in texto_crudo.split('\n') if l.strip()]
            
            regs = []
            i = 0
            
            # Definimos limpieza aquí para controlar errores específicos
            def clean_float_safe(t): 
                try:
                    # Quitamos símbolos de moneda, puntos de mil y espacios
                    limpio = t.replace('$','').replace('.','').replace(',','.').strip()
                    # Si está vacío o es un guion, devolvemos None
                    if not limpio or limpio == '-': return None
                    return float(limpio)
                except: return None

            dias_semana = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"]

            while i < len(lineas):
                linea = lineas[i].lower()
                
                # DETECTOR DE FECHA
                es_fecha = any(dia in linea for dia in dias_semana)
                
                if es_fecha:
                    
                    if i + 2 < len(lineas):
                        fecha_txt = lineas[i]
                        precio_1_txt = lineas[i+1] # MEP
                        precio_2_txt = lineas[i+2] # CCL
                        
                        val_mep = clean_float_safe(precio_1_txt)
                        val_ccl = clean_float_safe(precio_2_txt)

                        # Si alguno es None, es que el dato estaba sucio, pero NO saltamos el día ciegamente
                        if val_mep is not None and val_ccl is not None and val_mep > 0:
                            gap = ((val_ccl / val_mep) - 1) * 100
                            regs.append({"fecha": fecha_txt, "gap": gap})
                            i += 3 
                            continue
                        else:
                            i += 1 
                            continue
                
                i += 1

            # 3. ORDENAMIENTO (FILTRO DE DUPLICADOS DE "HOY")
            # Si tu cuadro "HOY" (el azul) ya muestra la data en vivo, 
            # necesitamos que la historia sean los 4 días ANTERIORES a hoy.
            
            # Eliminamos el primer registro si es "Miércoles" (siendo hoy Miércoles) para evitar duplicados visuales
            # Ojo: esto es una regla de negocio. Si quieres ver los últimos 5 CERRADOS, usa esto:
            
            # Lógica: Tomamos los primeros 5 encontrados
            top_recientes = regs[:4] 
            
            # Invertimos para orden cronológico
            registros_finales = top_recientes[::-1]
            
            # RESULTADO FINAL ESPERADO: [JUE, VIE, LUN, MAR, (MIE-hoy quitado o puesto al final)]
            # Como tu dashboard tiene un cuadro "HOY" separado, aquí probablemente quieras excluir el día actual si ya cerró.
            
            print(f"✅ Historia final cargada: {len(registros_finales)} registros.")
            
        except Exception as e:
            print(f"🔥 Error Histórico General: {e}")
        finally:
            if driver: driver.quit()
            
        return registros_finales

    # --- VIVO BLINDADO (ESTO SOLUCIONA TU ERROR) ---
    def obtener_precios_vivo(self):
        # Si no existe driver, lo creamos
        if self.driver_vivo is None:
            # print("🦅 Iniciando Motor Persistente...")
            self.driver_vivo = self._iniciar_driver(self.options_persistent)
        
        try:
            # Si el driver murió por alguna razón externa, lo revivimos
            try:
                self.driver_vivo.current_url
            except:
                self.driver_vivo = self._iniciar_driver(self.options_persistent)

            self.driver_vivo.get("https://www.dolarito.ar/cotizacion/dolar-hoy")
            wait = WebDriverWait(self.driver_vivo, 10)
            
            # FUNCIÓN DE EXTRACCIÓN A PRUEBA DE BALAS
            # Si da error Stale, reintenta hasta 3 veces en milisegundos
            def safe_get_text(xpath):
                for _ in range(3): 
                    try:
                        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                        return element.text
                    except StaleElementReferenceException:
                        continue # La página parpadeó, reintentamos YA
                    except:
                        return None
                return None

            xp_blue = '//*[@id="quotation-informal-desktop"]/div'
            xp_mep  = '//*[@id="quotation-mep-desktop"]/div'
            xp_ccl  = '//*[@id="quotation-ccl-desktop"]/div'

            # Usamos la función blindada
            txt_blue = safe_get_text(xp_blue)
            txt_mep  = safe_get_text(xp_mep)
            txt_ccl  = safe_get_text(xp_ccl)

            if not txt_blue or not txt_mep:
                raise Exception("Lectura vacía")

            def parse(txt):
                try:
                    parts = txt.replace("\n", "|").split('|')
                    pct = parts[0].strip()
                    val = float(parts[-1].strip().replace('.','').replace(',','.'))
                    return val, pct
                except: return 0.0, "---"

            return {
                "blue": parse(txt_blue),
                "mep": parse(txt_mep),
                "ccl": parse(txt_ccl)
            }

        except Exception as e:
            # Solo si falla catastróficamente reiniciamos
            # print(f"⚠️ Error Vivo: {e}")
            try: self.driver_vivo.quit()
            except: pass
            self.driver_vivo = None
            return None

# --- AGREGA ESTO AL FINAL DE TU CLASE DolaritoScraper ---
    def analizar_mercado(self, historia, vivo):
        """
        Calcula si conviene COMPRAR o VENDER basándose en la historia vs hoy.
        """
        # Si faltan datos, devolvemos neutro
        if not historia or not vivo:
            return {"accion": "CARGANDO...", "subtexto": "Esperando datos", "tipo": "neutral", "rec_contable": "ESPERAR"}

        try:
            # 1. Sacamos datos
            val_mep = vivo.get('mep', [0])[0]
            val_ccl = vivo.get('ccl', [0])[0]
            
            if val_mep == 0: return {"accion": "ERROR", "subtexto": "Sin precio MEP", "tipo": "error"}

            gap_hoy = ((val_ccl / val_mep) - 1) * 100
            
            # 2. Promedio de los últimos 4 días
            gaps_historicos = [d['gap'] for d in historia]
            if not gaps_historicos:
                promedio = gap_hoy
            else:
                promedio = sum(gaps_historicos) / len(gaps_historicos)

            delta = gap_hoy - promedio

            # 3. Veredicto (Umbral de 0.8% de diferencia)
            if delta < -0.8:
                # El GAP bajó -> Está BARATO -> Conviene ACUMULAR
                return {
                    "accion": f"ACUMULAR ({gap_hoy:.1f}%)",
                    "subtexto": f"Oportunidad: -{abs(delta):.1f}% vs media",
                    "tipo": "compra",         # Verde
                    "rec_contable": "SUMAR VOLUMEN"
                }
            
            elif delta > 0.8:
                # El GAP subió -> Está CARO -> Conviene VENDER
                return {
                    "accion": f"LIQUIDAR ({gap_hoy:.1f}%)",
                    "subtexto": f"Ganancia extra: +{delta:.1f}% vs media",
                    "tipo": "venta",          # Rojo
                    "rec_contable": "VENDER / CUBRIR"
                }
            
            else:
                # Está normal -> ROTAR
                return {
                    "accion": f"ROTAR ({gap_hoy:.1f}%)",
                    "subtexto": "Mercado estable. Arbitraje rápido.",
                    "tipo": "neutral",        # Azul
                    "rec_contable": "MANTENER CICLO"
                }

        except Exception as e:
            print(f"Error lógica mercado: {e}")
            return {"accion": "ERROR", "subtexto": "Fallo cálculo", "tipo": "error"}
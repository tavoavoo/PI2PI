import requests
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

# ==========================================================
# 1. MOTOR BINANCE (PARA EL RADAR / SCALPING) - Usa Requests
# ==========================================================
class BinanceP2PScraper:
    def __init__(self):
        self.url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        self.url_price = "https://api.binance.com/api/v3/ticker/price" # Para ETH/USDT
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }

    def get_p2p_price(self, trade_type):
        """Método CLÁSICO para el dashboard viejo (Solo mejor precio)"""
        try:
            data = self._fetch_p2p_data(trade_type, rows=1)
            if data:
                return float(data[0]['adv']['price'])
            return None
        except: return None

    def get_order_book_pressure(self):
        """Método NUEVO para el Radar (Analiza Volumen Top 10)"""
        try:
            oferta_data = self._fetch_p2p_data("BUY", rows=10) # Vendedores
            demanda_data = self._fetch_p2p_data("SELL", rows=10) # Compradores

            if not oferta_data or not demanda_data: return None

            # Volumen acumulado (Fuerza del mercado)
            volumen_oferta = sum([float(ad['adv']['surplusAmount']) for ad in oferta_data])
            volumen_demanda = sum([float(ad['adv']['surplusAmount']) for ad in demanda_data])
            
            # Precios punta
            precio_compra = float(oferta_data[0]['adv']['price'])
            precio_venta = float(demanda_data[0]['adv']['price'])

            return {
                "precio_compra": precio_compra,
                "precio_venta": precio_venta,
                "volumen_oferta": volumen_oferta,
                "volumen_demanda": volumen_demanda,
                "spread": precio_venta - precio_compra
            }
        except Exception as e:
            print(f"Error pressure: {e}")
            return None

    def get_eth_price(self):
        """Obtiene precio ETH/USDT para medir sentimiento global"""
        try:
            params = {"symbol": "ETHUSDT"}
            resp = requests.get(self.url_price, params=params, timeout=3)
            data = resp.json()
            return float(data['price'])
        except: return 0.0

    def _fetch_p2p_data(self, trade_type, rows=1):
        payload = {
            "asset": "USDT",
            "fiat": "ARS",
            "merchantCheck": False,
            "page": 1,
            "rows": rows,
            "payTypes": ["MercadoPago"], 
            "publisherType": None,
            "tradeType": trade_type,
            "transAmount": "50000"
        }
        try:
            response = requests.post(self.url, json=payload, headers=self.headers, timeout=5)
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                return data["data"]
            return []
        except:
            return []

# ==========================================================
# 2. MOTOR DOLARITO (PARA EL CLÁSICO / MEP) - Usa Selenium BLINDADO
# ==========================================================
class DolaritoScraper:
    def __init__(self):
        # CONFIGURACIÓN ANTI-CRASH
        def configurar_opciones():
            opts = Options()
            # Modo Headless clásico (más estable que =new a veces)
            opts.add_argument("--headless=new") 
            
            # Argumentos vitales para evitar crash de memoria
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-extensions")
            opts.add_argument("--disable-software-rasterizer")
            
            # Anti-Detección (Stealth)
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option('useAutomationExtension', False)
            opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            opts.add_argument("--log-level=3") # Silenciar logs
            return opts

        self.options_light = configurar_opciones()
        self.options_persistent = configurar_opciones()
        
        self.driver_vivo = None

    def _iniciar_driver(self, options):
        try:
            # Reinstala el driver si es necesario para coincidir con el navegador
            service = Service(ChromeDriverManager().install())
            try:
                # Ocultar ventana de consola en Windows
                service.creation_flags = subprocess.CREATE_NO_WINDOW
            except: pass
            
            driver = webdriver.Chrome(service=service, options=options)
            
            # Truco extra de evasión
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                    })
                """
            })
            return driver
        except Exception as e:
            print(f"Error fatal iniciando Driver: {e}")
            return None

    # --- HISTÓRICO BLINDADO ---
    def cargar_historia_combinada(self):
        print("🦅 Buscando historia en Dolarito (Modo Precisión)...")
        driver = self._iniciar_driver(self.options_light)
        if not driver: return []
        
        registros_finales = []
        try:
            wait = WebDriverWait(driver, 20) # Aumentamos tiempo de espera
            driver.get("https://www.dolarito.ar/cotizaciones-historicas/ccl")
            
            # 1. CLICS DE PREPARACIÓN
            try:
                # Esperamos que cargue el body primero
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                xp_mep = '//*[@id="switch:quotation-type-mep:thumb"]'
                xp_oficial = '//*[@id="switch:quotation-type-oficial:thumb"]'
                
                # Intentamos click JS directo
                driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, xp_mep))
                driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, xp_oficial))
                time.sleep(1)
                
                xpath_btn = '/html/body/div[3]/div/div/div[3]/div[2]/button[2]'
                btn = driver.find_element(By.XPATH, xpath_btn)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
            except: 
                pass # Si fallan los clicks, intentamos leer igual

            # 2. EXTRACCIÓN INTELIGENTE
            xpath_contenedor = '//*[@id="chart-image"]/div[1]/div[2]'
            try:
                texto_crudo = wait.until(EC.visibility_of_element_located((By.XPATH, xpath_contenedor))).text
            except TimeoutException:
                print("⚠️ Timeout esperando gráfico. Dolarito lento.")
                return []
            
            lineas = [l.strip() for l in texto_crudo.split('\n') if l.strip()]
            
            regs = []
            i = 0
            
            def clean_float_safe(t): 
                try:
                    limpio = t.replace('$','').replace('.','').replace(',','.').strip()
                    if not limpio or limpio == '-': return None
                    return float(limpio)
                except: return None

            dias_semana = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"]

            while i < len(lineas):
                linea = lineas[i].lower()
                es_fecha = any(dia in linea for dia in dias_semana)
                
                if es_fecha:
                    if i + 2 < len(lineas):
                        fecha_txt = lineas[i]
                        precio_1_txt = lineas[i+1] # MEP
                        precio_2_txt = lineas[i+2] # CCL
                        
                        val_mep = clean_float_safe(precio_1_txt)
                        val_ccl = clean_float_safe(precio_2_txt)

                        if val_mep is not None and val_ccl is not None and val_mep > 0:
                            gap = ((val_ccl / val_mep) - 1) * 100
                            regs.append({"fecha": fecha_txt, "gap": gap})
                            i += 3 
                            continue
                        else:
                            i += 1 
                            continue
                i += 1

            # 3. ORDENAMIENTO
            top_recientes = regs[:4] 
            registros_finales = top_recientes[::-1]
            
            print(f"✅ Historia final cargada: {len(registros_finales)} registros.")
            
        except Exception as e:
            print(f"🔥 Error Histórico General: {e}")
        finally:
            if driver: 
                try: driver.quit()
                except: pass
            
        return registros_finales

    # --- VIVO BLINDADO ---
    def obtener_precios_vivo(self):
        # Reiniciar driver si murió
        if self.driver_vivo is not None:
            try:
                self.driver_vivo.current_url
            except:
                self.driver_vivo = None

        if self.driver_vivo is None:
            self.driver_vivo = self._iniciar_driver(self.options_persistent)
            if not self.driver_vivo: return None
        
        try:
            self.driver_vivo.get("https://www.dolarito.ar/cotizacion/dolar-hoy")
            wait = WebDriverWait(self.driver_vivo, 15)
            
            def safe_get_text(xpath):
                for _ in range(3): 
                    try:
                        element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                        return element.text
                    except StaleElementReferenceException:
                        time.sleep(0.5)
                        continue 
                    except:
                        return None
                return None

            xp_blue = '//*[@id="quotation-informal-desktop"]/div'
            xp_mep  = '//*[@id="quotation-mep-desktop"]/div'
            xp_ccl  = '//*[@id="quotation-ccl-desktop"]/div'

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
            # print(f"⚠️ Error Vivo (Reintentando): {e}")
            try: self.driver_vivo.quit()
            except: pass
            self.driver_vivo = None
            return None

    def analizar_mercado(self, historia, vivo):
        """Calcula si conviene COMPRAR o VENDER basándose en la historia vs hoy."""
        if not historia or not vivo:
            return {"accion": "CARGANDO...", "subtexto": "Esperando datos", "tipo": "neutral", "rec_contable": "ESPERAR"}

        try:
            val_mep = vivo.get('mep', [0])[0]
            val_ccl = vivo.get('ccl', [0])[0]
            
            if val_mep == 0: return {"accion": "ERROR", "subtexto": "Sin precio MEP", "tipo": "error"}

            gap_hoy = ((val_ccl / val_mep) - 1) * 100
            
            gaps_historicos = [d['gap'] for d in historia]
            if not gaps_historicos:
                promedio = gap_hoy
            else:
                promedio = sum(gaps_historicos) / len(gaps_historicos)

            delta = gap_hoy - promedio

            if delta < -0.8:
                return {
                    "accion": f"ACUMULAR ({gap_hoy:.1f}%)",
                    "subtexto": f"Oportunidad: -{abs(delta):.1f}% vs media",
                    "tipo": "compra",
                    "rec_contable": "SUMAR VOLUMEN"
                }
            elif delta > 0.8:
                return {
                    "accion": f"LIQUIDAR ({gap_hoy:.1f}%)",
                    "subtexto": f"Ganancia extra: +{delta:.1f}% vs media",
                    "tipo": "venta",
                    "rec_contable": "VENDER / CUBRIR"
                }
            else:
                return {
                    "accion": f"ROTAR ({gap_hoy:.1f}%)",
                    "subtexto": "Mercado estable. Arbitraje rápido.",
                    "tipo": "neutral",
                    "rec_contable": "MANTENER CICLO"
                }

        except Exception as e:
            # print(f"Error lógica mercado: {e}")
            return {"accion": "ERROR", "subtexto": "Fallo cálculo", "tipo": "error"}
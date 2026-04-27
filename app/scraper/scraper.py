import re
import time
from functools import reduce

from bs4 import BeautifulSoup

PAGE_URL_SUFFIX = '-pagina-'
HTML_EXTENSION = '.html'
BASE_URL = 'https://www.zonaprop.com.ar'

FEATURE_UNIT_DICT = {
    'm²': 'm2',
    'm2': 'm2',
    'amb': 'ambientes',
    'ambiente': 'ambientes',
    'ambientes': 'ambientes',
    'dorm': 'dormitorios',
    'dormitorio': 'dormitorios',
    'dormitorios': 'dormitorios',
    'baño': 'banos',
    'baños': 'banos',
    'bano': 'banos',
    'banos': 'banos',
    'coch': 'cocheras',
    'cochera': 'cocheras',
    'cocheras': 'cocheras',
    }

LABEL_DICT = {
    'POSTING_CARD_PRICE' : 'price',
    'expensas' : 'expenses',
    'POSTING_CARD_LOCATION' : 'location',
    'POSTING_CARD_DESCRIPTION' : 'description',
}

class Scraper:
    def __init__(self, browser, base_url, fetch_details=True):
        self.browser = browser
        self.base_url = base_url
        self.fetch_details = fetch_details  # Si True, obtiene m2 de página de detalle

    def scrap_page(self, page_number):
        if page_number == 1:
            page_url = f'{self.base_url}{HTML_EXTENSION}'
        else:
            page_url = f'{self.base_url}{PAGE_URL_SUFFIX}{page_number}{HTML_EXTENSION}'

        print(f'URL: {page_url}')

        page = self.browser.get_text(page_url)

        soup = BeautifulSoup(page, 'lxml')
        estate_posts = soup.find_all('div', attrs = {'data-posting-type' : True})
        estates = []
        for estate_post in estate_posts:
            estate = self.parse_estate(estate_post)
            estates.append(estate)
        return estates

    def scrap_website(self):
        page_number = 1
        estates = []
        estates_quantity = self.get_estates_quantity()
        while len(estates) < estates_quantity:
            print(f'Page: {page_number}')
            page_results = self.scrap_page(page_number)
            if not page_results:
                break
            estates += page_results
            page_number += 1
            time.sleep(1)

        return estates


    def get_estates_quantity(self):
        page_url = f'{self.base_url}{HTML_EXTENSION}'
        page = self.browser.get_text(page_url)
        soup = BeautifulSoup(page, 'lxml')
        try:
            h1_text = soup.find_all('h1')[0].text
            matches = re.findall(r'\d[\d.]*', h1_text)
            if not matches:
                return 999  # fallback: scrape hasta que no haya más resultados
            estates_quantity = int(matches[0].replace('.', ''))
            return estates_quantity if estates_quantity > 0 else 999
        except (IndexError, ValueError):
            return 999

    def parse_estate(self, estate_post):
        # find any element with data-qa attribute (not just div - price is now h2)
        data_qa = estate_post.find_all(attrs={'data-qa': True})
        url = estate_post.get_attribute_list('data-to-posting')[0]
        
        # Convertir URL relativa a URL completa
        if url and url.startswith('/'):
            url = BASE_URL + url
        elif url and not url.startswith('http'):
            url = BASE_URL + '/' + url
        
        estate = {}
        estate['url'] = url
        estate['link'] = url  # Agregar también como 'link' para claridad
        
        # Inicializar características con valores None por defecto
        features = {
            'm2_totales': None,
            'm2_cubiertos': None,
            'm2_descubiertos': None,
            'ambientes': None,
            'dormitorios': None,
            'banos': None,
            'cocheras': None
        }
        
        for data in data_qa:
            label = data['data-qa']
            text = None
            if label in ['POSTING_CARD_PRICE', 'expensas']:
                currency_value, currency_type = self.parse_currency_value(data.get_text())
                estate[LABEL_DICT[label] + '_' + 'value'] = currency_value
                estate[LABEL_DICT[label] + '_' + 'type'] = currency_type
            elif label in ['POSTING_CARD_LOCATION', 'POSTING_CARD_DESCRIPTION']:
                text = self.parse_text(data.get_text())
                estate[LABEL_DICT[label]] = text
            elif label in ['POSTING_CARD_FEATURES']:
                parsed_features = self.parse_features(data.get_text())
                features.update(parsed_features)
            else:
                text = data.get_text()
                estate[label] = text
        
        # También buscar características en otros lugares si no se encontraron
        if all(v is None for v in features.values()):
            # Buscar en el texto completo del estate_post
            full_text = estate_post.get_text()
            parsed_features = self.parse_features(full_text)
            features.update(parsed_features)
        
        # Si fetch_details está activado, obtener m2 de la página de detalle
        # (el listado no siempre muestra m2 cubiertos y descubiertos separados)
        if self.fetch_details and url:
            detail_features = self.get_detail_features(url)
            # Solo actualizar si obtuvimos valores válidos del detalle
            if detail_features.get('m2_totales'):
                features['m2_totales'] = detail_features['m2_totales']
            if detail_features.get('m2_cubiertos'):
                features['m2_cubiertos'] = detail_features['m2_cubiertos']
            if detail_features.get('m2_descubiertos'):
                features['m2_descubiertos'] = detail_features['m2_descubiertos']
        
        # Agregar características al estate
        estate.update(features)
        
        return estate
    
    def get_detail_features(self, url):
        """Obtiene m2 totales, cubiertos y descubiertos de la página de detalle."""
        features = {
            'm2_totales': None,
            'm2_cubiertos': None,
            'm2_descubiertos': None
        }
        
        try:
            # Pequeña pausa para no sobrecargar el servidor
            time.sleep(0.5)
            page = self.browser.get_text(url)
            soup = BeautifulSoup(page, 'lxml')
            
            # En la página de detalle, los m2 están en listitem con formato "X m² tot." y "X m² cub."
            # Buscar todos los listitem que contengan información de m²
            list_items = soup.find_all('li')
            
            for item in list_items:
                text = item.get_text().strip()
                
                # Buscar m² totales
                tot_match = re.search(r'(\d+\.?\d*)\s*m[²2]\s*(?:tot\.?|total)', text, re.IGNORECASE)
                if tot_match:
                    features['m2_totales'] = tot_match.group(1)
                
                # Buscar m² cubiertos
                cub_match = re.search(r'(\d+\.?\d*)\s*m[²2]\s*(?:cub\.?|cubierto)', text, re.IGNORECASE)
                if cub_match:
                    features['m2_cubiertos'] = cub_match.group(1)
            
            # Calcular descubiertos
            if features['m2_totales'] and features['m2_cubiertos']:
                try:
                    total = float(features['m2_totales'])
                    cubierto = float(features['m2_cubiertos'])
                    descubierto = total - cubierto
                    if descubierto > 0:
                        features['m2_descubiertos'] = str(int(descubierto)) if descubierto == int(descubierto) else str(descubierto)
                    else:
                        features['m2_descubiertos'] = '0'
                except (ValueError, TypeError):
                    pass
                    
        except Exception as e:
            print(f'Error obteniendo detalle de {url}: {e}')
        
        return features

    def parse_currency_value(self, text):
        try:
            currency_value = re.findall(r'\d+\.?\d+', text)[0]
            currency_value = currency_value.replace('.', '')
            currency_value = int(currency_value)
            currency_type = re.findall(r'(USD)|(ARS)|(\$)', text)[0]
            currency_type = [x for x in currency_type if x != ''][0]
            return currency_value, currency_type
        except:
            return text, None

    def parse_text(self, text):
        text = text.replace('\n', '')
        text = text.replace('\t', '')
        text = text.strip()
        return text

    def parse_features(self, text):
        # Inicializar con valores None para asegurar que siempre existan las columnas
        features = {
            'm2_totales': None,
            'm2_cubiertos': None,
            'm2_descubiertos': None,
            'ambientes': None,
            'dormitorios': None,
            'banos': None,
            'cocheras': None
        }
        
        if not text:
            return features
        
        # Limpiar el texto
        text = text.strip()
        
        # Primero intentar capturar con etiquetas específicas (formato página de detalle)
        # Ejemplos: "109 m² tot.", "80 m² cub.", "109 m² total", "80 m² cubiertos"
        tot_pattern = r'(\d+\.?\d*)\s*m[²2]\s*(?:tot\.?|total(?:es)?)'
        cub_pattern = r'(\d+\.?\d*)\s*m[²2]\s*(?:cub\.?|cubierto(?:s)?)'
        
        tot_match = re.search(tot_pattern, text, re.IGNORECASE)
        cub_match = re.search(cub_pattern, text, re.IGNORECASE)
        
        if tot_match or cub_match:
            # Hay etiquetas específicas, usar esos valores
            if tot_match:
                features['m2_totales'] = tot_match.group(1)
            if cub_match:
                features['m2_cubiertos'] = cub_match.group(1)
            
            # Si solo hay total, asumir que cubierto = total
            if tot_match and not cub_match:
                features['m2_cubiertos'] = tot_match.group(1)
            # Si solo hay cubierto, asumir que total = cubierto
            if cub_match and not tot_match:
                features['m2_totales'] = cub_match.group(1)
        else:
            # No hay etiquetas, usar método por posición
            # ZonaProp en listado muestra dos valores de m²: primero total, segundo cubierto
            m2_pattern = r'(\d+\.?\d*)\s*m[²2]'
            m2_matches = re.findall(m2_pattern, text, re.IGNORECASE)
            
            if len(m2_matches) >= 2:
                # Primer valor = total, segundo valor = cubierto
                features['m2_totales'] = m2_matches[0]
                features['m2_cubiertos'] = m2_matches[1]
            elif len(m2_matches) == 1:
                # Solo un valor, asumimos que es total = cubierto
                features['m2_totales'] = m2_matches[0]
                features['m2_cubiertos'] = m2_matches[0]
        
        # Calcular descubierto como diferencia
        if features['m2_totales'] and features['m2_cubiertos']:
            try:
                total = float(features['m2_totales'])
                cubierto = float(features['m2_cubiertos'])
                descubierto = total - cubierto
                if descubierto > 0:
                    features['m2_descubiertos'] = str(int(descubierto)) if descubierto == int(descubierto) else str(descubierto)
                else:
                    features['m2_descubiertos'] = '0'
            except (ValueError, TypeError):
                features['m2_descubiertos'] = None
        
        # Patrón para ambientes (amb, ambiente, ambientes)
        amb_pattern = r'(\d+)\s*(?:amb|ambiente|ambientes)'
        amb_match = re.search(amb_pattern, text, re.IGNORECASE)
        if amb_match:
            features['ambientes'] = amb_match.group(1)
        
        # Patrón para dormitorios (dorm, dormitorio, dormitorios)
        dorm_pattern = r'(\d+)\s*(?:dorm|dormitorio|dormitorios)'
        dorm_match = re.search(dorm_pattern, text, re.IGNORECASE)
        if dorm_match:
            features['dormitorios'] = dorm_match.group(1)
        
        # Patrón para baños (baño, baños, bano, banos)
        bano_pattern = r'(\d+)\s*(?:baño|baños|bano|banos)'
        bano_match = re.search(bano_pattern, text, re.IGNORECASE)
        if bano_match:
            features['banos'] = bano_match.group(1)
        
        # Patrón para cocheras (coch, cochera, cocheras)
        coch_pattern = r'(\d+)\s*(?:coch|cochera|cocheras)'
        coch_match = re.search(coch_pattern, text, re.IGNORECASE)
        if coch_match:
            features['cocheras'] = coch_match.group(1)
        
        return features

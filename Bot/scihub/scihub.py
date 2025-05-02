# scihub.py
import requests
import re


class SciHubClient:
    def __init__(self):
        self.base_urls = [
            "https://sci-hub.se/",
            "https://sci-hub.st/",
            "https://sci-hub.cc",
            "https://sci-hub.hk",
            "https://sci-hub.tw",
            "https://sci-hub.la",
            "https://sci-hub.mn",
            "https://sci-hub.name",
            "https://sci-hub.is",
            "https://sci-hub.tv",
            "https://sci-hub.ws",
            "https://www.sci-hub.cn",
            "https://sci-hub.sci-hub.hk",
            "https://sci-hub.sci-hub.tw",
            "https://sci-hub.sci-hub.mn",
            "https://sci-hub.sci-hub.tv",
            "https://tree.sci-hub.la",
            # Puedes agregar más mirrors si quieres
        ]
        self.session = requests.Session()

    def search_pdf_url(self, query: str):
        """
        Busca el PDF de un paper dado un DOI o URL.
        Retorna URL directo al PDF o None si no se encuentra.
        """
        doi = self._extract_doi(query)
        if not doi:
            return None

        for base_url in self.base_urls:
            try:
                url = f"{base_url}{doi}"
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    pdf_url = self._extract_pdf_url(resp.text)
                    if pdf_url:
                        # Si el enlace es relativo, lo completamos
                        if not pdf_url.startswith("http"):
                            pdf_url = base_url.rstrip("/") + pdf_url
                        return pdf_url
            except Exception:
                continue
        return None

    def _extract_doi(self, text: str):
        doi_pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"
        match = re.search(doi_pattern, text, re.I)
        return match.group(0) if match else None

    def _extract_pdf_url(self, html: str):
        # Busca el enlace directo al PDF en el HTML de Sci-Hub
        # El patrón puede cambiar, aquí un ejemplo común:
        pattern = r'<iframe[^>]+src="([^"]+\.pdf)"'
        match = re.search(pattern, html)
        if match:
            return match.group(1)
        # Alternativa: buscar botones de descarga
        pattern_alt = r'<a[^>]+href="([^"]+\.pdf)"[^>]*>Download</a>'
        match_alt = re.search(pattern_alt, html)
        if match_alt:
            return match_alt.group(1)
        return None

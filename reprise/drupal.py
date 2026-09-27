"""Extraction d'une page publique Drupal (7, 9 ou 10) vers un enregistrement de lot d'import.

On lit la page telle que l'usager la voit : c'est la seule voie disponible quand ni JSON:API
ni export de base ne sont ouverts. Les sélecteurs couvrent les thèmes Drupal courants ;
un sélecteur propre au site peut être passé en paramètre.
"""
import re
import urllib.parse

import lxml.html

CORPS = [
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' field--name-body ')]",   # Drupal 8+
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' field-name-body ')]",    # Drupal 7
    "//article//div[contains(@class, 'node__content')]",
    "//main",
]
DOCS = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|odt|ods|zip|csv)$", re.I)
BALISES_TEXTE = {"p", "ul", "ol", "h2", "h3", "h4", "table", "blockquote"}


def _meta(doc, prop):
    v = doc.xpath(f"//meta[@property='{prop}' or @name='{prop}']/@content")
    return v[0].strip() if v else ""


def type_contenu(doc, classes_article):
    """Type de contenu Drupal : classe du <body> (D8+ : page-node-type-X ; D7 : node-type-X), sinon l'article principal."""
    corps = " ".join(doc.xpath("//body/@class"))
    m = re.search(r"\bpage-node-type-([\w-]+)", corps) or re.search(r"\bnode-type-([\w-]+)", corps)
    if m:
        return m.group(1)
    return classes_article[0] if classes_article else ""


def extraire(url, html_texte, selecteur=None):
    doc = lxml.html.fromstring(html_texte)
    doc.make_links_absolute(url)
    titre = (doc.xpath("string(//h1)") or _meta(doc, "og:title") or doc.findtext(".//title") or "").strip()
    titre = re.sub(r"\s*\|\s*[^|]+$", "", titre) if "|" in titre and not doc.xpath("//h1") else titre
    classes_article = (doc.xpath("//article[contains(concat(' ', normalize-space(@class), ' '), ' full ')]/@class")
                       or doc.xpath("//article/@class") or [""])[0].split()
    corps_el = None
    for xp in ([selecteur] if selecteur else []) + CORPS:
        r = doc.xpath(xp)
        if r:
            corps_el = r[0]
            break
    blocs, images, documents = [], [], []
    if corps_el is not None:
        for el in corps_el.iter():
            if el.tag == "img":
                images.append({"src": el.get("src", ""), "alt": (el.get("alt") or "").strip()})
            if el.tag == "a" and DOCS.search(urllib.parse.urlsplit(el.get("href", "")).path):
                documents.append({"href": el.get("href"), "texte": el.text_content().strip()})
        for el in corps_el.xpath(".//*[self::p or self::ul or self::ol or self::h2 or self::h3 or self::h4 or self::table or self::blockquote]"):
            if el.getparent() is not None and el.getparent().tag in BALISES_TEXTE | {"li"}:
                continue   # déjà pris avec son parent
            texte = el.text_content().strip()
            if not texte:
                continue
            if el.tag in ("h2", "h3", "h4"):
                blocs.append({"type": "intertitre", "texte": texte})
            else:
                blocs.append({"type": "paragraphe", "html": lxml.html.tostring(el, encoding="unicode"), "balise": el.tag})
    mots = [m.strip() for m in doc.xpath("//div[contains(@class,'mots-cles')]//a/text()") if m.strip()]
    return {
        "url_source": url,
        "chemin_source": urllib.parse.urlsplit(url).path or "/",
        "titre": titre,
        "type_drupal": type_contenu(doc, classes_article),
        "description": _meta(doc, "description"),
        "publie_le": _meta(doc, "article:published_time"),
        "modifie_le": _meta(doc, "article:modified_time"),
        "mots_cles": mots,
        "blocs": blocs,
        "images": images,
        "documents": documents,
        "canonical": (doc.xpath("//link[@rel='canonical']/@href") or [""])[0],
    }

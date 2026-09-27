"""Blocs StreamField « Tableau de données » et « Carte par commune » : configuration sans code, page par page."""
import re
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import FloatField, Q
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock

from . import calculs


DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:T00:00:00(?:\.0+)?(?:Z|[+-]00:00)?)?")


def lisible(v):
    """Valeur affichable : les listes deviennent un texte séparé par des points-virgules."""
    if isinstance(v, list):
        return " ; ".join(str(x) for x in v)
    if isinstance(v, dict):
        return " ; ".join(f"{k} : {x}" for k, x in v.items())
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and abs(v) >= 1000:
        return f"{v:,}".replace(",", "\u202f")
    if isinstance(v, float):
        return f"{v:,.0f}".replace(",", "\u202f") if v.is_integer() else f"{v:,.2f}".replace(",", "\u202f").replace(".", ",")
    if v == "EX":  # barème douanier officiel (unrtxtab) : « Tout D&T Taux exempt »
        return "Exonéré (EX)"
    if isinstance(v, str):
        m = DATE_ISO.fullmatch(v)
        if m:  # 2022-05-12 ou 2022-05-12T00:00:00+00:00 -> 12/05/2022
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return v


class ColonneBlock(blocks.StructBlock):
    champ = blocks.CharBlock(help_text="Nom du champ de la source (voir « État de la source »)")
    libelle = blocks.CharBlock(required=False, help_text="Intitulé affiché ; vide = nom du champ")

    class Meta:
        icon = "list-ul"


class IndicateurBlock(blocks.StructBlock):
    type = blocks.ChoiceBlock(choices=[("nombre", "Nombre de lignes"), ("distincts", "Nombre de valeurs distinctes d'un champ"),
                                       ("moyenne", "Moyenne d'un champ numérique"), ("ecart", "Écart moyen en % entre deux champs"),
                                       ("frequent", "Valeur la plus fréquente d'un champ")])
    champ = blocks.CharBlock(required=False)
    champ2 = blocks.CharBlock(required=False, help_text="Pour l'écart : champ comparé au premier")
    libelle = blocks.CharBlock(required=False, help_text="Texte sous le chiffre")

    class Meta:
        icon = "order"


def _base(value, request):
    """Lignes de la source après recherche et filtre à facette ; valeurs de contexte communes."""
    source = value["source"]
    q = (request.GET.get("q", "") if request else "").strip()
    f = (request.GET.get("f", "") if request else "").strip()
    lignes = source.lignes.all()
    if q:
        cond = Q()
        for mot in q.split():
            cond &= Q(texte__icontains=mot)
        lignes = lignes.filter(cond)
    champ_f = value.get("filtre_champ") or ""
    if f and champ_f:
        lignes = lignes.filter(**{f"donnees__{champ_f}": f})
    return source, lignes, q, f


class TableauBlock(blocks.StructBlock):
    source = SnippetChooserBlock("tableaux.SourceDonnees")
    titre = blocks.CharBlock(required=False)
    affichage = blocks.ChoiceBlock(choices=[("tableau", "Tableau"), ("carte", "Carte et tableau")], default="tableau",
                                   help_text="La carte exige un champ de localisation sur la source")
    indicateurs = blocks.ListBlock(IndicateurBlock(), label="Repères chiffrés", required=False,
                                   help_text="Calculés à chaque lecture de la source, jamais saisis")
    filtre_champ = blocks.CharBlock(required=False, label="Filtre en un clic sur le champ",
                                    help_text="Affiche les valeurs les plus fréquentes de ce champ comme filtres")
    colonnes = blocks.ListBlock(ColonneBlock(), label="Colonnes de la liste", min_num=1)
    colonnes_detail = blocks.ListBlock(ColonneBlock(), label="Champs de la fiche détail", required=False,
                                       help_text="Vide : tous les champs de la ligne")
    recherche = blocks.BooleanBlock(required=False, default=True, label="Champ de recherche")
    par_page = blocks.IntegerBlock(default=25, min_value=5, max_value=200, label="Lignes par page")
    abonnement = blocks.BooleanBlock(required=False, default=False, label="Proposer l'alerte e-mail")

    class Meta:
        icon = "table"
        template = "tableaux/bloc_tableau.html"
        label = "Tableau de données"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        request = (parent_context or {}).get("request")
        source, lignes, q, f = _base(value, request)
        cols = [(c["champ"], c["libelle"] or c["champ"]) for c in value["colonnes"]]

        # Tri par colonne (numérique si les valeurs le sont)
        tri = request.GET.get("tri", "") if request else ""
        ordre = request.GET.get("ordre", "asc") if request else "asc"
        if tri in dict(cols):
            premiere = source.lignes.exclude(**{f"donnees__{tri}": None}).first()
            # Une date jj/mm/aaaa se trie par sa copie aaaa-mm-jj (champ suffixé _iso) quand la source la fournit
            cle_tri = f"{tri}_iso" if premiere and f"{tri}_iso" in premiere.donnees else tri
            expr = KT(f"donnees__{cle_tri}")
            if premiere and isinstance(premiere.donnees.get(tri), (int, float)):
                expr = Cast(expr, FloatField())
            lignes = lignes.order_by(expr.desc(nulls_last=True) if ordre == "desc" else expr.asc(nulls_last=True))

        donnees_filtrees = [l.donnees for l in lignes] if (value.get("indicateurs") or value.get("filtre_champ")) else []
        toutes = [l.donnees for l in source.lignes.all()] if value.get("filtre_champ") else []
        reperes = [r for r in (calculs.indicateur(i, donnees_filtrees) for i in value.get("indicateurs") or []) if r]
        page = Paginator(lignes, value["par_page"]).get_page(request.GET.get("p") if request else 1)
        carte = None
        if value.get("affichage") == "carte":
            carte = {"points": calculs.points(lignes, cols[0][0]), "communes": calculs.COMMUNES}
        ctx.update({
            "source": source, "q": q, "f": f, "tri": tri, "ordre": ordre, "page_lignes": page, "colonnes": cols,
            "rangees": [(l, [lisible(l.donnees.get(ch)) for ch, _ in cols]) for l in page.object_list],
            "reperes": reperes, "facettes": calculs.facettes(toutes, value.get("filtre_champ")) if toutes else [],
            "carte": carte, "page": (parent_context or {}).get("page"),
            "numeros": numeros_pages(page.number, page.paginator.num_pages),
            "params": urlencode({k: v for k, v in (("q", q), ("f", f), ("tri", tri if tri else ""), ("ordre", ordre if tri else "")) if v}),
        })
        return ctx


def numeros_pages(n, total, autour=2):
    """Numéros à afficher : la première, la dernière et les voisines de la page courante ; None = « … »."""
    garde = sorted({1, total, *range(max(1, n - autour), min(total, n + autour) + 1)})
    out, prec = [], 0
    for k in garde:
        if k - prec > 1:
            out.append(None)
        out.append(k)
        prec = k
    return out


class CarteCommunesBlock(blocks.StructBlock):
    source = SnippetChooserBlock("tableaux.SourceDonnees")
    titre = blocks.CharBlock(required=False)
    champ_commune = blocks.CharBlock(help_text="Champ qui contient le nom de la commune")
    mesure = blocks.CharBlock(default="lignes", help_text="Ce que l'on compte, au pluriel (ex. établissements)")

    class Meta:
        icon = "site"
        template = "tableaux/bloc_carte_communes.html"
        label = "Carte par commune"

    def get_context(self, value, parent_context=None):
        ctx = super().get_context(value, parent_context)
        donnees = [l.donnees for l in value["source"].lignes.all()]
        comptes, hors = calculs.par_commune(donnees, value["champ_commune"])
        seuils = calculs.classes(list(comptes.values()))
        communes = calculs.COMMUNES["communes"]
        zones = [{"code": code, "nom": c["nom"], "d": c["d"], "n": comptes.get(code, 0),
                  "couleur": calculs.couleur(comptes.get(code, 0), seuils)} for code, c in communes.items()]
        legende, bas = [], 1
        for i, s in enumerate(seuils):
            legende.append((calculs.couleur(s, seuils), f"{calculs.fr(bas)} à {calculs.fr(s)}" if s > bas else calculs.fr(s)))
            bas = int(s) + 1
        ctx.update({"zones": zones, "viewbox": calculs.COMMUNES["viewbox"], "legende": legende, "hors": hors,
                    "classement": sorted(zones, key=lambda z: -z["n"]), "total": sum(comptes.values()),
                    "source": value["source"]})
        return ctx

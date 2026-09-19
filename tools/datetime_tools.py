import ast
import datetime
import operator


def obtenir_heure_actuelle() -> str:
    """Renvoie l'heure actuelle sur cet ordinateur, au format HH:MM."""
    return datetime.datetime.now().strftime("%H:%M")


def obtenir_date_actuelle() -> str:
    """Renvoie la date actuelle (jour de la semaine, jour, mois, année)."""
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    now = datetime.datetime.now()
    return f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"


_OPERATEURS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluer_noeud(noeud):
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp):
        op = _OPERATEURS.get(type(noeud.op))
        if op is None:
            raise ValueError("Opérateur non supporté")
        return op(_evaluer_noeud(noeud.left), _evaluer_noeud(noeud.right))
    if isinstance(noeud, ast.UnaryOp):
        op = _OPERATEURS.get(type(noeud.op))
        if op is None:
            raise ValueError("Opérateur non supporté")
        return op(_evaluer_noeud(noeud.operand))
    raise ValueError("Expression non supportée")


def calculer(expression: str) -> str:
    """Calcule le résultat d'une expression mathématique simple.

    Args:
        expression: une expression comme "12 * 7" ou "(45 + 5) / 2"
    """
    try:
        arbre = ast.parse(expression.strip(), mode="eval")
        return str(_evaluer_noeud(arbre.body))
    except Exception:
        return "Je n'ai pas réussi à calculer cette expression."

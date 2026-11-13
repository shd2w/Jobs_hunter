"""Experiment 2: smoke-test the B10 enrichment rules as written in doc 09.
PROTOTYPE ONLY. Test cases are hand-written by the designer, so passing proves the rules
are *implementable*, not that they are *accurate* on real postings."""
import re

EN = set("the and to of a in for with you will be is are our we as on at or by an your this that from have has it their us not all can more who work team".split())
DE = set("der die das und zu von mit für sie wir ihr ihre ist sind auf im in den dem des ein eine einer eines als auch bei oder nicht aus nach über zur zum werden wird haben sich unser unsere ihnen sowie".split())

def lang(text):
    toks = re.findall(r"[a-zäöüß']+", text.lower()); n = max(len(toks), 1)
    se = sum(t in EN for t in toks) / n; sd = sum(t in DE for t in toks) / n
    sd += 0.02 * bool(re.search(r"[äöüß]", text.lower()))
    if se < 0.08 and sd < 0.08: return ("other" if n >= 200 else "unknown", se, sd)
    if abs(se - sd) < 0.03: return ("bilingual:" + ("en" if se >= sd else "de"), se, sd)
    return ("en" if se > sd else "de", se, sd)

NUM = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,
       "ein":1,"eine":1,"zwei":2,"drei":3,"vier":4,"fünf":5,"sechs":6,"sieben":7,"acht":8,"neun":9,"zehn":10}
N = r"(\d{1,2}|" + "|".join(NUM) + r")"
RX = [  # (regex, group-handler)
 (re.compile(rf"{N}\s*(?:\+|plus)?\s*(?:[-–]|to|bis)\s*{N}\s*(?:years?|yrs?|jahre?n?)", re.I), "range"),
 (re.compile(rf"(?:mind(?:estens)?\.?|at least|minimum(?: of)?|über|more than)\s*{N}\s*(?:years?|yrs?|jahre?n?)", re.I), "single"),
 (re.compile(rf"{N}\s*\+?\s*(?:years?|yrs?|jahre?n?)", re.I), "single"),
 (re.compile(r"\b(?:langjährig\w*|mehrjährig\w*)", re.I), "vague"),
]
def num(x): return int(x) if x.isdigit() else NUM[x.lower()]
COMPANY_CUES = re.compile(r"\b(we|our|since|founded|gegründet|seit|unser\w*|wir)\b", re.I)

AGE = re.compile(r"(years?\s+(old|of age)|jahre\s+alt|jährig\w*\s+(alter|volljährig))", re.I)
def years(text, sectioned=True):
    """max of the *minimum* years over requirement-like sentences."""
    best = None
    for sent in re.split(r"(?<=[.!?\n])\s+|\n", text):
        if sectioned and COMPANY_CUES.search(sent) and not re.search(r"(you|ihr|sie|bring|expect|erwarten|require|candidate)", sent, re.I):
            continue                      # company-history sentence
        if AGE.search(sent): continue      # revised: ignore age statements
        for rx, kind in RX:
            m = rx.search(sent)
            if not m: continue
            if kind == "range": v = num(m.group(1))
            elif kind == "single": v = num(m.group(1))
            else: v = 5
            best = v if best is None else max(best, v); break
    return best

W = dict(years=0.50, scope=0.30, entry=0.60, title=0.15)
def seniority(title, text, title_only_hint=False):
    votes = {}
    def add(level, w): votes[level] = votes.get(level, 0) + w
    y = years(text)
    if y is not None:
        add("senior" if y >= 5 else "mid" if y >= 3 else "entry", W["years"])   # revised: years alone never => lead_exec
    scope = re.search(r"(lead a team|manage[sd]? a team|budget responsibility|Führungsverantwortung|Budgetverantwortung|Teamleitung|people management)", text, re.I)
    if scope: add("senior", W["scope"])
    exec_title = re.search(r"\b(director|head of|vp|vice president|chief|cto|ceo|cfo|geschäftsführer\w*|bereichsleiter\w*|abteilungsleiter\w*)\b", title, re.I)
    if exec_title or (scope and y is not None and y >= 8):
        votes.pop("senior", None); add("lead_exec", W["scope"] + W["title"])
    if re.search(r"(graduate|Berufseinsteiger|Werkstudent|Praktikum|Trainee|Ausbildung|entry[- ]level|no experience)", title + " " + text, re.I): add("entry", W["entry"])
    t = title.lower()
    if re.search(r"\b(senior|sr\.?|lead|principal|head|director|leiter\w*)\b", t): add("senior", W["title"])
    if re.search(r"\b(junior|jr\.?)\b", t): add("entry", W["title"])
    if y is not None and y >= 8 and votes.get("entry", 0) < W["entry"]: votes.pop("entry", None)  # override rule
    total = sum(votes.values())
    if total < 0.30:
        if title_only_hint and votes:  # proposed fix
            lvl = max(votes, key=votes.get); return (lvl, "title_only", round(total, 2))
        return ("unknown", None, round(total, 2))
    lvl = max(votes, key=votes.get); return (lvl, "ok", round(total, 2))

def check(name, got, want):
    ok = got == want; print(f"{'ok ' if ok else 'BAD'} {name}: got={got!r} want={want!r}"); return ok

if __name__ == "__main__":
    res = []
    print("--- language (hand-written snippets) ---")
    L = [
     ("en","We are looking for a data engineer who will work with our team to build pipelines for the company and you will have strong skills."),
     ("en","You will be responsible for the design of the platform and you have experience with cloud services as well as with databases."),
     ("de","Wir suchen eine Pflegefachkraft für unser Team. Sie sind für die Betreuung der Patienten verantwortlich und haben eine abgeschlossene Ausbildung."),
     ("de","Ihre Aufgaben: Sie übernehmen die Planung und Steuerung von Projekten in unserem Unternehmen und arbeiten mit dem Team zusammen."),
     ("de","Als Werkstudent unterstützen Sie das Marketing bei der Erstellung von Inhalten und der Auswertung von Kampagnen."),
     ("bilingual","Wir suchen Verstärkung für unser Team. We offer a hybrid setup and you will work with our engineers on the platform und die Kunden."),
     ("unknown","Software Engineer (m/w/d)"),
     ("unknown","Senior Projektleiter Bau"),
    ]
    for want, t in L:
        g = lang(t)[0]; ok = g.startswith(want) if want == "bilingual" else g == want
        print(f"{'ok ' if ok else 'BAD'} lang want={want:9} got={g:14} | {t[:60]}"); res.append(ok)
    print("--- non-EN/DE text must NOT be classed en/de (platform collects en+de only) ---")
    OTH = [
     ("fr","Nous recherchons un ingénieur de données pour rejoindre notre équipe. Vous serez responsable de la conception des pipelines et vous avez de l'expérience avec les bases de données dans le cadre de nos projets pour les clients de la société."),
     ("es","Buscamos un ingeniero de datos para unirse a nuestro equipo. Serás responsable del diseño de los pipelines y tienes experiencia con bases de datos en los proyectos para los clientes de la empresa."),
     ("nl","Wij zoeken een data engineer voor ons team. Je bent verantwoordelijk voor het ontwerp van de pipelines en je hebt ervaring met databases in de projecten voor de klanten van het bedrijf."),
     ("it","Cerchiamo un ingegnere dei dati per il nostro team. Sarai responsabile della progettazione delle pipeline e hai esperienza con i database nei progetti per i clienti dell'azienda."),
    ]
    for code, t in OTH:
        g = lang(t); ok = g[0] in ("other","unknown")
        print(f"{'ok ' if ok else 'BAD'} {code} classed as {g[0]:8} en={g[1]:.3f} de={g[2]:.3f}"); res.append(ok)
    print("--- years extraction ---")
    Y = [
     ("5+ years of experience in Python", 5), ("3-5 years of experience", 3), ("at least 7 years in sales", 7),
     ("mind. 3 Jahre Berufserfahrung", 3), ("mindestens 2 Jahre Erfahrung im Vertrieb", 2), ("3–5 Jahre Berufserfahrung", 3),
     ("über 5 Jahre Erfahrung", 5), ("drei Jahre Berufserfahrung in der Pflege", 3), ("three years of experience", 3),
     ("langjährige Erfahrung im Controlling", 5), ("mehrjährige Berufserfahrung", 5),
     ("10+ years overall and 3+ years as an architect", 10),
     ("You bring 4 yrs experience", 4),
     ("Since 1998 we have 25 years of experience in logistics. You bring 2 years of experience.", 2),   # company-history trap
     ("We are a company with 25 years of experience in logistics.", None),                            # company-history trap
     ("Candidates must be at least 18 years old", None),   # age guard (was a false positive in v1)
     ("ein bis zwei Jahre Berufserfahrung", 1),
    ]
    for t, want in Y: res.append(check(f"years '{t[:48]}'", years(t), want))
    print("--- seniority ---")
    S = [
     ("Senior AI Architect", "10+ years overall, 3+ years as AI architect", "senior"),
     ("AI Engineer (mid-level)", "10+ years of experience; 3+ years as an AI Architect", "senior"),   # Ericsson-style trap: title says mid, text says 10+
     ("Head of Engineering", "10+ years, lead a team, budget responsibility", "lead_exec"),
     ("Junior Analyst", "No experience required, graduate welcome", "entry"),
     ("Werkstudent Marketing (m/w/d)", "Student, Ausbildung oder Studium", "entry"),
     ("Senior Backend Engineer (m/w/d)", "We build great software.", "unknown"),         # current rule: title alone -> unknown
     ("Projektleiter Bau", "mind. 5 Jahre Berufserfahrung, Führungsverantwortung", "senior"),
    ]
    for ti, tx, want in S: res.append(check(f"seniority '{ti}'", seniority(ti, tx)[0], want))
    print("title-only with proposed hint:", seniority("Senior Backend Engineer (m/w/d)", "We build great software.", title_only_hint=True))
    print(f"\npassed {sum(res)}/{len(res)} (designer-written cases; BAD lines are findings, not bugs to hide)")

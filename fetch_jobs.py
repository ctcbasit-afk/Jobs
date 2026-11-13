import json, re, html, urllib.request, urllib.parse, datetime, os

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
QUERIES = ["Project Manager", "HR Manager", "Operations Manager", "Programme Manager", "Head of HR", "Admin Manager"]
KEEP = re.compile(r"project|programme|program manager|operations|\bhr\b|human resource|people (&|and) culture|admin|head of|director|coordinator|payroll|employee relations", re.I)
DROP = re.compile(r"intern\b|internship|trainee|driver|sales|marketing|developer|designer|fresh|receptionist|teacher|nurse", re.I)
TODAY = datetime.date.today().isoformat()

def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")

def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

def linkedin(q):
    out = []
    url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=%s&location=Pakistan&f_TPR=r604800&start=0"
           % urllib.parse.quote(q))
    for card in get(url).split("<li>")[1:]:
        u = re.search(r'href="(https://[^"]*linkedin\.com/jobs/view[^"]+)"', card)
        t = re.search(r'base-search-card__title">(.*?)</h3>', card, re.S)
        c = re.search(r'base-search-card__subtitle">(.*?)</h4>', card, re.S)
        l = re.search(r'job-search-card__location">(.*?)</span>', card, re.S)
        d = re.search(r'datetime="([\d-]+)"', card)
        if u and t:
            out.append(dict(title=clean(t.group(1)), company=clean(c.group(1)) if c else "", location=clean(l.group(1)) if l else "Pakistan",
                            url=html.unescape(u.group(1)).split("?")[0], source="LinkedIn", date=d.group(1) if d else TODAY))
    return out

def rozee(q):
    out = []
    page = get("https://www.rozee.pk/job/jsearch/q/" + urllib.parse.quote(q))
    for m in set(re.findall(r'href="((?:https://www\.rozee\.pk)?/[a-z0-9\-]+-jobs-\d+)"', page)):
        slug = m.rsplit("/", 1)[-1]
        slug = re.sub(r"-jobs-\d+$", "", slug)
        url = m if m.startswith("http") else "https://www.rozee.pk" + m
        out.append(dict(title=slug.replace("-", " ").title(), company="", location="Pakistan", url=url, source="Rozee", date=TODAY))
    return out

def unjobs():
    out = []
    page = get("https://unjobs.org/duty_stations/pak")
    for href, text in re.findall(r'<a[^>]*href="(/vacancies/[^"]+)"[^>]*>(.*?)</a>', page, re.S):
        t = clean(text)
        if t:
            out.append(dict(title=t, company="UN system", location="Pakistan", url="https://unjobs.org" + href, source="UNjobs", date=TODAY))
    return out

def score(j):
    s = 0
    t = j["title"].lower()
    blob = (j["title"] + " " + j["company"]).lower()
    if re.search(r"manager|head|director|lead|specialist", t): s += 40
    if re.search(r"project|programme|program|operations|\bhr\b|human resource|people", t): s += 25
    if re.search(r"energy|petrol|oil|gas|refin|pso|shell|wafi|parco|ogdcl|ppl|attock|fuel", blob): s += 15
    if re.search(r"\bun\b|who|unicef|unops|undp|united nations", blob): s += 15
    if re.search(r"assistant|officer|executive|associate|junior", t): s -= 30
    return max(0, min(100, s))

def main():
    try:
        old = json.load(open("jobs.json", encoding="utf-8"))
    except Exception:
        old = {"jobs": []}
    known = {j["url"]: j for j in old.get("jobs", [])}
    status = {}
    fresh = []
    tasks = [("LinkedIn:" + q, lambda q=q: linkedin(q)) for q in QUERIES] + \
            [("Rozee:" + q, lambda q=q: rozee(q)) for q in QUERIES[:3]] + [("UNjobs", unjobs)]
    for name, fn in tasks:
        try:
            r = fn()
            status[name] = len(r)
            fresh += r
        except Exception as e:
            status[name] = "error: " + str(e)[:60]
    for j in fresh:
        if not KEEP.search(j["title"]) or DROP.search(j["title"]):
            continue
        if j["url"] in known:
            continue
        j["first_seen"] = TODAY
        j["score"] = score(j)
        j["fit"] = "Best fit" if j["score"] >= 70 else "Good fit" if j["score"] >= 50 else "Check"
        known[j["url"]] = j
    cutoff = (datetime.date.today() - datetime.timedelta(days=21)).isoformat()
    jobs = [j for j in known.values() if j.get("first_seen", TODAY) >= cutoff]
    jobs.sort(key=lambda j: (j.get("score", 0), j.get("date", "")), reverse=True)
    out = {"updated": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z", "status": status, "jobs": jobs}
    json.dump(out, open("jobs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(status, indent=1), len(jobs), "jobs saved")

main()

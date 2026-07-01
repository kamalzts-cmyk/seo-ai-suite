from flask import Flask, render_template, request, send_file
import requests, csv, io, os, json
from datetime import datetime
from urllib.parse import urlparse

app = Flask(__name__)
APP_NAME = "SEO AI Suite"
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_API_URL = "https://google.serper.dev/search"

def normalize_domain(domain):
    return domain.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")

def clean_host(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""

def fetch_serper(keyword, location="India", gl="in", hl="en", num=100):
    if not SERPER_API_KEY:
        return {"error": "Missing SERPER_API_KEY in Render environment variables."}
    payload = {"q": keyword, "num": num, "gl": gl or "in", "hl": hl or "en", "location": location or "India"}
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(SERPER_API_URL, headers=headers, json=payload, timeout=45)
        r.raise_for_status()
        data = r.json()
        return {
            "organic": data.get("organic", []),
            "people_also_ask": data.get("peopleAlsoAsk", []),
            "answer_box": data.get("answerBox"),
            "knowledge_graph": data.get("knowledgeGraph")
        }
    except Exception as e:
        return {"error": str(e)}

def check_rank(keyword, target_domain, location, gl, hl):
    target = normalize_domain(target_domain)
    serp = fetch_serper(keyword, location, gl, hl)
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    if serp.get("error"):
        return {"keyword": keyword, "rank": "Error", "found_url": serp["error"], "serp_features": "-", "checked_at": checked_at}
    features = []
    if serp.get("answer_box"): features.append("Answer Box")
    if serp.get("knowledge_graph"): features.append("Knowledge Graph")
    if serp.get("people_also_ask"): features.append("People Also Ask")
    feature_text = ", ".join(features) if features else "Standard Organic SERP"
    for item in serp.get("organic", []):
        url = item.get("link", "")
        if target in clean_host(url) or target in url.lower():
            return {"keyword": keyword, "rank": item.get("position") or ">100", "found_url": url, "serp_features": feature_text, "checked_at": checked_at}
    return {"keyword": keyword, "rank": ">100", "found_url": "Not found in top 100 organic results", "serp_features": feature_text, "checked_at": checked_at}

def quick_audit(url):
    try:
        if not url.startswith("http"): url = "https://" + url
        r = requests.get(url, timeout=15, headers={"User-Agent": "SEOAI-Suite/1.0"})
        html = r.text.lower()
        checks = []
        checks.append({"check": "Status Code", "result": str(r.status_code), "status": "Pass" if r.status_code == 200 else "Review"})
        checks.append({"check": "Title Tag", "result": "Found" if "<title" in html else "Missing", "status": "Pass" if "<title" in html else "Fail"})
        checks.append({"check": "Meta Description", "result": "Found" if 'name="description"' in html or "name='description'" in html else "Missing", "status": "Pass" if 'name="description"' in html or "name='description'" in html else "Fail"})
        checks.append({"check": "H1 Tag", "result": "Found" if "<h1" in html else "Missing", "status": "Pass" if "<h1" in html else "Review"})
        checks.append({"check": "Canonical", "result": "Found" if 'rel="canonical"' in html or "rel='canonical'" in html else "Missing", "status": "Pass" if 'rel="canonical"' in html or "rel='canonical'" in html else "Review"})
        checks.append({"check": "Schema", "result": "Found" if "application/ld+json" in html else "Missing", "status": "Pass" if "application/ld+json" in html else "Review"})
        return checks
    except Exception as e:
        return [{"check": "Fetch Error", "result": str(e), "status": "Fail"}]

@app.route("/")
def dashboard():
    modules = [
        ("Rank Tracker", "/rank-tracker", "Live", "Check Google rankings by domain, country and location."),
        ("Technical SEO Audit", "/technical-audit", "Live", "Check title, meta description, H1, canonical and schema."),
        ("AI SERP Checker", "/ai-serp", "Live", "Detect answer box, knowledge graph, PAA and top competitors."),
        ("Keyword Clustering", "/keyword-clustering", "Beta", "Group keywords by commercial and informational intent."),
        ("Content Briefs", "/content-brief", "Beta", "Generate strategic SEO content briefs."),
        ("Competitor Analyzer", "/competitor-analyzer", "Beta", "Map competitor risks and action points."),
        ("Client Reports", "/reports", "Beta", "Reporting hub for client-ready summaries.")
    ]
    return render_template("dashboard.html", app_name=APP_NAME, modules=modules, api_ready=bool(SERPER_API_KEY))

@app.route("/rank-tracker", methods=["GET","POST"])
def rank_tracker():
    results=[]; domain=""; location="India"; gl="in"; hl="en"; keywords_text=""
    if request.method=="POST":
        domain=request.form.get("domain","").strip()
        location=request.form.get("location","India").strip()
        gl=request.form.get("gl","in").strip()
        hl=request.form.get("hl","en").strip()
        keywords_text=request.form.get("keywords","").strip()
        for kw in [k.strip() for k in keywords_text.splitlines() if k.strip()]:
            results.append(check_rank(kw,domain,location,gl,hl))
    return render_template("rank_tracker.html", app_name=APP_NAME, results=results, domain=domain, location=location, gl=gl, hl=hl, keywords_text=keywords_text, api_ready=bool(SERPER_API_KEY))

@app.route("/export-ranks", methods=["POST"])
def export_ranks():
    rows=json.loads(request.form.get("results_json","[]"))
    out=io.StringIO()
    writer=csv.DictWriter(out, fieldnames=["keyword","rank","found_url","serp_features","checked_at"])
    writer.writeheader(); writer.writerows(rows)
    mem=io.BytesIO(out.getvalue().encode("utf-8")); mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="seo-ai-rank-report.csv")

@app.route("/technical-audit", methods=["GET","POST"])
def technical_audit():
    url=""; checks=[]
    if request.method=="POST":
        url=request.form.get("url","").strip()
        if url: checks=quick_audit(url)
    return render_template("technical_audit.html", app_name=APP_NAME, url=url, checks=checks)

@app.route("/ai-serp", methods=["GET","POST"])
def ai_serp():
    keyword=""; location="India"; gl="in"; hl="en"; data=None
    if request.method=="POST":
        keyword=request.form.get("keyword","").strip()
        location=request.form.get("location","India").strip()
        gl=request.form.get("gl","in").strip()
        hl=request.form.get("hl","en").strip()
        if keyword: data=fetch_serper(keyword, location, gl, hl, 20)
    return render_template("ai_serp.html", app_name=APP_NAME, keyword=keyword, location=location, gl=gl, hl=hl, data=data)

@app.route("/keyword-clustering", methods=["GET","POST"])
def keyword_clustering():
    clusters={}; keywords_text=""
    if request.method=="POST":
        keywords_text=request.form.get("keywords","").strip()
        for kw in [k.strip() for k in keywords_text.splitlines() if k.strip()]:
            low=kw.lower()
            if any(x in low for x in ["buy","price","cost","near me","for sale"]): bucket="Commercial Intent"
            elif any(x in low for x in ["how","what","why","guide","tips"]): bucket="Informational Intent"
            elif any(x in low for x in ["best","top","compare","vs"]): bucket="Comparison Intent"
            else: bucket="General / Topical"
            clusters.setdefault(bucket,[]).append(kw)
    return render_template("keyword_clustering.html", app_name=APP_NAME, keywords_text=keywords_text, clusters=clusters)

@app.route("/content-brief", methods=["GET","POST"])
def content_brief():
    topic=""; audience=""; brief=None
    if request.method=="POST":
        topic=request.form.get("topic","").strip()
        audience=request.form.get("audience","").strip()
        if topic:
            brief={
                "title": f"{topic}: Strategic SEO Content Brief",
                "audience": audience or "CEOs, founders, COOs, CMOs and revenue leaders",
                "sections": ["Executive hook","Market opportunity","Buyer pain points","Solution positioning","Competitor comparison","ROI and risk","FAQs","CTA"],
                "entities": [topic,"ROI","organic growth","search visibility","lead generation","authority"],
                "links": ["Main service page","Relevant case study","Supporting blog cluster","Contact page"]
            }
    return render_template("content_brief.html", app_name=APP_NAME, topic=topic, audience=audience, brief=brief)

@app.route("/competitor-analyzer", methods=["GET","POST"])
def competitor_analyzer():
    domain=""; competitors_text=""; rows=[]
    if request.method=="POST":
        domain=request.form.get("domain","").strip()
        competitors_text=request.form.get("competitors","").strip()
        for c in [x.strip() for x in competitors_text.splitlines() if x.strip()]:
            rows.append({"competitor": c, "risk": "High", "action": "Review SERP coverage, backlink strength, content depth, service page quality and local/entity signals."})
    return render_template("competitor_analyzer.html", app_name=APP_NAME, domain=domain, competitors_text=competitors_text, rows=rows)

@app.route("/reports")
def reports():
    return render_template("reports.html", app_name=APP_NAME)

if __name__ == "__main__":
    app.run(debug=True)

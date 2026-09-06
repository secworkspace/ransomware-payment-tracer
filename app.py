from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import json

from fetch_transactions import trace_chain
from detect_risk import analyze_trace, load_blacklist

app = FastAPI()

@app.get("/api/trace")
def get_trace(address: str = Query(default="bc1qq2euq8pw950klpjcawuy4uj39ym43hs6cfsegq")):
    """
    Runs a LIVE trace for whatever address is passed in.
    Defaults to the Colonial Pipeline seed address if none is given.
    """
    chain = trace_chain(address)
    blacklist = load_blacklist()
    results = analyze_trace(chain, blacklist)
    return results

@app.get("/")
def serve_dashboard():
    with open("dashboard.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
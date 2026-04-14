import os
import json
import logging
import requests
import boto3
import uuid

from datetime import datetime, timezone
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REGION        = "ap-south-1"
COUNTER_TABLE = os.getenv("COUNTER_TABLE", "resume_counter")
GEO_TABLE     = os.getenv("GEO_TABLE",     "resume_geo_logs")

dynamodb      = boto3.resource("dynamodb", region_name=REGION)
counter_table = dynamodb.Table(COUNTER_TABLE)
geo_table     = dynamodb.Table(GEO_TABLE)

CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type":                 "application/json",
}

def respond(status, body):
    return {"statusCode": status, "headers": CORS, "body": json.dumps(body)}

def get_ip(event):
    headers = event.get("headers") or {}
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    try:
        return event["requestContext"]["http"]["sourceIp"]
    except Exception:
        pass
    try:
        return event["requestContext"]["identity"]["sourceIp"]
    except Exception:
        pass
    return "0.0.0.0"

def geolocate(ip):
    private = ("127.", "10.", "192.168.", "172.", "::1")
    if any(ip.startswith(p) for p in private):
        return {"country":"Local","country_code":"LO","region":"Local","city":"Local","latitude":0.0,"longitude":0.0,"isp":"Local"}
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", params={"fields":"status,country,countryCode,regionName,city,lat,lon,isp"}, timeout=3)
        d = r.json()
        if d.get("status") == "success":
            return {"country":d.get("country","Unknown"),"country_code":d.get("countryCode","XX"),"region":d.get("regionName","Unknown"),"city":d.get("city","Unknown"),"latitude":d.get("lat",0.0),"longitude":d.get("lon",0.0),"isp":d.get("isp","Unknown")}
    except Exception as e:
        logger.warning(f"Geo failed for {ip}: {e}")
    return {"country":"Unknown","country_code":"XX","region":"Unknown","city":"Unknown","latitude":0.0,"longitude":0.0,"isp":"Unknown"}

def post_visitors(event):
    try:
        ip  = get_ip(event)
        geo = geolocate(ip)
        ua  = (event.get("headers") or {}).get("user-agent", "Unknown")
        resp = counter_table.update_item(Key={"id":"visits"},UpdateExpression="SET #c = #c + :inc",ExpressionAttributeNames={"#c":"count"},ExpressionAttributeValues={":inc":1},ReturnValues="UPDATED_NEW")
        new_count = int(resp["Attributes"]["count"])
        geo_table.put_item(Item={"visit_id":str(uuid.uuid4()),"visited_at":datetime.now(timezone.utc).isoformat(),"ip_address":ip,"country":geo["country"],"country_code":geo["country_code"],"region":geo["region"],"city":geo["city"],"latitude":Decimal(str(geo["latitude"])),"longitude":Decimal(str(geo["longitude"])),"isp":geo["isp"],"user_agent":ua})
        logger.info(f"Count -> {new_count}")
        return respond(200, {"count": new_count, "status": "ok"})
    except Exception as e:
        logger.error(f"post_visitors error: {e}")
        return respond(500, {"error": str(e), "status": "error"})

def get_visitors():
    try:
        r = counter_table.get_item(Key={"id": "visits"})
        return respond(200, {"count": int(r["Item"]["count"]), "status": "ok"})
    except Exception as e:
        return respond(500, {"error": str(e), "status": "error"})

def get_logs():
    try:
        r = geo_table.scan(Limit=50)
        items = sorted(r.get("Items",[]), key=lambda x: x.get("visited_at",""), reverse=True)
        logs = [{"ip":i.get("ip_address",""),"country":i.get("country",""),"country_code":i.get("country_code",""),"region":i.get("region",""),"city":i.get("city",""),"latitude":float(i.get("latitude",0)),"longitude":float(i.get("longitude",0)),"isp":i.get("isp",""),"user_agent":i.get("user_agent",""),"visited_at":i.get("visited_at","")} for i in items]
        return respond(200, {"logs": logs, "total": len(logs), "status": "ok"})
    except Exception as e:
        return respond(500, {"error": str(e), "status": "error"})

def get_health():
    ts = datetime.now(timezone.utc).isoformat()
    try:
        counter_table.get_item(Key={"id": "visits"})
        return respond(200, {"status": "healthy", "db": "connected", "timestamp": ts})
    except Exception as e:
        return respond(500, {"status": "unhealthy", "db": "unreachable", "timestamp": ts})

def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    method = (event.get("httpMethod") or event.get("requestContext",{}).get("http",{}).get("method","")).upper()
    path   = event.get("rawPath") or event.get("path", "")
    logger.info(f"{method} {path}")
    if method == "OPTIONS":
        return respond(200, {})
    if method == "POST" and path == "/api/visitors":
        return post_visitors(event)
    if method == "GET" and path == "/api/visitors":
        return get_visitors()
    if method == "GET" and path == "/api/logs":
        return get_logs()
    if method == "GET" and path == "/api/health":
        return get_health()
    return respond(404, {"error": "Not found", "status": "error"})

#!/usr/bin/env python3
"""
Migrate from PostgreSQL to DynamoDB.
Schema source:
  - visitors        (id, count, created_at, updated_at)
  - visit_logs      (id, ip_address, country, country_code, region,
                     city, latitude, longitude, isp, user_agent, visited_at)

Run this ON the EC2 instance.
  pip install psycopg2-binary boto3
"""

import psycopg2
import boto3
import uuid
from datetime import timezone
from decimal import Decimal

# ── CONFIG — only edit this block ────────────────────────────────────────────
PG_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "portfolio",          
    "user":     "your_db_user",       
    "password": "your_db_password",   
}

DYNAMO_REGION = "ap-south-1"         
COUNTER_TABLE = "resume_counter"
GEO_TABLE     = "resume_geo_logs"
# ─────────────────────────────────────────────────────────────────────────────


def get_pg():
    print("Connecting to PostgreSQL...")
    return psycopg2.connect(**PG_CONFIG)


def get_dynamo():
    return boto3.resource("dynamodb", region_name=DYNAMO_REGION)


def migrate_counter(pg, dynamo):
    """
    visitors table has a single row (id=1) with a running count bigint.
    We read that value directly — no need to COUNT(*).
    """
    print("\n── Migrating visitors counter ──")
    cur = pg.cursor()
    cur.execute("SELECT count FROM visitors ORDER BY id LIMIT 1")
    row = cur.fetchone()

    if not row:
        print("  No rows in visitors table — writing count=0")
        count = 0
    else:
        count = int(row[0])

    dynamo.Table(COUNTER_TABLE).put_item(Item={
        "id":    "visits",
        "count": count,
    })
    print(f"  Written → resume_counter: count={count}")
    cur.close()


def migrate_geo_logs(pg, dynamo):
    """
    visit_logs maps directly to resume_geo_logs.
    Postgres integer id is dropped; a UUID becomes the new partition key.
    All nullable text fields default to 'unknown' if NULL.
    latitude/longitude (double precision) are cast to Decimal for DynamoDB.
    """
    print("\n── Migrating visit_logs ──")
    cur = pg.cursor()
    cur.execute("""
        SELECT
            ip_address,
            country,
            country_code,
            region,
            city,
            latitude,
            longitude,
            isp,
            user_agent,
            visited_at
        FROM visit_logs
        ORDER BY visited_at ASC
    """)

    rows = cur.fetchall()
    print(f"  Rows to migrate: {len(rows)}")

    table = dynamo.Table(GEO_TABLE)
    written = 0
    skipped = 0

    with table.batch_writer() as batch:
        for row in rows:
            (ip_address, country, country_code, region, city,
             latitude, longitude, isp, user_agent, visited_at) = row

            # visited_at is NOT NULL in your schema so this is always set
            ts = visited_at.astimezone(timezone.utc).isoformat()

            item = {
                "visit_id":     str(uuid.uuid4()),
                "visited_at":   ts,
                "ip_address":   str(ip_address   or "unknown"),
                "country":      str(country      or "unknown"),
                "country_code": str(country_code or "unknown"),
                "region":       str(region       or "unknown"),
                "city":         str(city         or "unknown"),
                "isp":          str(isp          or "unknown"),
                "user_agent":   str(user_agent   or "unknown"),
            }

            # latitude/longitude are nullable doubles — skip if both missing
            if latitude is not None and longitude is not None:
                item["latitude"]  = Decimal(str(latitude))
                item["longitude"] = Decimal(str(longitude))
            else:
                skipped += 1
                # still write the row, just without geo coords
                item["latitude"]  = Decimal("0")
                item["longitude"] = Decimal("0")

            batch.put_item(Item=item)
            written += 1

            if written % 200 == 0:
                print(f"  ...{written} rows written")

    print(f"  Done. {written} rows written ({skipped} had no lat/lon, stored as 0,0)")
    cur.close()


def verify(dynamo):
    print("\n── Verification ──")

    resp = dynamo.Table(COUNTER_TABLE).get_item(Key={"id": "visits"})
    print(f"  resume_counter    → count = {resp['Item']['count']}")

    resp = dynamo.Table(GEO_TABLE).scan(Select="COUNT")
    print(f"  resume_geo_logs   → items = {resp['Count']}")
    # Note: scan Count is eventually consistent; for large tables it may
    # show slightly less than final — run again after 10s to confirm.


def main():
    pg     = get_pg()
    dynamo = get_dynamo()
    try:
        migrate_counter(pg, dynamo)
        migrate_geo_logs(pg, dynamo)
        verify(dynamo)
        print("\n✓ Migration complete. Safe to proceed to Day 3.")
    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        raise
    finally:
        pg.close()


if __name__ == "__main__":
    main()
import os
import json
import boto3
import requests
from flask import Flask, render_template

app = Flask(__name__)


def load_secrets():
    """Load secrets from AWS Secrets Manager into os.environ."""
    try:
        client = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        secret_name = os.environ.get("SECRET_NAME", "prod/horizon/env")
        response = client.get_secret_value(SecretId=secret_name)
        for key, value in json.loads(response["SecretString"]).items():
            os.environ[key] = str(value)
        print("✅ Secrets loaded from AWS Secrets Manager")
    except Exception as e:
        print(f"⚠️  ASM unavailable ({e}) — using local env vars")


# Load secrets before anything reads env
load_secrets()

# Defensive: ensure https:// prefix
raw_cf_url = os.environ.get("CLOUDFRONT_URL", "").rstrip("/")
if raw_cf_url and not raw_cf_url.startswith("http"):
    raw_cf_url = f"https://{raw_cf_url}"
CLOUDFRONT_URL = raw_cf_url


def cf(path):
    """Return a full CloudFront URL for a given object path."""
    if not path or not CLOUDFRONT_URL:
        return None
    return f"{CLOUDFRONT_URL}/{path.lstrip('/')}"


def fetch_content():
    """Fetch page_content.json via CloudFront. Falls back to defaults."""
    if CLOUDFRONT_URL:
        try:
            resp = requests.get(cf("page_content.json"), timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"⚠️  CloudFront fetch failed ({e}) — using fallback content")

    return {
        "title": "Horizon",
        "tagline": "Places. Moments. Motion.",
        "sections": [
            {
                "heading": "Mountain",
                "body": "Above the treeline, where the air thins and the world opens up.",
                "image": "mountain.jpeg",
                "video": None,
            },
            {
                "heading": "Ocean",
                "body": "The rhythm of the waves never stops.",
                "image": None,
                "video": "ocean.mp4",
            },
            {
                "heading": "On the Road",
                "body": "Windows down, no fixed destination.",
                "image": None,
                "video": "car.mp4",
            },
        ],
    }


@app.route("/")
def index():
    content = fetch_content()
    for s in content["sections"]:
        s["image_url"] = cf(s.get("image"))
        s["video_url"] = cf(s.get("video"))
    return render_template("index.html", content=content, cloudfront_url=CLOUDFRONT_URL)


@app.route("/health")
def health():
    return {"status": "healthy", "cloudfront_configured": bool(CLOUDFRONT_URL)}, 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
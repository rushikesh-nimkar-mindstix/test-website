import os
import json
import boto3
import requests
from flask import Flask, render_template

app = Flask(__name__)


def load_secrets():
    """
    Load secrets from AWS Secrets Manager into environment variables.
    Call this BEFORE anything else.
    """
    try:
        # Use IAM role attached to EC2 (no access keys needed)
        client = boto3.client(
            'secretsmanager',
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        secret_name = os.environ.get('SECRET_NAME', 'prod/myapp/env')
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response['SecretString'])
        
        # Store all secrets in os.environ for easy access
        for key, value in secrets.items():
            os.environ[key] = str(value)
            
        print("✅ Secrets loaded from ASM")
        return True
        
    except Exception as e:
        print(f"⚠️ Could not load secrets from ASM: {e}")
        print("⚠️ Falling back to local environment variables")
        return False


# Load secrets FIRST when module imports
load_secrets()


# Now read CloudFront URL from environment (set by ASM or fallback)
CLOUDFRONT_URL = os.environ.get("CLOUDFRONT_URL", "").rstrip("/")


def cf(path):
    """Build a full CloudFront URL for any file path."""
    if not path:
        return None
    return f"{CLOUDFRONT_URL}/{path.lstrip('/')}"


def fetch_content():
    """
    Fetch page_content.json from CloudFront.
    Falls back to hardcoded content if CloudFront is not reachable.
    """
    if CLOUDFRONT_URL:
        try:
            resp = requests.get(cf("page_content.json"), timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"⚠️ Could not fetch from CloudFront: {e}")
            print("⚠️ Using fallback content")

    # Fallback / local dev content
    return {
        "title": "My Media Page",
        "intro": "A simple page with images, text, and videos — all served from CloudFront.",
        "sections": [
            {
                "heading": "Mountains",
                "body": "Crisp air, endless views, and the quiet you can only find above the treeline.",
                "image": "images/mountains.jpg",
                "video": None,
            },
            {
                "heading": "Ocean",
                "body": "Salt water, rhythm of the waves, and a horizon that goes on forever.",
                "image": "images/ocean.jpg",
                "video": "videos/ocean.mp4",
            },
            {
                "heading": "City at Night",
                "body": "Neon reflections, endless movement, and a million stories per block.",
                "image": None,
                "video": "videos/city.mp4",
            },
        ],
    }


@app.route("/")
def index():
    content = fetch_content()

    # Resolve all paths to full CloudFront URLs
    for section in content["sections"]:
        section["image_url"] = cf(section.get("image")) if section.get("image") else None
        section["video_url"] = cf(section.get("video")) if section.get("video") else None

    return render_template(
        "index.html",
        content=content,
        cloudfront_url=CLOUDFRONT_URL
    )


@app.route("/health")
def health():
    """Health check endpoint for ALB."""
    return {"status": "healthy", "cloudfront_configured": bool(CLOUDFRONT_URL)}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
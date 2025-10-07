import os
import requests
import boto3
from datetime import datetime

# === Global Config (via environment variables) ===
# Note: Do NOT hardcode credentials or personal data here. Configure via environment.
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "")  # required in production

ZYTE_API_KEY = os.getenv("ZYTE_API_KEY", "")
CALLBACK_API_JOB = os.getenv(
    "CALLBACK_API_JOB",
    ""
)
CALLBACK_API_APPLICATION = os.getenv(
    "CALLBACK_API_APPLICATION",
    ""
)

s3 = boto3.client("s3", region_name=AWS_REGION)

## check job live status and update DB directly
def checkJobStatus(apply_now_url, jobID, appID):
    try:
        response = requests.get(apply_now_url)
        if response.ok:
            browserhtml = response.text
        else:
            return False
        
        is_redirect = is_dead_status = False
        if ("Job is Archived" in browserhtml) or ("This job has now closed" in browserhtml):
            is_dead_status = True
            is_redirect = True

        if is_redirect or is_dead_status:
            response = updateApplicationStatus(appID, 2, "", "Application failed because the job is closed")
            if CALLBACK_API_JOB:
                update_response = requests.post(
                    CALLBACK_API_JOB.format(job_id=jobID),
                    json={"job_post_status": 1}
                )
            else:
                update_response = None

            if update_response.status_code == 200:
                print(f"[Update] Job {jobID} marked as closed.")
            else:
                print(f"[Update Error] Status code: {update_response.status_code}")
            
            return False

        print("Job is still live")
        return True

    except requests.RequestException as e:
        print(f"[Exception] Error during job check: {e}")
        return True


## update application status 
def updateApplicationStatus(appID = 0, status = 0, screenshotURL = "", message = ""):
    if (appID < 0):
        return None
    payload = {
        "status": str(status),
        "status_message": message,
        "applied_screenshot_url": screenshotURL,
    }
    if not CALLBACK_API_APPLICATION:
        print("[Warn] CALLBACK_API_APPLICATION is not configured; skipping status update call.")
        return None
    try:
        response = requests.put(CALLBACK_API_APPLICATION.format(appID=appID), json=payload)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        return response
    except requests.RequestException as e:
        print(f"Error updating application {appID}: {e}")
        return None
    
     ## generate s3 screenshot url
     
def generate_object_name(appID, atsName: str, extension="jpeg") -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    clean_site = atsName.replace(" ", "-").lower()
    return f"{appID}-{clean_site}-{timestamp}.{extension}"

def upload_file_to_s3(file_path: str, object_name: str, make_public: bool = True) -> str:
    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET is not configured. Set the environment variable before running.")
    print(f"Uploading `{object_name}` to S3 bucket `{S3_BUCKET}`...")

    extra_args = {"ContentType": 'image/png'} if make_public else {}

    with open(file_path, "rb") as f:
        s3.upload_fileobj(f, S3_BUCKET, object_name, ExtraArgs=extra_args)

    s3_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{object_name}"
    print("Upload complete.")
    return s3_url


def get_zyte_auth_credentials():
    """Return a tuple suitable for HTTP Basic auth with Zyte API.

    Zyte expects the API key as the username and an empty password.
    """
    return (ZYTE_API_KEY or "", "")
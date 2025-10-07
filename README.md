## GoHire Auto-Apply (AWS Lambda / GitHub Deployment)

This repository contains an AWS Lambda function that automates job applications on GoHire.

### Features

- Fetches GoHire widget, fills fields, uploads resume, and submits.
- Captures a full-page screenshot via Zyte and uploads to S3.
- Reports application status to a callback API.

### Security and configuration

Do not hardcode secrets. Configure all credentials and endpoints via environment variables.

Required environment variables:

- `AWS_REGION` (e.g. `us-east-1`)
- `S3_BUCKET` (destination bucket for screenshots)
- `ZYTE_API_KEY` (Zyte Extract API key)
- `CALLBACK_API_JOB` (e.g. `https://<host>/api/v1/copilot/job/{job_id}`)
- `CALLBACK_API_APPLICATION` (e.g. `https://<host>/api/v1/copilot/application/{appID}`)

### Local development

1. Create and activate a virtualenv.
2. `pip install -r requirements.txt`
3. Export env vars above (Windows PowerShell):
   ```powershell
   $env:AWS_REGION = "us-east-1"
   $env:S3_BUCKET = "your-bucket"
   $env:ZYTE_API_KEY = "<redacted>"
   $env:CALLBACK_API_JOB = "https://example.com/api/v1/copilot/job/{job_id}"
   $env:CALLBACK_API_APPLICATION = "https://example.com/api/v1/copilot/application/{appID}"
   ```
4. Create an event JSON and invoke `lambda_handler` from `lambda_function.py`.

### AWS Lambda deployment

- Package code with dependencies or use a Lambda layer for native packages.
- Configure the environment variables in the Lambda console or IaC tool.
- Grant the Lambda role `s3:PutObject` permissions for `S3_BUCKET`.

### GitHub deployment

You can deploy using GitHub Actions. A minimal workflow might:

- Set environment secrets (same names as above) in the repo settings.
- Build a zip artifact with `lambda_function.py`, `oh_utils.py`, and dependencies.
- Update the Lambda function via AWS CLI or serverless framework.

This repository does not include a workflow file by default. Add one tailored to your AWS account and deployment approach.

### Event contract

`lambda_handler(event, context)` expects:

```json
{
  "application": 123,
  "mongoID": "abc123",
  "source": { "apply_now_url": "https://jobs..." },
  "ats_name": "GoHire",
  "seeker": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "mobile_code": "+1",
    "mobile_num": "5551234567",
    "address": "",
    "country": "",
    "state": "",
    "city": "",
    "zip": "",
    "available_date": "",
    "desired_pay": "",
    "resume": "https://.../resume.pdf",
    "seeker_response": []
  }
}
```

### Notes

- Comments and code avoid embedding any personal data or secrets.
- If `CALLBACK_API_*` values are not set, callbacks are skipped gracefully.

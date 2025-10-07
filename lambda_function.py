import os
import json
import requests
from lxml import html
from base64 import b64decode
from parsel import Selector
from oh_utils import (
    checkJobStatus,
    upload_file_to_s3,
    updateApplicationStatus,
    generate_object_name,
    get_zyte_auth_credentials,
)

def element_exists_xpath(html_content, xpath):
    tree = html.fromstring(html_content)
    elements = tree.xpath(xpath)
    return len(elements) > 0

def lambda_handler(event, context=""):
    applicationID  = event.get('application', 0)
    mongoID = event.get('mongoID',0)         
    source = event.get("source")
    job_url = source.get('apply_now_url')
    jobStatus = checkJobStatus(job_url, mongoID, applicationID)
    if not jobStatus:
        return {
            "statusCode": 400,
            # "Response":response;
            "message": "Application URL is dead or expired."
        }

    seeker = event.get('seeker')
    first_name = seeker.get('first_name')
    last_name = seeker.get('last_name')
    fullName = f"{first_name} {last_name}"
    email_input = seeker.get('email')
    
    mobile_code = seeker.get('mobile_code')
    mobile_num = seeker.get('mobile_num')
    address = seeker.get("address")
    country = seeker.get("country")
    state = seeker.get("state")
    city = seeker.get("city")
    zipcode = seeker.get("zip")
    
    dateAvailable = seeker.get("available_date")
    desired_pay = seeker.get("desired_pay")
    
    pdf_url = seeker.get('resume')
    
    seeker_response = seeker.get('seeker_response', [])
    dataResponse = seeker_response
    
    mobile_num = f"{mobile_code}{mobile_num}"
    atsName = event.get('ats_name')
    resume_type = "pdf"
    if (".docx" in pdf_url):
        resume_type = 'docx'
    
    actions = [
        {
            "action": "evaluate",
            "source": """
                const descriptor = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype,
                "value"
            );
            var input = document.querySelector("input[name='f_name']");
            descriptor.set.call(input, "%s");
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
            """%first_name,
            "onError": "continue"
        },
        {
            "action": "evaluate",
            "source": """
                input = document.querySelector("input[name='l_name']");
                descriptor.set.call(input, "%s");
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            """%last_name,
            "onError": "continue"    
        },
        {
            "action": "evaluate",
            "source": """
                input = document.querySelector("input[name='email']");
                descriptor.set.call(input, "%s");
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            """%email_input,
            "onError": "continue"
        },
        {
            "action": "evaluate",
            "source": """
                input = document.querySelector("input[name='phone']");
                descriptor.set.call(input, "%s");
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
            """%mobile_num,
            "onError": "continue"
        },
        {
            "action": "evaluate",
            "source": """
                var pdf_url = '%s'; var fileInput = document.querySelector('input[id=attach]'); fetch(pdf_url).then(response => response.blob()).then(pdfBlob => { var pdfFile = new File([pdfBlob], "My_Resume.pdf", { type: "application/%s" }); var fileList = new DataTransfer(); fileList.items.add(pdfFile); fileInput.files = fileList.files; fileInput.dispatchEvent(new Event("change", { bubbles: true })); }).catch(error => console.error('Error fetching or processing PDF:', error));
            """%(pdf_url, resume_type),
            "onError": "continue"
        },
        {
            "action": "waitForTimeout",
            "timeout": 5,
            "onError": "continue"
        },
        {
            "action": "evaluate",
            "source": """
                document.querySelector('div.primary-btn.gh-widget-btn').click();
            """,
            "onError": "continue"
        },
        {
            "action": "waitForTimeout",
            "timeout": 3,
            "onError": "continue"
        }
    ]

    response = requests.get(job_url)
    selector = Selector(response.text)
    link = selector.xpath("//script[contains(@src, 'https://widget.gohire.io/widget')]/@src").get()
    code = link.split("/")[-1]
    job_id = job_url.split("-")[-1]
    job_url = f"https://app.gohire.io/widget/{code}/{job_id}"
    print("Job URL : ", job_url)
        
    print("-----------Start Applying to the Job-------------")
    api_response = requests.post(
        "https://api.zyte.com/v1/extract",
        auth=get_zyte_auth_credentials(),
        json={
            "url": job_url,
            "browserHtml": True,
            "screenshot": True,
            "screenshotOptions": {
                "fullPage": True
            },
            "actions": actions,
        }
    )

    try:
        try:
            browser_html = api_response.json()["browserHtml"]
        except Exception:
            # Log non-sensitive response body for debugging
            print(api_response.json())

        print("Status Code : ", api_response.status_code)
        if not api_response.status_code == 200:
            print(api_response.text)
            return
        
        actions_res = api_response.json()["actions"]
        print("actions : ", actions_res)
        
        screenshot: bytes = b64decode(api_response.json()["screenshot"])
        filename = generate_object_name(applicationID, atsName)
        s3_key = f"{atsName}/{filename}"
        local_file_path = f"/tmp/{filename}"
        with open(local_file_path, "wb") as file:
            file.write(screenshot)
        s3_url = upload_file_to_s3(local_file_path, s3_key)
        print(s3_url)

        if (element_exists_xpath(browser_html, "//*[contains(text(),'Application Sent!')]")):
            print("------------Job Application Successfull------------")
            res = updateApplicationStatus(applicationID, 1, s3_url, "Success Application")
            print(res, "call back API response")
            return {
                "statusCode": 200,
                # "Response":response;
                "message":"Application Completed."
            }
        elif element_exists_xpath(browser_html, "//*[contains(text(), 'already applied')]"):
            print("Already Applied.")
            res = updateApplicationStatus(applicationID, 1, s3_url, "Success Application")
            return {
                "statusCode": 200,
                # "Response":response;
                "message":"Application Completed."
            }
        else:
            updateApplicationStatus(applicationID, 2, s3_url, "Failed Application")
            
    except Exception as e:
        print("Exception : ", str(e))
        updateApplicationStatus(applicationID, 0, "", str(e))
        
    print("Failed to apply")
    return {
        "statusCode": 200,
        # "Response":response;
        "message":"Application Failed."
    }
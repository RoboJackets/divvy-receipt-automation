"""
Augment Divvy's native receipt automation
"""
from base64 import b64encode
from json import JSONDecodeError, loads
from os import environ
from re import search
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from requests import get, post

HTML_PARSER = "html.parser"
DIGIKEY_INVOICE_UUID_REGEX = r"(?P<uuid>[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})"

DIVVY_RECEIPT_EMAIL_ADDRESS = environ["DIVVY_RECEIPT_EMAIL_ADDRESS"]
POSTMARK_TOKEN = environ["POSTMARK_TOKEN"]
DIGIKEY_SENDER_EMAIL_ADDRESS = environ["DIGIKEY_SENDER_EMAIL_ADDRESS"]
MCMASTER_SENDER_EMAIL_ADDRESS = environ["MCMASTER_SENDER_EMAIL_ADDRESS"]
TOP_KART_SENDER_EMAIL_ADDRESS = environ["TOP_KART_SENDER_EMAIL_ADDRESS"]


def digikey_get_invoice_tracking_url(html_body: str) -> Optional[str]:
    """
    Extract the tracking link to download an invoice from a Digi-Key HTML email

    :param html_body: the HTML to parse
    :return: the invoice URL, or None if it could not be extracted
    """
    soup = BeautifulSoup(html_body, HTML_PARSER)

    invoice_url = None

    for a_tag in soup.find_all("a", href=True):
        if a_tag.contents[0] == "Review Invoice":
            invoice_url = a_tag["href"]

    return invoice_url


def digikey_get_invoice_uuid(invoice_url: str) -> Optional[str]:
    """
    Get the invoice UUID from a tracking link

    :param invoice_url: the URL to download the invoice
    :return: the UUID for the invoice, or None if it could not be extracted
    """
    invoice_tracking_redirect = get(invoice_url)

    if invoice_tracking_redirect.status_code != 302:
        print(f"Digi-Key returned {invoice_tracking_redirect.status_code} when accessing tracking URL")
        return None

    soup = BeautifulSoup(invoice_tracking_redirect.text, HTML_PARSER)

    match_parts = search(DIGIKEY_INVOICE_UUID_REGEX, soup.script.contents[0])  # type: ignore

    if match_parts is None:
        print("Could not extract invoice UUID from redirect JavaScript")
        return None

    return match_parts.group("uuid")


def digikey_download_pdf(invoice_uuid: str) -> Optional[bytes]:
    """
    Download the PDF for an invoice given its UUID

    :param invoice_uuid: the UUID of the invoice to download
    :return: the bytes for the PDF, or None if it could not be downloaded
    """
    pdf_binary_response = get(
        "https://www.digikey.com/MyDigiKey/Invoice/PDF",
        params={"id": invoice_uuid},
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"  # noqa
        },
    )

    if pdf_binary_response.status_code != 200:
        print(f"Digi-Key returned {pdf_binary_response.status_code} when downloading PDF")
        return None

    return pdf_binary_response.content


def digikey_forward_to_divvy(pdf_binary: bytes) -> None:
    """
    Send a Digi-Key receipt PDF to Divvy

    :param pdf_binary: The PDF bytes to send
    """
    postmark_response = post(
        "https://api.postmarkapp.com/email",
        headers={"X-Postmark-Server-Token": POSTMARK_TOKEN},
        json={
            "From": DIGIKEY_SENDER_EMAIL_ADDRESS,
            "To": DIVVY_RECEIPT_EMAIL_ADDRESS,
            "Subject": "Receipt for Digi-Key transaction",
            "TextBody": "This is an automatically generated email to upload a Digi-Key receipt to Divvy. Please build a proper API so I don't have to do this. https://github.com/RoboJackets/divvy-receipt-automation",  # noqa: E501
            "MessageStream": "outbound",
            "Attachments": [
                {
                    "Name": "receipt.pdf",
                    "Content": b64encode(pdf_binary).decode("utf-8"),
                    "ContentType": "application/pdf",
                }
            ],
        },
    )

    print(postmark_response.status_code)
    print(postmark_response.text)


def mcmaster_forward_to_divvy(pdf_base64: str) -> None:
    """
    Send a McMaster-Carr receipt PDF to Divvy

    :param pdf_base64: the base64 encoded PDF to send
    """
    postmark_response = post(
        "https://api.postmarkapp.com/email",
        headers={"X-Postmark-Server-Token": POSTMARK_TOKEN},
        json={
            "From": MCMASTER_SENDER_EMAIL_ADDRESS,
            "To": DIVVY_RECEIPT_EMAIL_ADDRESS,
            "Subject": "Receipt for McMaster-Carr transaction",
            "TextBody": "This is an automatically generated email to upload a McMaster-Carr receipt to Divvy. Please build a proper API so I don't have to do this. https://github.com/RoboJackets/divvy-receipt-automation",  # noqa: E501
            "MessageStream": "outbound",
            "Attachments": [
                {
                    "Name": "receipt.pdf",
                    "Content": pdf_base64,
                    "ContentType": "application/pdf",
                }
            ],
        },
    )

    print(postmark_response.status_code)
    print(postmark_response.text)


def top_kart_forward_to_divvy(pdf_base64: str) -> None:
    """
    Send a Top Kart receipt PDF to Divvy

    :param pdf_base64: the base64 encoded PDF to send
    """
    postmark_response = post(
        "https://api.postmarkapp.com/email",
        headers={"X-Postmark-Server-Token": POSTMARK_TOKEN},
        json={
            "From": TOP_KART_SENDER_EMAIL_ADDRESS,
            "To": DIVVY_RECEIPT_EMAIL_ADDRESS,
            "Subject": "Receipt for Top Kart transaction",
            "TextBody": "This is an automatically generated email to upload a Top Kart receipt to Divvy. Please build a proper API so I don't have to do this. https://github.com/RoboJackets/divvy-receipt-automation",  # noqa: E501
            "MessageStream": "outbound",
            "Attachments": [
                {
                    "Name": "receipt.pdf",
                    "Content": pdf_base64,
                    "ContentType": "application/pdf",
                }
            ],
        },
    )

    print(postmark_response.status_code)
    print(postmark_response.text)


def process_digikey_email(html_body: str) -> None:
    """
    Process an email from Digi-Key and forward it to Divvy if it is for a receipt

    :param html_body: the HTML of the email to parse
    """
    invoice_tracking_url = digikey_get_invoice_tracking_url(html_body)

    if invoice_tracking_url is None:
        return

    invoice_uuid = digikey_get_invoice_uuid(invoice_tracking_url)

    if invoice_uuid is None:
        return

    invoice_pdf_binary = digikey_download_pdf(invoice_uuid)

    if invoice_pdf_binary is None:
        return

    digikey_forward_to_divvy(invoice_pdf_binary)


def process_mcmaster_email(attachments: List[Dict[str, str]]) -> None:
    """
    Process an email from McMaster-Carr and forward it to Divvy

    :param attachments: the attachments to parse
    """
    for attachment in attachments:
        if attachment["ContentType"] in ["application/pdf", "application/octet-stream"]:
            mcmaster_forward_to_divvy(attachment["Content"])


def process_top_kart_email(attachments: List[Dict[str, str]]) -> None:
    """
    Process an email from Top Kart and forward it to Divvy

    :param attachments: the attachments to parse
    """
    for attachment in attachments:
        if attachment["ContentType"] in ["application/pdf", "application/octet-stream"]:
            top_kart_forward_to_divvy(attachment["Content"])


def handler(event: Dict[str, str], _: None) -> Dict[str, int]:
    """
    Entrypoint for AWS Lambda

    :param event: The event to process
    :param _: Unused but passed by Lambda anyway
    :return: always a 204 status code, unless something really broke
    """
    if "body" not in event:
        print("Did not find expected key 'body' in Lambda event")
        return {"statusCode": 204}

    try:
        json_payload = loads(event["body"])
    except JSONDecodeError:
        print("Body was not valid JSON")
        return {"statusCode": 204}

    if "HtmlBody" not in json_payload:
        print("Did not find expected key 'HtmlBody' in JSON body")
        return {"statusCode": 204}

    html_body = json_payload["HtmlBody"]
    attachments = json_payload["Attachments"]

    if "digikey" in html_body:
        process_digikey_email(html_body)
    elif "mcmaster" in html_body:
        process_mcmaster_email(attachments)
    elif "topkart" in html_body:
        process_top_kart_email(attachments)

    return {"statusCode": 204}

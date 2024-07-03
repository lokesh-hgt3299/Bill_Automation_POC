from dotenv import load_dotenv
import os, requests, re, json, logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
api_key = os.getenv("OPENAI_KEY")

regular_bill_format = {
    "invoices": [
        {
            "invoice_number": "",
            "invoice_date": "",
            "invoice_amount": "",
            "payment_due_date": "",
            "vendor_name": "",
            "vendor_city": "",
            "vendor_zipcode": "",
            "vendor_address": "",
            "customer_number": "",
            "page_numbers": [],
            "all_address": ["vendor_address", "customer_address"],
            "invoice_type": "",
            "taxes": "",
            "discounts": "",
            "delivery_charges": "",
            "line_items": [
                {
                    "description": "",
                    "net_amount": "",
                    "purpose": "",
                }
            ],
        },
    ]
}

utility_bill_format = {
    "invoices": [
        {
            "invoice_number": "",
            "invoice_date": "bill_date_value or issued_date_value",
            "invoice_amount": "current_month_charges",
            "payment_due_date": "",
            "total_amount_due": "",
            "vendor_name": "",
            "vendor_city": "",
            "vendor_zipcode": "",
            "vendor_address": "",
            "account_number": "",
            "page_numbers": [],
            "all_address": ["vendor_address", "customer_address"],
            "invoice_type": "",
            "taxes": "",
            "discounts": "",
            "adjustments": "",
            "previous_month_charges": "",
            "line_items": [
                {
                    "description": "",
                    "current_charges": "",
                    "purpose": "",
                }
            ],
        },
    ]
}

keywords = {
    "invoice_number": [
        "id",
        "inv",
        "invoice",
        "number",
        "memo",
        "statement",
    ],
    "invoice_date": [
        "bill date",
        "credit date",
        "document date",
        "issue date",
        "memo date",
        "order date",
        "sale date",
        "service date",
        "statement date",
    ],
    "invoice_amount": [
        "amount",
        "balance",
        "charges",
        "due",
        "net",
        "outstanding",
        "payment",
        "remit",
        "total",
        "pay",
    ],
    "delivery_charges": ["freight_charges"],
    "adjustments": ["payments", "adjustments", "credits"],
}

utility_key_names = [
    "Current charges",
    "Total services",
    "Total New charges, Taxes and Surcharges",
    "New charges",
    "Current amount",
    "New charges - due by",
    "Total New charges",
    "Amount Due",
    "Credit Balance (If we have credit from the vendor)",
    "Total amount due",
    "This month's Charges",
    "Charges due",
    "Total Current Charges",
    "Total charges this period",
    "Charges this period",
    "Current Charges Subtotal",
    "Service Related Charges",
]

notALineItems = [
    "LATE FEES",
    "ENERGY SURCHARGE",
    "SUB TOTAL",
    "TOTAL BEFORE TAXES",
    "SALES TAX",
    "MISCELLANEOUS TAXABLE",
    "ENVIRONMENTAL CHARGE",
    "FINANCIAL CHARGE",
    "LINEN PROGRAM",
    "FREIGHT CHARGES",
    "FREIGHT",
    "SHIPPING AND HANDLING",
    "CHEMICAL AND JANITORIAL SUBTOTAL",
    "PAPER AND DISPOSABLES SUBTOTAL",
    "CHARGE",
    "SUPPLY CHAIN SURCHARGE",
    "DELIVERY FUEL SURCHARGE",
    "DELIVERY CHARGE",
    "SERVICE FEE",
    "INVENTORY MAINTENANCE",
    "SERVICE FEE",
    "FUEL INDEX SURCHARGE",
]

f = open(os.path.join(os.getcwd(), "extraction", "purposes.json"), "r")
purposes = json.loads(f.read())


def extract_entities(ocr_text: list, property_name=None):

    prompt = f"""Given the invoices in the form of OCR text, analyze each page to identify information about an invoice.

    1. Identify each invoice whether it is utility bill or regular bill. If Invoice contain this words {utility_key_names} consider it is utility invoice.
        Note: It is mandatory to identify the invoice type.

    2. For each invoice, provide the result in the following formats:
        If it is a utility invoice, use the format: {utility_bill_format}.
        If it is a regular invoice, use the format: {regular_bill_format}.

    3. If an entity is not found in above step, please use the keywords associated with each entity as given in this list to find the entity: {keywords} 

    4. Extract all the line items for each invoice and ensure that every individual item is identified and listed separately, these line items might be spanned across multiple pages.
    
    5. Use these purposes for line items: {purposes['regular']}. Do not include any purposes that are not listed.

    6. Exclude the following description as line items: {notALineItems}

    7. List the page numbers in which the invoice is found.

    While giving the results meet the following conditions:

    1. invoice_number should be unique.

    2. vendor_name should not be {property_name} 

    3. Do not print any analysis in output.

    4. Give me result in json format only.

    Text: {ocr_text}

    Entities:"""

    response = requests.post(
        url="https://api.openai.com/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "gpt-3.5-turbo",  # "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        },
    )

    if response.status_code == 200:
        data = response.json()
        try:
            # Attempt to extract JSON content from the first structure
            content = data["choices"][0]["message"]["content"]
            result: dict = json.loads(content)
            return result.get("invoices")

        except json.JSONDecodeError:
            # If JSON decoding fails, attempt to find JSON content within code blocks
            pattern = re.compile(r"```json(.*?)```", re.DOTALL | re.MULTILINE)
            match = pattern.search(content)

            if match:
                json_string = match.group(1)
                try:
                    # Try to decode JSON from the matched content
                    result = json.loads(json_string)
                    return result.get("invoices")

                except json.JSONDecodeError as error:
                    # Handle JSON decoding error from matched content
                    logger.error("Error decoding JSON from matched content: %s", error)

        except Exception as error:
            # Handle any other unexpected errors during processing
            logger.error("Error while processing content: %s", error)

    else:
        logger.error("Error while getting response from GPT: %s", response.text)

    return []

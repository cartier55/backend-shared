from lxml import html
import requests
# from logger import coach_logger  # Assuming you have a logger module

def find_weekly_links(html_content):
    # coach_logger.log_info("[+] Finding weekly links...")
    # Parse the HTML content
    tree = html.fromstring(html_content)

    # Define a dictionary to hold the day-link pairs
    weekly_links = {}

    # Define days of the week to search for
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    # Iterate over each day and use XPath to find corresponding links
    # coach_logger.log_info("[+] Searching for links...")
    for day in days_of_week:
        # Construct XPath expression for the current day
        xpath_expression = f"//img[contains(@alt, '{day}')]/parent::a/@href"

        # Find all links for the current day using XPath
        links = tree.xpath(xpath_expression)

        # Store the links in the dictionary using the day as the key
        if links:
            weekly_links[day] = links[0]

    # coach_logger.log_info(f"[+] Found {len(weekly_links)} links")
    return weekly_links

def find_class_wods_pdf_link(html_content):
    # coach_logger.log_info("[+] Finding Class Wods PDF link...")
    # Parse the HTML content
    tree = html.fromstring(html_content)

    # XPath expression to find the `a` tag with the exact text 'Class Wods PDF'
    xpath_expression = "//a[text()='Class Wods PDF']/@href"

    # Find the link using XPath
    link = tree.xpath(xpath_expression)

    # Return the link if found, otherwise return None
    return link[0] if link else None

# Example usage:
# Let's assume 'html_content' is a string that contains the HTML from which we want to extract the links.
# html_content = requests.get('URL_OF_YOUR_HTML_PAGE').content
# html_content = """"""
# weekly_programming_links = find_weekly_links(html_content)
# weekly_pdf = find_class_wods_pdf_link(html_content)
# print(weekly_programming_links)
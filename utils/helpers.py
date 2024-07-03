import re


def replace_special_characters(input_string):
    #! Spaces cause major error. Please remove it.
    #! According to AWS Docs these are the name rules.
    # * Check this link to know about "https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html"
    # * Alphanumeric characters
    # 0-9
    # a-z
    # A-Z
    # * Special characters
    # Exclamation point (!)
    # Hyphen (-)
    # Underscore (_)
    # Period (.)
    # Asterisk (*)
    # Single quote (')
    # Open parenthesis (()
    # Close parenthesis ())
    # Regex string must contain these only
    pattern = r"[^0-9a-zA-Z!\-_.*'()]"
    x = re.sub(pattern, "_", input_string)
    return re.sub(r"\s+", "_", x)

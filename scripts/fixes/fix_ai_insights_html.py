#!/usr/bin/env python3
"""
Temporary fix for AI insights HTML parsing errors
Converts HTML formatted messages to plain text
"""
import re

def strip_html_tags(text):
    """Remove all HTML tags from text"""
    # Remove HTML tags
    clean = re.sub('<.*?>', '', text)
    # Decode HTML entities
    clean = clean.replace('&lt;', '<')
    clean = clean.replace('&gt;', '>')
    clean = clean.replace('&amp;', '&')
    clean = clean.replace('&quot;', '"')
    clean = clean.replace('&#39;', "'")
    return clean

def convert_to_markdown(html_text):
    """Convert HTML formatted text to Markdown"""
    # Replace bold tags
    text = html_text.replace('<b>', '**').replace('</b>', '**')
    # Replace italic tags
    text = text.replace('<i>', '_').replace('</i>', '_')
    # Replace code tags
    text = text.replace('<code>', '`').replace('</code>', '`')
    # Remove any remaining HTML tags
    text = re.sub('<.*?>', '', text)
    return text

# Test the function
if __name__ == "__main__":
    sample = """<b>AI MARKET INSIGHTS</b>
├ <b>BTCUSDT</b> <code>+$100.50 (+2.5%)</code>
├ 🟢 Outlook: <b>BULLISH</b> (STRONG signal)
├ 📈 Prediction: Price > $50,000 expected
└ 💡 Action: Consider < 5% position"""
    
    print("Original:")
    print(sample)
    print("\nPlain text:")
    print(strip_html_tags(sample))
    print("\nMarkdown:")
    print(convert_to_markdown(sample))
"""One-time / re-runnable seed script for the RAG knowledge base.

Run after applying supabase/migrations/0001_init.sql:
    cd backend && python -m scripts.seed_scam_patterns

Illustrative examples only, written for the demo — not scraped real victim
data. Extend this list with more categories/languages as time allows; more
patterns = better retrieval grounding = better "Technical Accuracy" score.
"""

from app.core.supabase_client import get_supabase
from app.services.embeddings import embed

SEED_PATTERNS = [
    # KYC update scams
    {"category": "kyc_scam", "language": "en", "pattern_text": "Your KYC will expire today, update immediately by clicking this link or your account will be blocked"},
    {"category": "kyc_scam", "language": "hi", "pattern_text": "आपका केवाईसी आज समाप्त हो जाएगा, तुरंत इस लिंक पर अपडेट करें वरना खाता बंद हो जाएगा"},
    {"category": "kyc_scam", "language": "gu", "pattern_text": "તમારું KYC આજે સમાપ્ત થઈ જશે, તરત જ આ લિંક પર અપડેટ કરો નહીં તો ખાતું બ્લોક થઈ જશે"},
    # OTP sharing requests
    {"category": "otp_scam", "language": "en", "pattern_text": "This is your bank calling, please share the OTP sent to your phone to verify your identity"},
    {"category": "otp_scam", "language": "hi", "pattern_text": "यह आपका बैंक बोल रहा है, कृपया अपनी पहचान सत्यापित करने के लिए फोन पर भेजा गया ओटीपी शेयर करें"},
    {"category": "otp_scam", "language": "gu", "pattern_text": "આ તમારી બેંક બોલે છે, કૃપા કરીને તમારી ઓળખ ચકાસવા માટે ફોન પર મોકલેલ ઓટીપી શેર કરો"},
    # Fake lottery / prize
    {"category": "lottery_scam", "language": "en", "pattern_text": "Congratulations! You have won Rs 25,00,000 in the KBC lucky draw, pay processing fee to claim"},
    {"category": "lottery_scam", "language": "hi", "pattern_text": "बधाई हो! आपने केबीसी लकी ड्रॉ में 25,00,000 रुपये जीते हैं, दावा करने के लिए प्रोसेसिंग शुल्क का भुगतान करें"},
    # Fake refund / cashback
    {"category": "refund_scam", "language": "en", "pattern_text": "Your electricity bill refund of Rs 2340 is pending, click here and enter your UPI PIN to receive it"},
    {"category": "refund_scam", "language": "gu", "pattern_text": "તમારું વીજળી બિલ રિફંડ રૂ 2340 બાકી છે, અહીં ક્લિક કરો અને પ્રાપ્ત કરવા માટે તમારો UPI PIN દાખલ કરો"},
    # Fake loan apps
    {"category": "loan_scam", "language": "en", "pattern_text": "Instant loan of Rs 50000 approved without documents, download this app and pay a small advance fee first"},
    {"category": "loan_scam", "language": "hi", "pattern_text": "बिना दस्तावेजों के 50000 रुपये का तुरंत लोन स्वीकृत, यह ऐप डाउनलोड करें और पहले एक छोटी अग्रिम फीस चुकाएं"},
    # Fake customer care
    {"category": "fake_support_scam", "language": "en", "pattern_text": "For refund assistance call this customer care number and share your card details and CVV"},
    {"category": "fake_support_scam", "language": "gu", "pattern_text": "રિફંડ સહાય માટે આ કસ્ટમર કેર નંબર પર કૉલ કરો અને તમારી કાર્ડ વિગતો અને CVV શેર કરો"},
]


def main() -> None:
    supabase = get_supabase()
    rows = []
    for item in SEED_PATTERNS:
        rows.append(
            {
                "pattern_text": item["pattern_text"],
                "language": item["language"],
                "category": item["category"],
                "embedding": embed(item["pattern_text"]),
            }
        )
    supabase.table("scam_patterns").insert(rows).execute()
    print(f"Seeded {len(rows)} scam patterns.")


if __name__ == "__main__":
    main()

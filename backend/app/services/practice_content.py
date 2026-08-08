"""Curated content bank for Practice mode — a "Scam or Safe?" reflex game.

Deliberately hand-curated and static (not LLM-generated per request): quality
and correctness matter more than novelty here, since this is what teaches
users to actually recognize red flags. Mirrors the scam categories seeded in
scripts/seed_scam_patterns.py plus a couple of game-only categories, and adds
plausible SAFE look-alikes so the game isn't trivially "everything is a scam."

English, Hindi and Gujarati each carry the full 12-item set (same categories,
independently written — not machine-translated) so a full round never has to
silently pad itself out with English content for these three. Every other
language still falls back to English via get_round(), same as the rest of the
app's i18n policy: an English question is honest, a badly-translated safety
message is actively dangerous.
"""

from dataclasses import dataclass, field


@dataclass
class QuizItem:
    id: str
    language: str
    text: str
    is_scam: bool
    category: str
    red_flags: list[str] = field(default_factory=list)
    tip: str = ""


QUIZ_BANK: list[QuizItem] = [
    # ── English ──────────────────────────────────────────────────────────
    QuizItem(
        id="en-1", language="en", is_scam=True, category="kyc_scam",
        text="Dear customer, your KYC has expired and your account will be blocked in 24 hours. Update now: bit.ly/kyc-upd8",
        red_flags=["KYC has expired", "blocked in 24 hours", "bit.ly/kyc-upd8"],
        tip="Real banks never threaten to block your account within hours over a link click, and never use shortened links for KYC.",
    ),
    QuizItem(
        id="en-2", language="en", is_scam=True, category="otp_scam",
        text="This is Rohit from your bank's fraud team. I've blocked a suspicious transaction — just read me the OTP you received to confirm the block.",
        red_flags=["read me the OTP", "fraud team"],
        tip="No bank employee will ever ask you to read out an OTP over the phone — an OTP authorizes a transaction, it doesn't cancel one.",
    ),
    QuizItem(
        id="en-3", language="en", is_scam=True, category="lottery_scam",
        text="CONGRATULATIONS! Your number has won Rs 25,00,000 in the KBC Lucky Draw 2026. Pay Rs 4,999 processing fee to claim your prize today.",
        red_flags=["won", "processing fee", "claim your prize"],
        tip="You can't win a lottery you never entered. Any 'prize' that asks you to pay money first is a scam.",
    ),
    QuizItem(
        id="en-4", language="en", is_scam=True, category="refund_scam",
        text="Your electricity bill refund of Rs 2,340 is pending. Click here and enter your UPI PIN to receive it instantly.",
        red_flags=["enter your UPI PIN", "refund"],
        tip="You NEVER need to enter a UPI PIN to receive money — PINs are only for sending/paying. Any request to 'enter PIN to receive' is a scam.",
    ),
    QuizItem(
        id="en-5", language="en", is_scam=True, category="loan_scam",
        text="Instant personal loan of Rs 50,000 approved, no documents needed! Download this app now and pay a small advance processing fee to release funds.",
        red_flags=["no documents needed", "advance processing fee"],
        tip="Legitimate lenders deduct fees from the loan amount, they never ask you to pay money upfront before disbursing anything.",
    ),
    QuizItem(
        id="en-6", language="en", is_scam=True, category="job_scam",
        text="Congrats! You're selected for a work-from-home data entry job, Rs 3000/day. Pay Rs 999 registration fee to activate your ID and start today.",
        red_flags=["registration fee", "Rs 3000/day", "activate your ID"],
        tip="A real employer pays you — they never charge you to 'activate' a job. Unrealistically high pay for simple work is a major red flag.",
    ),
    QuizItem(
        id="en-7", language="en", is_scam=True, category="investment_scam",
        text="Our AI trading bot guarantees 15% daily returns on crypto investment. Limited slots left, join our Telegram group and deposit now to lock in your spot.",
        red_flags=["guarantees 15% daily returns", "limited slots", "deposit now"],
        tip="No legitimate investment can guarantee daily returns — that's mathematically impossible over time. 'Guaranteed high returns' is the #1 sign of an investment scam.",
    ),
    QuizItem(
        id="en-8", language="en", is_scam=False, category="safe_bank_alert",
        text="Your savings account balance is Rs 12,450 as of today, 6:00 PM. Available balance may vary. This is an auto-generated message, please do not reply.",
        tip="A routine balance alert with no link, no urgency, and no request for information or action — this is what a genuine bank SMS looks like.",
    ),
    QuizItem(
        id="en-9", language="en", is_scam=False, category="safe_delivery",
        text="Your order #48213 has been shipped and will be delivered by tomorrow, 8 PM. Track it in the app under 'My Orders'.",
        tip="Legitimate delivery updates point you to check status inside the official app — they don't ask you to click an external link or share personal details.",
    ),
    QuizItem(
        id="en-10", language="en", is_scam=False, category="safe_personal",
        text="Hey, are we still meeting for lunch tomorrow at 1? Let me know if the time works for you.",
        tip="A normal personal message with no financial ask, no link, no urgency — nothing here needs a security check.",
    ),
    QuizItem(
        id="en-11", language="en", is_scam=False, category="safe_otp_use",
        text="Your OTP for login is 482913. Valid for 10 minutes. Do not share this OTP with anyone, including bank staff.",
        tip="This is a normal, legitimate OTP message — the giveaway that it's safe is that it explicitly tells you never to share it, and you didn't have to do anything.",
    ),
    QuizItem(
        id="en-12", language="en", is_scam=False, category="safe_support",
        text="Thanks for reaching out. Your complaint (Ref #SR3391) has been logged and our team will respond within 2 business days.",
        tip="A genuine support acknowledgment — no request for OTP, PIN, card details, or a payment. Just a reference number and timeline.",
    ),
    # ── Hindi ────────────────────────────────────────────────────────────
    QuizItem(
        id="hi-1", language="hi", is_scam=True, category="kyc_scam",
        text="प्रिय ग्राहक, आपका केवाईसी 24 घंटे में समाप्त हो जाएगा और खाता ब्लॉक हो जाएगा। तुरंत अपडेट करें: bit.ly/kyc-upd8",
        red_flags=["केवाईसी 24 घंटे में समाप्त", "खाता ब्लॉक", "bit.ly/kyc-upd8"],
        tip="असली बैंक कभी भी कुछ घंटों में खाता ब्लॉक करने की धमकी नहीं देते, और केवाईसी के लिए छोटे लिंक इस्तेमाल नहीं करते।",
    ),
    QuizItem(
        id="hi-2", language="hi", is_scam=True, category="otp_scam",
        text="मैं आपके बैंक की फ्रॉड टीम से बोल रहा हूं। एक संदिग्ध लेनदेन रोका गया है — कृपया पुष्टि के लिए मिला ओटीपी बताएं।",
        red_flags=["ओटीपी बताएं", "फ्रॉड टीम"],
        tip="कोई भी बैंक कर्मचारी कभी फोन पर ओटीपी बताने को नहीं कहेगा — ओटीपी लेनदेन को रोकने के लिए नहीं, अनुमति देने के लिए होता है।",
    ),
    QuizItem(
        id="hi-3", language="hi", is_scam=True, category="lottery_scam",
        text="बधाई हो! आपने केबीसी लकी ड्रॉ में 25,00,000 रुपये जीते हैं। दावा करने के लिए आज ही 4,999 रुपये प्रोसेसिंग फीस भरें।",
        red_flags=["जीते हैं", "प्रोसेसिंग फीस", "दावा करने"],
        tip="जो लॉटरी आपने कभी खरीदी ही नहीं, वो जीतना संभव नहीं। कोई भी इनाम जो पहले पैसे मांगे, वो स्कैम है।",
    ),
    QuizItem(
        id="hi-4", language="hi", is_scam=True, category="refund_scam",
        text="आपका बिजली बिल रिफंड 2,340 रुपये बकाया है। तुरंत प्राप्त करने के लिए यहां क्लिक करें और अपना यूपीआई पिन दर्ज करें।",
        red_flags=["यूपीआई पिन दर्ज करें", "रिफंड"],
        tip="पैसे प्राप्त करने के लिए कभी भी यूपीआई पिन डालने की जरूरत नहीं होती — पिन सिर्फ भुगतान भेजने के लिए होता है।",
    ),
    QuizItem(
        id="hi-5", language="hi", is_scam=True, category="loan_scam",
        text="बिना किसी दस्तावेज़ के 50,000 रुपये का तुरंत पर्सनल लोन स्वीकृत! अभी यह ऐप डाउनलोड करें और राशि पाने के लिए मामूली एडवांस प्रोसेसिंग फीस भरें।",
        red_flags=["बिना किसी दस्तावेज़", "एडवांस प्रोसेसिंग फीस"],
        tip="असली कर्जदाता फीस को लोन राशि में से काटते हैं, वे कभी भी पैसा देने से पहले अग्रिम भुगतान नहीं मांगते।",
    ),
    QuizItem(
        id="hi-6", language="hi", is_scam=True, category="job_scam",
        text="बधाई हो! आपका वर्क-फ्रॉम-होम डेटा एंट्री जॉब के लिए चयन हुआ है, 3000 रुपये/दिन। आज ही अपनी आईडी एक्टिवेट करने के लिए 999 रुपये रजिस्ट्रेशन फीस भरें।",
        red_flags=["रजिस्ट्रेशन फीस", "3000 रुपये/दिन", "आईडी एक्टिवेट"],
        tip="असली नियोक्ता आपको पैसे देता है — वे कभी भी नौकरी 'एक्टिवेट' करने के लिए पैसे नहीं मांगते। साधारण काम के लिए बहुत ज़्यादा वेतन एक बड़ा खतरे का संकेत है।",
    ),
    QuizItem(
        id="hi-7", language="hi", is_scam=True, category="investment_scam",
        text="हमारा AI ट्रेडिंग बॉट क्रिप्टो निवेश पर 15% रोज़ाना रिटर्न की गारंटी देता है। सीमित सीटें बची हैं, अभी हमारे टेलीग्राम ग्रुप से जुड़ें और डिपॉज़िट करके अपनी जगह पक्की करें।",
        red_flags=["15% रोज़ाना रिटर्न की गारंटी", "सीमित सीटें", "अभी डिपॉज़िट करें"],
        tip="कोई भी वैध निवेश रोज़ाना रिटर्न की गारंटी नहीं दे सकता — यह गणितीय रूप से असंभव है। 'गारंटीड ज़्यादा रिटर्न' निवेश धोखाधड़ी का नंबर एक संकेत है।",
    ),
    QuizItem(
        id="hi-8", language="hi", is_scam=False, category="safe_bank_alert",
        text="आपका बचत खाता शेष आज शाम 6 बजे तक 12,450 रुपये है। यह एक स्वतः-जनित संदेश है, कृपया उत्तर न दें।",
        tip="बिना लिंक, बिना जल्दबाजी और बिना किसी जानकारी मांगे — यह असली बैंक संदेश जैसा दिखता है।",
    ),
    QuizItem(
        id="hi-9", language="hi", is_scam=False, category="safe_delivery",
        text="आपका ऑर्डर #48213 भेज दिया गया है और कल रात 8 बजे तक डिलीवर हो जाएगा। ऐप में 'My Orders' में जाकर ट्रैक करें।",
        tip="असली डिलीवरी अपडेट आपको ऐप के अंदर ही स्थिति देखने के लिए कहते हैं — वे किसी बाहरी लिंक पर क्लिक करने या निजी जानकारी मांगने को नहीं कहते।",
    ),
    QuizItem(
        id="hi-10", language="hi", is_scam=False, category="safe_personal",
        text="कल दोपहर 1 बजे मिलना है क्या? बताना अगर समय ठीक है।",
        tip="कोई पैसे की मांग नहीं, कोई लिंक नहीं, कोई जल्दबाजी नहीं — यह एक सामान्य व्यक्तिगत संदेश है।",
    ),
    QuizItem(
        id="hi-11", language="hi", is_scam=False, category="safe_otp_use",
        text="लॉगिन के लिए आपका ओटीपी 482913 है। यह 10 मिनट के लिए मान्य है। इसे बैंक कर्मचारी सहित किसी के साथ साझा न करें।",
        tip="यह एक सामान्य, असली ओटीपी संदेश है — इसके सुरक्षित होने का संकेत यह है कि यह साफ़ तौर पर कहता है कि इसे कभी साझा न करें, और आपको कुछ करने की ज़रूरत नहीं थी।",
    ),
    QuizItem(
        id="hi-12", language="hi", is_scam=False, category="safe_support",
        text="संपर्क करने के लिए धन्यवाद। आपकी शिकायत (संदर्भ #SR3391) दर्ज कर ली गई है और हमारी टीम 2 कार्य दिवसों के भीतर जवाब देगी।",
        tip="एक असली सपोर्ट पावती — कोई ओटीपी, पिन, कार्ड विवरण या भुगतान नहीं मांगा गया। बस एक संदर्भ नंबर और समयसीमा।",
    ),
    # ── Gujarati ─────────────────────────────────────────────────────────
    QuizItem(
        id="gu-1", language="gu", is_scam=True, category="kyc_scam",
        text="પ્રિય ગ્રાહક, તમારું KYC 24 કલાકમાં સમાપ્ત થઈ જશે અને ખાતું બ્લોક થઈ જશે. તરત અપડેટ કરો: bit.ly/kyc-upd8",
        red_flags=["24 કલાકમાં સમાપ્ત", "ખાતું બ્લોક", "bit.ly/kyc-upd8"],
        tip="ખરી બેંક ક્યારેય થોડા કલાકોમાં ખાતું બ્લોક કરવાની ધમકી નથી આપતી, અને KYC માટે ટૂંકી લિંક વાપરતી નથી.",
    ),
    QuizItem(
        id="gu-2", language="gu", is_scam=True, category="otp_scam",
        text="હું તમારી બેંકની ફ્રોડ ટીમમાંથી બોલું છું. શંકાસ્પદ ટ્રાન્ઝેક્શન રોકાયું છે — પુષ્ટિ માટે મળેલો OTP કહો.",
        red_flags=["OTP કહો", "ફ્રોડ ટીમ"],
        tip="કોઈ પણ બેંક કર્મચારી ફોન પર OTP કહેવાનું ક્યારેય નહીં કહે — OTP ટ્રાન્ઝેક્શન રોકવા માટે નહીં, મંજૂરી આપવા માટે હોય છે.",
    ),
    QuizItem(
        id="gu-3", language="gu", is_scam=True, category="lottery_scam",
        text="અભિનંદન! તમે KBC લકી ડ્રો 2026 માં રૂ 25,00,000 જીત્યા છે. તમારું ઇનામ મેળવવા આજે જ રૂ 4,999 પ્રોસેસિંગ ફી ભરો.",
        red_flags=["જીત્યા છે", "પ્રોસેસિંગ ફી", "ઇનામ મેળવવા"],
        tip="તમે ક્યારેય ખરીદી ન હોય તેવી લોટરી જીતવી શક્ય નથી. કોઈ પણ 'ઇનામ' જે પહેલા પૈસા માંગે તે છેતરપિંડી છે.",
    ),
    QuizItem(
        id="gu-4", language="gu", is_scam=True, category="refund_scam",
        text="તમારું વીજળી બિલ રિફંડ રૂ 2,340 બાકી છે. તરત મેળવવા માટે અહીં ક્લિક કરો અને તમારો UPI PIN દાખલ કરો.",
        red_flags=["UPI PIN દાખલ કરો", "રિફંડ"],
        tip="પૈસા મેળવવા માટે ક્યારેય UPI PIN નાખવાની જરૂર નથી હોતી — PIN ફક્ત ચુકવણી મોકલવા માટે હોય છે.",
    ),
    QuizItem(
        id="gu-5", language="gu", is_scam=True, category="loan_scam",
        text="કોઈ પણ દસ્તાવેજ વગર રૂ 50,000 ની તાત્કાલિક પર્સનલ લોન મંજૂર! અત્યારે જ આ એપ ડાઉનલોડ કરો અને રકમ મેળવવા થોડી એડવાન્સ પ્રોસેસિંગ ફી ભરો.",
        red_flags=["કોઈ પણ દસ્તાવેજ વગર", "એડવાન્સ પ્રોસેસિંગ ફી"],
        tip="ખરા ધિરાણકર્તા ફી ને લોનની રકમમાંથી કાપે છે, તેઓ ક્યારેય રકમ આપતા પહેલા આગોતરી ચુકવણી માંગતા નથી.",
    ),
    QuizItem(
        id="gu-6", language="gu", is_scam=True, category="job_scam",
        text="અભિનંદન! તમારી વર્ક-ફ્રોમ-હોમ ડેટા એન્ટ્રી જોબ માટે પસંદગી થઈ છે, રૂ 3000/દિવસ. તમારી ID એક્ટિવેટ કરવા આજે જ રૂ 999 રજિસ્ટ્રેશન ફી ભરો.",
        red_flags=["રજિસ્ટ્રેશન ફી", "રૂ 3000/દિવસ", "ID એક્ટિવેટ"],
        tip="ખરો નોકરીદાતા તમને પૈસા આપે છે — તેઓ ક્યારેય નોકરી 'એક્ટિવેટ' કરવા પૈસા માંગતા નથી. સાદા કામ માટે ખૂબ વધારે પગાર એ મોટો ખતરાનો સંકેત છે.",
    ),
    QuizItem(
        id="gu-7", language="gu", is_scam=True, category="investment_scam",
        text="અમારો AI ટ્રેડિંગ બોટ ક્રિપ્ટો રોકાણ પર 15% રોજિંદા વળતરની ગેરંટી આપે છે. મર્યાદિત જગ્યાઓ બાકી છે, અમારા ટેલિગ્રામ ગ્રુપમાં જોડાઓ અને હમણાં જ ડિપોઝિટ કરી તમારી જગ્યા પાક્કી કરો.",
        red_flags=["15% રોજિંદા વળતરની ગેરંટી", "મર્યાદિત જગ્યાઓ", "હમણાં જ ડિપોઝિટ"],
        tip="કોઈ પણ ખરું રોકાણ રોજિંદા વળતરની ગેરંટી આપી શકતું નથી — તે ગણિતની રીતે અશક્ય છે. 'ગેરંટીડ વધારે વળતર' એ રોકાણ છેતરપિંડીની નંબર વન નિશાની છે.",
    ),
    QuizItem(
        id="gu-8", language="gu", is_scam=False, category="safe_bank_alert",
        text="તમારું બચત ખાતું બેલેન્સ આજે સાંજે 6 વાગ્યા સુધી રૂ 12,450 છે. આ સ્વયં-જનરેટેડ સંદેશ છે, કૃપા કરી જવાબ ન આપો.",
        tip="લિંક વગર, ઉતાવળ વગર અને કોઈ માહિતી માંગ્યા વગર — આ ખરા બેંક સંદેશ જેવું લાગે છે.",
    ),
    QuizItem(
        id="gu-9", language="gu", is_scam=False, category="safe_delivery",
        text="તમારો ઓર્ડર #48213 મોકલી દેવાયો છે અને આવતીકાલે રાત્રે 8 વાગ્યા સુધીમાં પહોંચી જશે. એપમાં 'My Orders' હેઠળ ટ્રેક કરો.",
        tip="ખરા ડિલિવરી અપડેટ તમને એપની અંદર જ સ્થિતિ ચકાસવાનું કહે છે — તેઓ બહારની લિંક પર ક્લિક કરવા કે અંગત માહિતી શેર કરવા કહેતા નથી.",
    ),
    QuizItem(
        id="gu-10", language="gu", is_scam=False, category="safe_personal",
        text="કાલે બપોરે 1 વાગ્યે મળીએ છીએ ને? સમય બરાબર હોય તો જણાવજે.",
        tip="કોઈ પૈસાની માંગ નહીં, કોઈ લિંક નહીં, કોઈ ઉતાવળ નહીં — આ એક સામાન્ય અંગત સંદેશ છે.",
    ),
    QuizItem(
        id="gu-11", language="gu", is_scam=False, category="safe_otp_use",
        text="લોગિન માટે તમારો OTP 482913 છે. તે 10 મિનિટ માટે માન્ય છે. તેને બેંક કર્મચારી સહિત કોઈની સાથે શેર ન કરો.",
        tip="આ એક સામાન્ય, ખરો OTP સંદેશ છે — તે સુરક્ષિત હોવાની નિશાની એ છે કે તે સ્પષ્ટ કહે છે કે તેને ક્યારેય શેર ન કરો, અને તમારે કંઈ કરવાની જરૂર નહોતી.",
    ),
    QuizItem(
        id="gu-12", language="gu", is_scam=False, category="safe_support",
        text="સંપર્ક કરવા બદલ આભાર. તમારી ફરિયાદ (સંદર્ભ #SR3391) નોંધાઈ ગઈ છે અને અમારી ટીમ 2 કાર્યકારી દિવસોમાં જવાબ આપશે.",
        tip="એક ખરો સપોર્ટ સ્વીકૃતિ — કોઈ OTP, PIN, કાર્ડ વિગતો કે ચુકવણી માંગી નથી. ફક્ત એક સંદર્ભ નંબર અને સમયમર્યાદા.",
    ),
]

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "kyc_scam": "KYC Scam",
        "otp_scam": "OTP Scam",
        "lottery_scam": "Lottery Scam",
        "refund_scam": "Refund Scam",
        "loan_scam": "Loan Scam",
        "job_scam": "Job Scam",
        "investment_scam": "Investment Scam",
        "safe_bank_alert": "Genuine Bank Alert",
        "safe_delivery": "Genuine Delivery Update",
        "safe_personal": "Personal Message",
        "safe_otp_use": "Genuine OTP",
        "safe_support": "Genuine Support Reply",
    },
    "hi": {
        "kyc_scam": "केवाईसी स्कैम",
        "otp_scam": "ओटीपी स्कैम",
        "lottery_scam": "लॉटरी स्कैम",
        "refund_scam": "रिफंड स्कैम",
        "loan_scam": "लोन स्कैम",
        "job_scam": "जॉब स्कैम",
        "investment_scam": "निवेश स्कैम",
        "safe_bank_alert": "असली बैंक अलर्ट",
        "safe_delivery": "असली डिलीवरी अपडेट",
        "safe_personal": "व्यक्तिगत संदेश",
        "safe_otp_use": "असली ओटीपी",
        "safe_support": "असली सपोर्ट जवाब",
    },
    "gu": {
        "kyc_scam": "KYC સ્કેમ",
        "otp_scam": "OTP સ્કેમ",
        "lottery_scam": "લોટરી સ્કેમ",
        "refund_scam": "રિફંડ સ્કેમ",
        "loan_scam": "લોન સ્કેમ",
        "job_scam": "જોબ સ્કેમ",
        "investment_scam": "રોકાણ સ્કેમ",
        "safe_bank_alert": "ખરો બેંક અલર્ટ",
        "safe_delivery": "ખરો ડિલિવરી અપડેટ",
        "safe_personal": "અંગત સંદેશ",
        "safe_otp_use": "ખરો OTP",
        "safe_support": "ખરો સપોર્ટ જવાબ",
    },
}


def category_label(category: str, language: str) -> str:
    """Falls back to the English label if `language` has no translated
    category names (or if `category` is somehow unknown in either)."""
    labels = CATEGORY_LABELS.get(language, CATEGORY_LABELS["en"])
    return labels.get(category, CATEGORY_LABELS["en"].get(category, category))


def get_round(language: str, count: int) -> list[QuizItem]:
    """Returns up to `count` items for the given language, falling back to
    English items to top up if a language doesn't have enough curated content
    yet (keeps the game playable while the content bank grows)."""
    pool = [item for item in QUIZ_BANK if item.language == language]
    if language != "en" and len(pool) < count:
        pool = pool + [item for item in QUIZ_BANK if item.language == "en"]
    return pool

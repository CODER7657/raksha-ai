import type { Verdict } from './scanResult'

export interface SimulatorQuestion {
  id: string
  message: string
  language: string
  verdict: Verdict
  /** Matches the category taxonomy in backend/scripts/seed_scam_patterns.py,
   * shown as a tag so patterns become recognizable across questions. */
  category: string
  /** Phrases shown as selectable chips — a mix of real red flags and decoys. */
  candidatePhrases: string[]
  /** Ground-truth subset of candidatePhrases that are actually red flags. */
  flaggedPhrases: string[]
  explanation: string
}

/** Local mock data — GET /api/simulator/questions isn't implemented on the
 * backend yet (see frontend/README.md), swap this out once it lands.
 * Categories deliberately mirror backend/scripts/seed_scam_patterns.py so
 * the quiz reinforces the same pattern language the real scanner uses. */
export const SIMULATOR_QUESTIONS: SimulatorQuestion[] = [
  {
    id: 'q1',
    message: 'Dear customer, your KYC will expire today. Click bit.ly/kyc-verify now to avoid account suspension.',
    language: 'en',
    verdict: 'high_risk',
    category: 'KYC scam',
    candidatePhrases: ['Dear customer', 'expire today', 'bit.ly/kyc-verify', 'account suspension'],
    flaggedPhrases: ['expire today', 'bit.ly/kyc-verify', 'account suspension'],
    explanation:
      'Urgency ("expire today"), a shortened link instead of your bank\'s real website, and a suspension threat are all classic phishing pressure tactics.',
  },
  {
    id: 'q2',
    message: 'Sir aapka account block ho jayega, turant apna OTP number bataiye verify karne ke liye.',
    language: 'hi',
    verdict: 'high_risk',
    category: 'OTP scam',
    candidatePhrases: ['Sir aapka account', 'block ho jayega', 'OTP number bataiye', 'verify karne ke liye'],
    flaggedPhrases: ['block ho jayega', 'OTP number bataiye'],
    explanation:
      'No legitimate bank or company will ever ask you to share your OTP over a call — that request alone is the scam, regardless of the urgency wrapped around it.',
  },
  {
    id: 'q3',
    message: 'Hi, are we still meeting for lunch tomorrow at 1pm near the office?',
    language: 'en',
    verdict: 'safe',
    category: 'Not a scam',
    candidatePhrases: ['meeting for lunch', 'tomorrow at 1pm', 'near the office'],
    flaggedPhrases: [],
    explanation:
      'A normal personal message with no urgency, no links, no request for money or personal details — nothing here matches a scam pattern.',
  },
  {
    id: 'q4',
    message: 'Congratulations! Aapka number KBC lottery mein select hua hai. ₹25,00,000 jeetne ke liye is number par turant call karein.',
    language: 'hi',
    verdict: 'high_risk',
    category: 'Lottery scam',
    candidatePhrases: ['Congratulations', 'KBC lottery mein select', '₹25,00,000 jeetne', 'turant call karein'],
    flaggedPhrases: ['KBC lottery mein select', '₹25,00,000 jeetne', 'turant call karein'],
    explanation:
      'A lottery you never entered, a large unearned prize, and pressure to call immediately — a textbook advance-fee scam pattern.',
  },
  {
    id: 'q5',
    message: 'Your electricity bill refund of Rs 2340 is pending. Click here and enter your UPI PIN to receive it.',
    language: 'en',
    verdict: 'high_risk',
    category: 'Refund scam',
    candidatePhrases: ['electricity bill refund', 'Rs 2340', 'click here', 'enter your UPI PIN'],
    flaggedPhrases: ['click here', 'enter your UPI PIN'],
    explanation:
      'A real refund never needs your UPI PIN — that field is for authorizing a *payment out*, not receiving one. Asking for it here is the entire scam.',
  },
  {
    id: 'q6',
    message: 'Instant loan of Rs 50000 approved without documents — download this app and pay a small advance fee first.',
    language: 'en',
    verdict: 'high_risk',
    category: 'Loan app scam',
    candidatePhrases: ['Instant loan', 'approved without documents', 'download this app', 'advance fee first'],
    flaggedPhrases: ['approved without documents', 'advance fee first'],
    explanation:
      'A loan "approved" before any paperwork, gated behind a fee paid upfront, is the advance-fee pattern — real lenders deduct fees from the loan, they never ask you to pay in first.',
  },
  {
    id: 'q7',
    message: 'Reminder: your dentist appointment is confirmed for Thursday 10:30am. Reply STOP to cancel.',
    language: 'en',
    verdict: 'safe',
    category: 'Not a scam',
    candidatePhrases: ['dentist appointment', 'Thursday 10:30am', 'Reply STOP to cancel'],
    flaggedPhrases: [],
    explanation:
      'A standard appointment reminder — no financial request, no urgency beyond a normal reminder, no suspicious link.',
  },
]

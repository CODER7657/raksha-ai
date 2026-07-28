import type { Verdict } from './scanResult'

export interface SimulatorQuestion {
  id: string
  message: string
  language: string
  verdict: Verdict
  /** Phrases shown as selectable chips — a mix of real red flags and decoys. */
  candidatePhrases: string[]
  /** Ground-truth subset of candidatePhrases that are actually red flags. */
  flaggedPhrases: string[]
  explanation: string
}

/** Local mock data — GET /api/simulator/questions isn't implemented on the
 * backend yet (see frontend/README.md), swap this out once it lands. */
export const SIMULATOR_QUESTIONS: SimulatorQuestion[] = [
  {
    id: 'q1',
    message: 'Dear customer, your KYC will expire today. Click bit.ly/kyc-verify now to avoid account suspension.',
    language: 'en',
    verdict: 'high_risk',
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
    candidatePhrases: ['Congratulations', 'KBC lottery mein select', '₹25,00,000 jeetne', 'turant call karein'],
    flaggedPhrases: ['KBC lottery mein select', '₹25,00,000 jeetne', 'turant call karein'],
    explanation:
      'A lottery you never entered, a large unearned prize, and pressure to call immediately — a textbook advance-fee scam pattern.',
  },
]

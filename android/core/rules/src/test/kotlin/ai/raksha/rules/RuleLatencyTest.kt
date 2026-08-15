package ai.raksha.rules

import kotlin.system.measureNanoTime
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Guards the latency budget from ARCHITECTURE.md (~200ms on device).
 *
 * This is a JVM smoke test, not a benchmark. It runs on desktop hardware, so a
 * pass here does not prove the budget holds on a cheap handset — the real
 * measurement is the Macrobenchmark in #29 §8. What it does catch is the
 * regression that would actually blow the budget: rebuilding [Regex] objects
 * per message instead of once at class-load. That mistake is orders of
 * magnitude, so it shows up even on fast hardware.
 *
 * The threshold is deliberately loose. A tight one on shared CI runners is a
 * flaky test, and a flaky performance test gets disabled, which is worse than
 * not having it.
 */
class RuleLatencyTest {

    private val message = buildString {
        append("Dear customer, your KYC is expiring today. ")
        append("Share your OTP now or your account will be blocked. ")
        append("Claim your refund by clicking the link below. ")
        while (length < 500) append("Please verify your details immediately. ")
    }.take(500)

    @Test
    fun `a full rule sweep over a 500 character message stays well inside budget`() {
        repeat(200) { offlineRuleHits(message, "hi") } // warm up the JIT

        val runs = 100
        val elapsedNanos = measureNanoTime {
            repeat(runs) { offlineRuleHits(message, "hi") }
        }
        val perSweepMillis = elapsedNanos / runs / 1_000_000.0

        // 20ms is a tenth of the on-device budget, leaving room for a phone
        // being far slower than a CI runner while still catching per-message
        // recompilation, which costs milliseconds per pattern.
        assertTrue(
            perSweepMillis < 20.0,
            "rule sweep took %.3f ms per message (budget for this test: 20 ms). "
                .format(perSweepMillis) +
                "The usual cause is Regex objects being constructed per call " +
                "instead of once at class-load.",
        )
    }

    @Test
    fun `hindi sweep also runs the english rules and still fits`() {
        // The hi path evaluates hi + en rules, so it is the worst case.
        val hiRuleCount = RULES.getValue("hi").size + RULES.getValue("en").size
        assertTrue(hiRuleCount >= RULES.getValue("en").size)

        repeat(100) { offlineRuleHits(message, "hi") }
        val nanos = measureNanoTime { repeat(50) { offlineRuleHits(message, "hi") } }
        assertTrue((nanos / 50 / 1_000_000.0) < 20.0)
    }
}

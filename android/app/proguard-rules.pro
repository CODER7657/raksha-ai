# R8 rules for the release build.
#
# Kept deliberately short. Every keep rule is a piece of the app R8 may not
# shrink or rename, so a long file is usually a sign someone silenced a crash
# rather than understood it. If you add one, say why here — "fixes a crash" is
# not a reason, it is a symptom.

# --- Entry points Android reaches by name, not by call -----------------------
#
# The manifest names these as strings, so nothing in the bytecode references
# them and R8 would otherwise consider them unreachable. Losing the receiver
# would mean the app builds, installs, runs — and silently never scans an SMS,
# which is the worst possible failure for this particular class.
-keep class ai.raksha.app.MainActivity { *; }
-keep class ai.raksha.app.sms.SmsReceiver { *; }

# --- Nothing else needs a rule, and that is on purpose -----------------------
#
# `:core:rules` is plain Kotlin with no reflection: the engine compiles regexes
# held in a list and returns data classes. R8 may rename all of it freely.
#
# Compose and AndroidX ship their own consumer rules through AGP, so repeating
# them here would only create a second copy to drift.
#
# SafeLogContractTest uses reflection over SafeLog, but it is a JVM unit test
# and never runs against a minified build — so SafeLog needs no keep rule, and
# giving it one would defeat the point of shrinking a privacy-sensitive class.

# --- Stack traces we can actually read ---------------------------------------
#
# Without this a crash report from a pilot user is unusable, and the mapping
# file stays on the build machine rather than in the APK.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

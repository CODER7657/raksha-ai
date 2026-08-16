package ai.raksha.app.data

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/**
 * [ScanStore] on the platform's SQLite. See that interface for why not Room.
 *
 * Two tables rather than one row with a serialised blob: a hit is a real thing
 * with three fields the trace schema names, and flattening it into JSON would
 * make the one query that matters — "show me this scan's rules" — a string
 * parse. It also keeps the shape close to what Room would generate, so the
 * swap stays mechanical.
 *
 * Every call here is synchronous and must be made off the main thread. The two
 * callers are the SMS receiver's background executor and a ViewModel's
 * `Dispatchers.IO`, both of which already are.
 */
class SqliteScanStore(context: Context) : ScanStore {

    private val helper = Helper(context.applicationContext)

    override fun recent(limit: Int): List<ScanRecord> =
        helper.readableDatabase.use { db ->
            val scans = db.query(
                TABLE_SCANS, null, null, null, null, null, "$COL_SCANNED_AT DESC", limit.toString(),
            ).use { cursor -> generateSequence { if (cursor.moveToNext()) cursor.readScan() else null }.toList() }

            // One query for every hit rather than one per scan: a history screen
            // of 200 rows would otherwise be 201 queries.
            val hits = db.hitsFor(scans.map { it.first })
            scans.map { (id, record) -> record.copy(hits = hits[id].orEmpty()) }
        }

    override fun byId(id: Long): ScanRecord? =
        helper.readableDatabase.use { db ->
            val scan = db.query(
                TABLE_SCANS, null, "$COL_ID = ?", arrayOf(id.toString()), null, null, null,
            ).use { cursor -> if (cursor.moveToFirst()) cursor.readScan() else null } ?: return null
            scan.second.copy(hits = db.hitsFor(listOf(id))[id].orEmpty())
        }

    override fun record(
        scannedAtMillis: Long,
        sender: String,
        language: String,
        body: String,
        hits: List<RuleHitRecord>,
        ruleReviewStatus: String,
    ): ScanRecord? = helper.writableDatabase.use { db ->
        db.beginTransaction()
        try {
            val id = db.insert(
                TABLE_SCANS, null,
                ContentValues().apply {
                    put(COL_SCANNED_AT, scannedAtMillis)
                    put(COL_SENDER, sender)
                    put(COL_LANGUAGE, language)
                    put(COL_BODY, body)
                    put(COL_REVIEW_STATUS, ruleReviewStatus)
                },
            )
            if (id == -1L) return@use null

            hits.forEach { hit ->
                db.insert(
                    TABLE_HITS, null,
                    ContentValues().apply {
                        put(COL_SCAN_ID, id)
                        put(COL_RULE_ID, hit.ruleId)
                        put(COL_PATTERN, hit.pattern)
                        put(COL_MATCHED_TEXT, hit.matchedText)
                    },
                )
            }

            // Trim inside the same transaction, so the cap cannot be exceeded
            // by a crash between insert and prune. `ON DELETE CASCADE` takes the
            // hits with the scan.
            db.execSQL(
                "DELETE FROM $TABLE_SCANS WHERE $COL_ID NOT IN " +
                    "(SELECT $COL_ID FROM $TABLE_SCANS ORDER BY $COL_SCANNED_AT DESC LIMIT ?)",
                arrayOf(ScanStore.MAX_RECORDS),
            )

            db.setTransactionSuccessful()
            ScanRecord(id, scannedAtMillis, sender, language, body, hits, ruleReviewStatus)
        } finally {
            db.endTransaction()
        }
    }

    override fun clear() {
        helper.writableDatabase.use { db ->
            // Hits go first even with the cascade, so a database opened without
            // foreign keys on cannot leave orphans behind.
            db.delete(TABLE_HITS, null, null)
            db.delete(TABLE_SCANS, null, null)
        }
    }

    override fun count(): Int =
        helper.readableDatabase.use { db ->
            db.rawQuery("SELECT COUNT(*) FROM $TABLE_SCANS", null).use { cursor ->
                if (cursor.moveToFirst()) cursor.getInt(0) else 0
            }
        }

    // --- reading -------------------------------------------------------------

    private fun Cursor.readScan(): Pair<Long, ScanRecord> {
        val id = getLong(getColumnIndexOrThrow(COL_ID))
        return id to ScanRecord(
            id = id,
            scannedAtMillis = getLong(getColumnIndexOrThrow(COL_SCANNED_AT)),
            sender = getString(getColumnIndexOrThrow(COL_SENDER)).orEmpty(),
            language = getString(getColumnIndexOrThrow(COL_LANGUAGE)).orEmpty(),
            body = getString(getColumnIndexOrThrow(COL_BODY)).orEmpty(),
            hits = emptyList(),
            ruleReviewStatus = getString(getColumnIndexOrThrow(COL_REVIEW_STATUS)).orEmpty(),
        )
    }

    private fun SQLiteDatabase.hitsFor(scanIds: List<Long>): Map<Long, List<RuleHitRecord>> {
        if (scanIds.isEmpty()) return emptyMap()
        val placeholders = scanIds.joinToString(",") { "?" }
        return rawQuery(
            "SELECT $COL_SCAN_ID, $COL_RULE_ID, $COL_PATTERN, $COL_MATCHED_TEXT " +
                "FROM $TABLE_HITS WHERE $COL_SCAN_ID IN ($placeholders) ORDER BY $COL_ID ASC",
            scanIds.map { it.toString() }.toTypedArray(),
        ).use { cursor ->
            buildMap<Long, MutableList<RuleHitRecord>> {
                while (cursor.moveToNext()) {
                    getOrPut(cursor.getLong(0)) { mutableListOf() }
                        .add(RuleHitRecord(cursor.getString(1), cursor.getString(2), cursor.getString(3)))
                }
            }
        }
    }

    private class Helper(context: Context) :
        SQLiteOpenHelper(context, DATABASE_NAME, null, DATABASE_VERSION) {

        override fun onConfigure(db: SQLiteDatabase) {
            db.setForeignKeyConstraintsEnabled(true)
        }

        override fun onCreate(db: SQLiteDatabase) {
            db.execSQL(
                """
                CREATE TABLE $TABLE_SCANS (
                    $COL_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    $COL_SCANNED_AT INTEGER NOT NULL,
                    $COL_SENDER TEXT NOT NULL,
                    $COL_LANGUAGE TEXT NOT NULL,
                    $COL_BODY TEXT NOT NULL,
                    $COL_REVIEW_STATUS TEXT NOT NULL
                )
                """.trimIndent(),
            )
            db.execSQL("CREATE INDEX idx_scans_time ON $TABLE_SCANS($COL_SCANNED_AT DESC)")
            db.execSQL(
                """
                CREATE TABLE $TABLE_HITS (
                    $COL_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    $COL_SCAN_ID INTEGER NOT NULL,
                    $COL_RULE_ID TEXT NOT NULL,
                    $COL_PATTERN TEXT NOT NULL,
                    $COL_MATCHED_TEXT TEXT NOT NULL,
                    FOREIGN KEY($COL_SCAN_ID) REFERENCES $TABLE_SCANS($COL_ID) ON DELETE CASCADE
                )
                """.trimIndent(),
            )
            db.execSQL("CREATE INDEX idx_hits_scan ON $TABLE_HITS($COL_SCAN_ID)")
        }

        override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
            // Version 1 is the first release. When there is a version 2 this
            // becomes a real migration — dropping a user's history to avoid
            // writing one would be deleting their data to save our time.
            throw IllegalStateException(
                "No migration from $oldVersion to $newVersion. Write one; do not drop the table.",
            )
        }
    }

    private companion object {
        const val DATABASE_NAME = "raksha_scans.db"
        const val DATABASE_VERSION = 1

        const val TABLE_SCANS = "scans"
        const val TABLE_HITS = "rule_hits"

        const val COL_ID = "id"
        const val COL_SCANNED_AT = "scanned_at"
        const val COL_SENDER = "sender"
        const val COL_LANGUAGE = "language"
        const val COL_BODY = "body"
        const val COL_REVIEW_STATUS = "rule_review_status"

        const val COL_SCAN_ID = "scan_id"
        const val COL_RULE_ID = "rule_id"
        const val COL_PATTERN = "pattern"
        const val COL_MATCHED_TEXT = "matched_text"
    }
}

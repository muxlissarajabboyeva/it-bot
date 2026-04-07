import sqlite3
from pathlib import Path
from difflib import get_close_matches

DB_PATH = Path(__file__).resolve().parent / "terms.db"


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        english_word TEXT NOT NULL UNIQUE,
        full_form TEXT,
        uzbek_translation TEXT NOT NULL,
        explanation TEXT NOT NULL,
        example TEXT,
        level TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        english_word TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, english_word)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        english_word TEXT NOT NULL,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS term_stats (
        english_word TEXT PRIMARY KEY,
        search_count INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


def register_user(user_id: int, username: str | None, first_name: str | None):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (user_id, username, first_name)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        first_name=excluded.first_name
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def normalize_level(level: str) -> str:
    level = (level or "").strip().lower()
    mapping = {
        "beginner": "beginner",
        "boshlangich": "beginner",
        "boshlang'ich": "beginner",
        "intermediate": "intermediate",
        "orta": "intermediate",
        "o'rta": "intermediate",
        "advanced": "advanced",
        "murakkab": "advanced",
    }
    return mapping.get(level, level)


def get_level_label(level: str) -> str:
    level = normalize_level(level)
    mapping = {
        "beginner": "Boshlang‘ich",
        "intermediate": "O‘rta",
        "advanced": "Murakkab",
    }
    return mapping.get(level, level)


def get_term(word: str):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM terms WHERE lower(english_word) = ?",
        (word.strip().lower(),)
    )
    result = cursor.fetchone()
    conn.close()
    return result


def get_random_term(level: str | None = None):
    conn = connect_db()
    cursor = conn.cursor()

    if level:
        level = normalize_level(level)
        cursor.execute(
            "SELECT * FROM terms WHERE lower(level) = ? ORDER BY RANDOM() LIMIT 1",
            (level,)
        )
    else:
        cursor.execute("SELECT * FROM terms ORDER BY RANDOM() LIMIT 1")

    result = cursor.fetchone()
    conn.close()
    return result


def get_terms_by_level(level: str, limit: int = 10):
    conn = connect_db()
    cursor = conn.cursor()
    level = normalize_level(level)
    cursor.execute(
        "SELECT * FROM terms WHERE lower(level) = ? ORDER BY english_word ASC LIMIT ?",
        (level, limit)
    )
    results = cursor.fetchall()
    conn.close()
    return results


def add_search_history(user_id: int, english_word: str):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO search_history (user_id, english_word) VALUES (?, ?)",
        (user_id, english_word.lower())
    )
    cursor.execute("""
    INSERT INTO term_stats (english_word, search_count)
    VALUES (?, 1)
    ON CONFLICT(english_word) DO UPDATE SET search_count = search_count + 1
    """, (english_word.lower(),))
    conn.commit()
    conn.close()


def get_user_history(user_id: int, limit: int = 10):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT english_word
    FROM search_history
    WHERE user_id = ?
    ORDER BY id DESC
    LIMIT ?
    """, (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results


def add_favorite(user_id: int, english_word: str):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR IGNORE INTO favorites (user_id, english_word)
    VALUES (?, ?)
    """, (user_id, english_word.lower()))
    conn.commit()
    conn.close()


def remove_favorite(user_id: int, english_word: str):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    DELETE FROM favorites
    WHERE user_id = ? AND english_word = ?
    """, (user_id, english_word.lower()))
    conn.commit()
    conn.close()


def is_favorite(user_id: int, english_word: str) -> bool:
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 1 FROM favorites
    WHERE user_id = ? AND english_word = ?
    """, (user_id, english_word.lower()))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def get_favorites(user_id: int, limit: int = 20):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT t.*
    FROM favorites f
    JOIN terms t ON lower(t.english_word) = lower(f.english_word)
    WHERE f.user_id = ?
    ORDER BY f.id DESC
    LIMIT ?
    """, (user_id, limit))
    results = cursor.fetchall()
    conn.close()
    return results


def get_similar_terms(word: str, limit: int = 5):
    conn = connect_db()
    cursor = conn.cursor()

    w = word.strip().lower()
    cursor.execute("""
    SELECT english_word FROM terms
    WHERE lower(english_word) LIKE ?
    ORDER BY english_word ASC
    LIMIT ?
    """, (f"%{w}%", limit))
    rows = cursor.fetchall()

    if rows:
        conn.close()
        return [r["english_word"] for r in rows]

    cursor.execute("SELECT english_word FROM terms")
    all_words = [r["english_word"] for r in cursor.fetchall()]
    conn.close()

    return get_close_matches(w, all_words, n=limit, cutoff=0.5)


def get_total_terms():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM terms")
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def get_total_users():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total = cursor.fetchone()["total"]
    conn.close()
    return total


def get_top_terms(limit: int = 10):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT english_word, search_count
    FROM term_stats
    ORDER BY search_count DESC, english_word ASC
    LIMIT ?
    """, (limit,))
    results = cursor.fetchall()
    conn.close()
    return results


def add_term(english_word, full_form, uzbek_translation, explanation, example, level):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO terms
    (english_word, full_form, uzbek_translation, explanation, example, level)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        english_word.strip().lower(),
        (full_form or "").strip(),
        uzbek_translation.strip(),
        explanation.strip(),
        (example or "").strip(),
        normalize_level(level)
    ))
    conn.commit()
    conn.close()


def update_term(english_word, full_form, uzbek_translation, explanation, example, level):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE terms
    SET full_form = ?, uzbek_translation = ?, explanation = ?, example = ?, level = ?
    WHERE lower(english_word) = ?
    """, (
        (full_form or "").strip(),
        uzbek_translation.strip(),
        explanation.strip(),
        (example or "").strip(),
        normalize_level(level),
        english_word.strip().lower()
    ))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    return updated > 0


def delete_term(english_word):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM terms WHERE lower(english_word) = ?",
        (english_word.strip().lower(),)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted > 0